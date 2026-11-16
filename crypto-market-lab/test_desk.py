"""Exercise the desk HTTP contract against the running local demo."""
import os
import time
import unittest

import requests

from ingest import Database, literal


class DeskIntegrationTest(unittest.TestCase):
    base = os.getenv('DESK_URL', 'http://desk:8080')

    def setUp(self):
        self.datasets = []

    def tearDown(self):
        # Replays write into the shared `crypto` database; leftovers would show up in Grafana's dataset list.
        db = Database()
        try:
            for dataset in self.datasets:
                db.sql(f'DELETE FROM trades WHERE dataset={literal(dataset)}')
            db.sql("ADMIN FLUSH_FLOW('crypto_candles_1m')")
            for dataset in self.datasets:
                db.sql(f'DELETE FROM candles_1m WHERE dataset={literal(dataset)}')
                db.sql(f'DELETE FROM ingestion WHERE dataset={literal(dataset)}')
        finally:
            db.session.close()

    def start_replay(self, payload):
        response = requests.post(self.base+'/api/replay/start', json=payload)
        response.raise_for_status()
        self.datasets.append(response.json()['dataset'])

    def get(self, path):
        response = requests.get(self.base + path, timeout=60)
        response.raise_for_status()
        return response.json()

    def wait_terminal(self):
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            job = self.get('/api/replay')
            if job['status'] in ('complete', 'stopped', 'failed'):
                return job
            time.sleep(.2)
        self.fail('Replay did not reach a terminal state within 30 seconds')

    def test_market_and_benchmark(self):
        for symbol in ('BTCUSDT', 'ETHUSDT'):
            for mode in ('live', 'history'):
                data = self.get(f'/api/desk?symbol={symbol}&mode={mode}')
                self.assertTrue(data['candles'])
                self.assertTrue(data['latest'])
                self.assertTrue(data['trades'])
                if mode == 'live':
                    self.assertTrue(data['quotes'])
                else:
                    self.assertEqual(data['quotes'], [])
                minute = data['candles'][0][0]
                detail = self.get(f'/api/minute?symbol={symbol}&start={minute}')
                self.assertTrue(detail['rows'])
                self.assertTrue(all(minute <= row[0] < minute+60_000_000 for row in detail['rows']))
            comparison = self.get('/api/benchmark?symbol='+symbol)
            self.assertTrue(comparison['equal'])
            self.assertEqual(comparison['buckets'], 1440)
        self.assertEqual(requests.get(self.base+'/api/desk?symbol=INVALID').status_code,400)
        self.assertEqual(requests.post(self.base+'/api/replay/start',json={},headers={'Origin':'https://example.com'}).status_code,403)

    def test_pause_step_and_no_future_data(self):
        from decimal import Decimal
        from ingest import timestamp
        first, _ = self.get('/api/catalog?symbol=BTCUSDT')[0]
        start = first // 60_000_000 * 60_000_000
        self.start_replay(dict(symbol='BTCUSDT',start=timestamp(start),minutes=1,speed=100,paused=True))
        def until(predicate):
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                state = self.get('/api/replay')
                if predicate(state):
                    return state
                self.assertNotEqual(state['status'],'failed',state)
                time.sleep(.05)
            self.fail(self.get('/api/replay'))
        try:
            until(lambda s: s['status']=='paused')
            frame=self.get('/api/desk?symbol=BTCUSDT&mode=replay')
            self.assertEqual(frame['summary'][0],0)
            self.assertEqual(frame['tape'],[])
            requests.post(self.base+'/api/replay/control',json={'action':'step'}).raise_for_status()
            step=until(lambda s:s['written']==1)
            frame=self.get('/api/desk?symbol=BTCUSDT&mode=replay')
            self.assertEqual(frame['summary'][0],1)
            self.assertEqual(len(frame['tape']),1)
            self.assertEqual(frame['tape'][0][-1],step['last_trade_id'])
            minute=self.get(f'/api/minute?symbol=BTCUSDT&mode=replay&start={start}')
            self.assertEqual(len(minute['rows']),1)
            time.sleep(.1)
            self.assertEqual(self.get('/api/replay')['written'],1)
            requests.post(self.base+'/api/replay/control',json={'action':'speed','speed':100}).raise_for_status()
            requests.post(self.base+'/api/replay/control',json={'action':'play'}).raise_for_status()
            self.assertEqual(self.wait_terminal()['status'],'complete')
            frame=self.get('/api/desk?symbol=BTCUSDT&mode=replay')
            self.assertEqual(sum(r[7] for r in frame['candles']),frame['summary'][0])
            self.assertEqual(sum(Decimal(r[1])+Decimal(r[2]) for r in frame['profile']),Decimal(frame['summary'][1]))
        finally:
            requests.post(self.base+'/api/replay/stop',json={}).raise_for_status()
            until(lambda s:s['status'] not in ('loading','running','paused','stopping'))

    def test_replay_completion_and_stop(self):
        first, _ = self.get('/api/catalog?symbol=BTCUSDT')[0]
        start = first // 60_000_000 * 60_000_000
        from ingest import timestamp
        payload = dict(symbol='BTCUSDT',start=timestamp(start),minutes=1,speed=100)
        self.start_replay(payload)
        job = self.wait_terminal()
        self.assertEqual(job['status'],'complete',job)
        self.assertEqual(job['written'],job['total'])
        self.assertGreater(job['total'],0)
        db = Database()
        columns = 'count(*),sum(quantity),sum(notional)'
        expected = db.rows(f"SELECT {columns} FROM trades WHERE dataset='market' AND symbol='BTCUSDT' AND event_time >= CAST({start} AS TIMESTAMP(6)) AND event_time < CAST({start+60_000_000} AS TIMESTAMP(6))")
        actual = db.rows(f"SELECT {columns} FROM trades WHERE dataset={literal(job['dataset'])}")
        self.assertEqual(actual,expected)
        replay = self.get('/api/desk?symbol=BTCUSDT&mode=replay')
        self.assertEqual(replay['summary'][0],job['total'])
        self.assertTrue(replay['candles'])
        self.assertEqual(replay['quotes'],[])
        payload.update(minutes=5,speed=1)
        self.start_replay(payload)
        self.assertEqual(requests.post(self.base+'/api/replay/start',json=payload).status_code,400)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            if self.get('/api/replay').get('written',0) > 0:
                break
            time.sleep(.1)
        else:
            self.fail('Replay produced no trades before the stop test')
        requests.post(self.base+'/api/replay/stop',json={}).raise_for_status()
        job=self.wait_terminal()
        self.assertEqual(job['status'],'stopped',job)
        self.assertGreater(job['written'],0)
        self.assertLess(job['written'],job['total'])
        actual = db.rows(f"SELECT count(*) FROM trades WHERE dataset={literal(job['dataset'])}")[0][0]
        self.assertEqual(actual,job['written'])
        db.session.close()


if __name__ == '__main__':
    unittest.main()
