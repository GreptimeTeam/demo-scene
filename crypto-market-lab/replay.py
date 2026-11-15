"""Replay stored trades using a controllable event clock and isolated identities."""
import bisect
import logging
import threading
import time
import uuid
from decimal import Decimal

from ingest import Database, Trade, literal

ACTIVE = ('loading', 'running', 'paused', 'stopping')


class Replay:
    def __init__(self):
        self.condition = threading.Condition()
        self.state = {'status': 'idle'}
        self.clock_us = 0
        self.clock_wall = 0
        self.steps = 0

    def snapshot(self):
        with self.condition:
            return self.state.copy()

    def start(self, symbol, start, minutes, speed, paused=False):
        with self.condition:
            if self.state['status'] in ACTIVE:
                raise ValueError('A replay is already active; stop it before starting another')
            self.state = dict(status='loading', symbol=symbol, start=start,
                              end=start+minutes*60_000_000, cursor=start, speed=speed,
                              dataset='replay-'+uuid.uuid4().hex[:12], written=0, total=0,
                              last_trade_id=None)
            self.steps = 0
            job = self.state.copy()
            threading.Thread(target=self.run, args=(job, paused), daemon=True).start()
            return job

    def event_clock(self):
        if self.state['status'] != 'running':
            return self.clock_us
        return self.clock_us + (time.monotonic()-self.clock_wall)*self.state['speed']*1_000_000

    def control(self, action, speed=None):
        with self.condition:
            status = self.state['status']
            if action == 'stop':
                if status in ACTIVE:
                    self.state['status'] = 'stopping'
            elif action == 'speed':
                if status not in ('running', 'paused') or speed not in (1, 10, 100):
                    raise ValueError('Speed changes require a running or paused replay')
                self.clock_us = self.event_clock()
                self.clock_wall = time.monotonic()
                self.state['speed'] = speed
            elif action == 'pause':
                if status != 'running':
                    raise ValueError('Pause requires a running replay')
                self.clock_us = self.event_clock()
                self.state['status'] = 'paused'
            elif action == 'play':
                if status != 'paused':
                    raise ValueError('Play requires a paused replay')
                self.clock_wall = time.monotonic()
                self.state['status'] = 'running'
                self.steps = 0
            elif action == 'step':
                if status != 'paused':
                    raise ValueError('Step requires a paused replay')
                self.steps += 1
            else:
                raise ValueError('Unknown replay action')
            self.condition.notify_all()
            return self.state.copy()

    def stop(self):
        return self.control('stop')

    def run(self, job, paused):
        db = Database()
        try:
            rows = db.rows(f'''SELECT trade_id,price,quantity,event_time,taker_buy FROM trades
                WHERE dataset='market' AND origin='history' AND symbol={literal(job['symbol'])}
                AND event_time >= CAST({job['start']} AS TIMESTAMP(6))
                AND event_time < CAST({job['end']} AS TIMESTAMP(6))
                ORDER BY event_time,trade_id LIMIT 100001''')
            if not rows:
                raise ValueError('No archived trades in the selected interval')
            if len(rows) > 100000:
                raise ValueError('Interval exceeds 100,000 trades; select one minute')
            times = [row[3] for row in rows]
            with self.condition:
                self.state['total'] = len(rows)
                if self.state['status'] != 'stopping':
                    self.state['status'] = 'paused' if paused else 'running'
                self.clock_us, self.clock_wall = job['start'], time.monotonic()
            index = 0
            while index < len(rows):
                with self.condition:
                    if self.state['status'] == 'stopping':
                        break
                    if self.state['status'] == 'paused':
                        if not self.steps:
                            self.condition.wait()
                            continue
                        self.steps -= 1
                        end = index+1
                    else:
                        now = self.event_clock()
                        end = min(index+200, bisect.bisect_right(times, now))
                        if end <= index:
                            delay = (times[index]-now)/1_000_000/self.state['speed']
                            self.condition.wait(timeout=min(.1, max(0, delay)))
                            continue
                    batch = [Trade(job['symbol'], row[0], Decimal(row[1]), Decimal(row[2]), row[3], row[4])
                             for row in rows[index:end]]
                    # A pause acknowledges a committed batch boundary, never an in-flight write.
                    db.write(batch, job['dataset'], 'replay')
                    index = end
                    self.state.update(written=index, cursor=batch[-1].event_us,
                                      last_trade_id=batch[-1].trade_id)
                    if self.state['status'] == 'paused':
                        self.clock_us = batch[-1].event_us
            db.sql("ADMIN FLUSH_FLOW('crypto_candles_1m')")
            with self.condition:
                status = 'stopped' if self.state['status'] == 'stopping' else 'complete'
                db.status(job['dataset'], job['symbol'], 'replay', status, text=f'{index}/{len(rows)} trades')
                self.state['status'] = status
        except Exception as error:
            logging.exception('Replay failed')
            with self.condition:
                self.state.update(status='failed', error=str(error) if isinstance(error, ValueError)
                                  else 'Replay failed; see desk logs')
        finally:
            db.session.close()
