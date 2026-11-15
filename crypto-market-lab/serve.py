"""Local market desk with bounded, read-only GreptimeDB queries."""
import json
import logging
import math
import os
import statistics
import time
from decimal import Decimal
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from ingest import Database, SYMBOLS, literal, unix_us
from replay import Replay

REPLAY = Replay()

WEB = Path(__file__).resolve().parent / 'web'


def bounds(db, symbol, mode):
    end = time.time_ns() // 1000
    if mode == 'history':
        rows = db.rows(f"SELECT max(event_time) FROM trades WHERE dataset='market' AND symbol={literal(symbol)} AND origin='history'")
        if not rows or rows[0][0] is None:
            raise ValueError('No historical trades imported')
        end = rows[0][0] + 1
    return end - 60 * 60 * 1_000_000, end


def replay_filter(job):
    if not job['written']:
        return ' AND 1=0'
    return (f" AND (event_time < CAST({job['cursor']} AS TIMESTAMP(6)) OR "
            f"(event_time = CAST({job['cursor']} AS TIMESTAMP(6)) AND trade_id <= {job['last_trade_id']}))")


def desk(db, symbol, mode, resolution='1 minute'):
    dataset, job, cutoff = 'market', None, ''
    if mode == 'replay':
        job = REPLAY.snapshot()
        if job.get('symbol') != symbol:
            raise ValueError('Start a replay for this symbol first')
        start, end, dataset = job['start'], job['end'], job['dataset']
        cutoff = replay_filter(job)
    else:
        start, end = bounds(db, symbol, mode)
        start = start // 60_000_000 * 60_000_000
    where = f"dataset={literal(dataset)} AND symbol={literal(symbol)}"
    window = f"event_time >= CAST({start} AS TIMESTAMP(6)) AND event_time < CAST({end} AS TIMESTAMP(6)){cutoff}"
    if resolution == '1 second' or mode == 'replay':
        candle_sql = f"""SELECT date_bin(INTERVAL '{resolution}',event_time) AS bucket,
            first_value(price ORDER BY event_time,trade_id),max(price),min(price),
            last_value(price ORDER BY event_time,trade_id),sum(quantity),
            sum(CASE WHEN taker_buy THEN quantity ELSE 0 END),count(*),sum(notional)
            FROM trades WHERE {where} AND {window} GROUP BY bucket ORDER BY bucket"""
    else:
        candle_sql = f"""SELECT bucket,open,high,low,close,volume,buy_volume,trade_count,quote_volume
            FROM candles_1m WHERE {where} AND bucket >= CAST({start} AS TIMESTAMP(6))
            AND bucket < CAST({end} AS TIMESTAMP(6)) ORDER BY bucket"""
    candles = db.rows(candle_sql)
    summary = db.rows(f"""SELECT count(*),sum(quantity),sum(notional),
        sum(CASE WHEN taker_buy THEN quantity ELSE 0 END),max(event_time),min(price),max(price)
        FROM trades WHERE {where} AND {window}""")[0]
    trades = db.rows(f"""SELECT event_time,price,quantity,notional,taker_buy,trade_id
        FROM trades WHERE {where} AND {window} ORDER BY notional DESC LIMIT 8""")
    tape = db.rows(f"""SELECT event_time,price,quantity,notional,taker_buy,trade_id
        FROM trades WHERE {where} AND {window} ORDER BY event_time DESC,trade_id DESC LIMIT 200""")
    profile, step = [], None
    if summary[0]:
        width = max(float(summary[6])-float(summary[5]), float(summary[6])*.0001)/24
        scale = 10**math.floor(math.log10(width))
        step = math.ceil(width/scale)*scale
        profile = db.rows(f"""SELECT floor(CAST(price AS DOUBLE)/{step})*{step} AS price_band,
            sum(CASE WHEN taker_buy THEN quantity ELSE 0 END) AS buys,
            sum(CASE WHEN taker_buy THEN 0 ELSE quantity END) AS sells
            FROM trades WHERE {where} AND {window} GROUP BY price_band ORDER BY price_band DESC""")
    quotes = []
    if mode == 'live':
        quotes = db.rows(f"""SELECT sampled_at,bid_price,bid_quantity,ask_price,ask_quantity,received_at
            FROM quotes WHERE {where} AND sampled_at >= CAST({end-15*60*1000000} AS TIMESTAMP(6))
            ORDER BY sampled_at""")
    latest = [[tape[0][1], tape[0][0]]] if tape else []
    return dict(symbol=symbol, mode=mode, dataset=dataset, start=start, end=end, candles=candles,
                summary=summary, latest=latest, trades=trades, quotes=quotes, tape=tape,
                profile=profile, profile_step=step, replay=job, resolution=resolution,
                candle_sql=candle_sql, now=time.time_ns()//1000)


def benchmark(db, symbol):
    latest = db.rows(f"SELECT max(event_time) FROM trades WHERE dataset='market' AND symbol={literal(symbol)} AND origin='history'")[0][0]
    if latest is None:
        raise ValueError('Import an archive before running the comparison')
    start = latest // 86400000000 * 86400000000
    end = start + 86400000000
    where = f"dataset='market' AND symbol={literal(symbol)}"
    raw = f'''SELECT date_bin(INTERVAL '1 minute',event_time) AS bucket,
    count(*) AS trade_count, sum(quantity) AS volume, sum(notional) AS quote_volume
FROM trades WHERE {where}
    AND event_time >= CAST({start} AS TIMESTAMP(6)) AND event_time < CAST({end} AS TIMESTAMP(6))
GROUP BY bucket ORDER BY bucket'''
    flow = f'''SELECT bucket,trade_count,volume,quote_volume FROM candles_1m
WHERE {where} AND bucket >= CAST({start} AS TIMESTAMP(6))
    AND bucket < CAST({end} AS TIMESTAMP(6)) ORDER BY bucket'''
    timings = {'raw': [], 'flow': []}
    results = {}
    for iteration in range(3):
        for name, sql in ([('raw', raw), ('flow', flow)] if iteration % 2 == 0 else [('flow', flow), ('raw', raw)]):
            before = time.perf_counter()
            results[name] = db.rows(sql)
            timings[name].append((time.perf_counter()-before)*1000)
    def normalized(rows):
        return [[r[0], int(r[1]), Decimal(r[2]), Decimal(r[3])] for r in rows]
    equal = normalized(results['raw']) == normalized(results['flow'])
    return dict(equal=equal, trades=sum(r[1] for r in results['raw']), buckets=len(results['flow']),
                raw_sql=raw, flow_sql=flow, timings=timings,
                raw_ms=statistics.median(timings['raw']), flow_ms=statistics.median(timings['flow']), start=start)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/grafana':
            self.send_response(302)
            self.send_header('Location', 'http://localhost:' + os.getenv('GRAFANA_PORT', '25300') + '/')
            self.end_headers()
            return
        if not url.path.startswith('/api/'):
            return super().do_GET()
        try:
            query = parse_qs(url.query)
            symbol = query.get('symbol', ['BTCUSDT'])[0]
            mode = query.get('mode', ['live'])[0]
            if symbol not in SYMBOLS or mode not in ('live', 'history', 'replay'):
                raise ValueError('Invalid symbol or mode')
            db = Database()
            try:
                if url.path == '/api/desk':
                    resolution = query.get('resolution', ['1 second' if mode == 'replay' else '1 minute'])[0]
                    if resolution not in ('1 second', '1 minute'):
                        raise ValueError('Invalid chart resolution')
                    result = desk(db, symbol, mode, resolution)
                elif url.path == '/api/replay':
                    result = REPLAY.snapshot()
                elif url.path == '/api/catalog':
                    result = db.rows(f"SELECT min(event_time),max(event_time) FROM trades WHERE dataset='market' AND symbol={literal(symbol)} AND origin='history'")
                elif url.path == '/api/minute':
                    start = int(query.get('start', ['0'])[0])
                    if start <= 0 or start % 60_000_000:
                        raise ValueError('Select a UTC minute')
                    dataset, cutoff = 'market', ''
                    if mode == 'replay':
                        job = REPLAY.snapshot()
                        if job.get('symbol') != symbol:
                            raise ValueError('No replay for this symbol')
                        dataset = job['dataset']
                        cutoff = replay_filter(job)
                    sql = f'''SELECT event_time,trade_id,price,quantity,notional,taker_buy
FROM trades WHERE dataset={literal(dataset)} AND symbol={literal(symbol)}
AND event_time >= CAST({start} AS TIMESTAMP(6))
AND event_time < CAST({start+60_000_000} AS TIMESTAMP(6)){cutoff}
ORDER BY notional DESC LIMIT 25'''
                    result = dict(sql=sql, rows=db.rows(sql), start=start)
                elif url.path == '/api/benchmark':
                    result = benchmark(db, symbol)
                else:
                    self.send_error(404)
                    return
            finally:
                db.session.close()
            self.respond(200, result)
        except ValueError as error:
            self.respond(400, {'error': str(error)})
        except Exception:
            logging.exception('Market query failed')
            self.respond(502, {'error': 'GreptimeDB query failed; see desk logs'})

    def do_POST(self):
        # The local demo has no auth; mutations require same-origin JSON requests.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            self.respond(403, {'error': 'Cross-origin writes are not allowed'})
            return
        if self.headers.get('Content-Type') != 'application/json':
            self.respond(415, {'error': 'Expected application/json'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2048:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Expected a JSON object')
            if self.path == '/api/replay/stop':
                result = REPLAY.stop()
            elif self.path == '/api/replay/control':
                action, speed = payload.get('action'), payload.get('speed')
                if action not in ('pause', 'play', 'step', 'speed'):
                    raise ValueError('Unknown replay action')
                if action == 'speed' and (type(speed) is not int or speed not in (1, 10, 100)):
                    raise ValueError('Speed must be 1, 10, or 100')
                result = REPLAY.control(action, speed)
            elif self.path == '/api/replay/start':
                symbol = payload.get('symbol')
                minutes, speed = payload.get('minutes'), payload.get('speed')
                if symbol not in SYMBOLS or type(minutes) is not int or minutes not in (1, 5):
                    raise ValueError('Select BTCUSDT or ETHUSDT and a 1- or 5-minute interval')
                if type(speed) is not int or speed not in (1, 10, 100):
                    raise ValueError('Speed must be 1, 10, or 100')
                start = unix_us(str(payload.get('start', '')))
                if start <= 0 or start % 60_000_000:
                    raise ValueError('Start must be aligned to a UTC minute')
                paused = payload.get('paused', False)
                if type(paused) is not bool:
                    raise ValueError('Invalid paused flag')
                result = REPLAY.start(symbol, start, minutes, speed, paused)
            else:
                self.respond(404, {'error': 'Unknown endpoint'})
                return
            self.respond(200, result)
        except (ValueError, TypeError) as error:
            self.respond(400, {'error': str(error)})

    def respond(self, status, result):
        body = json.dumps(result).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
