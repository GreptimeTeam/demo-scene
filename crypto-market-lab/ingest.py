#!/usr/bin/env python3
"""Load public Binance spot trades, stream live trades, or replay an archive."""

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import re
import signal
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import requests
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parent
ARCHIVE = 'https://data.binance.vision/data/spot/daily'
STREAM = 'wss://data-stream.binance.vision:443/stream'
SYMBOLS = ('BTCUSDT', 'ETHUSDT')
LOG = logging.getLogger('crypto')
STOP = threading.Event()


def stop_on_sigterm():
    # Collectors poll this flag so `docker compose stop` flushes pending rows instead of waiting for SIGKILL.
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def timestamp(us):
    seconds, micros = divmod(us, 1_000_000)
    return datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S') + f'.{micros:06d}Z'


def unix_us(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps require a timezone')
    delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def fixed_decimal(value):
    number = Decimal(value)
    if not number.is_finite() or number <= 0:
        raise ValueError(f'Expected a finite positive decimal: {value}')
    if number >= Decimal('1e16') or number != number.quantize(Decimal('0.00000001')):
        raise ValueError(f'Value exceeds DECIMAL(24,8): {value}')
    return number


@dataclass(frozen=True)
class Trade:
    symbol: str
    trade_id: int
    price: Decimal
    quantity: Decimal
    event_us: int
    taker_buy: bool

    @property
    def notional(self):
        with localcontext() as context:
            context.prec = 50
            return self.price * self.quantity

    def values(self, dataset, origin, ingested_us):
        return '(' + ','.join([
            literal(dataset), literal(self.symbol), str(self.trade_id), str(self.price),
            str(self.quantity), str(self.notional), str(self.taker_buy).lower(),
            literal(timestamp(self.event_us)), literal(timestamp(ingested_us)), literal(origin),
        ]) + ')'


def archive_trade(symbol, row, archive_date):
    if len(row) != 7 or row[5] not in ('True', 'False', 'true', 'false'):
        raise ValueError(f'Invalid trade row: {row}')
    event_us = int(row[4]) * (1000 if archive_date < date(2025, 1, 1) else 1)
    if datetime.fromtimestamp(event_us // 1_000_000, timezone.utc).date() != archive_date:
        raise ValueError(f'Trade timestamp outside archive date: {row[4]}')
    return Trade(symbol, int(row[0]), fixed_decimal(row[1]), fixed_decimal(row[2]),
                 event_us, row[5].lower() == 'false')


def stream_trade(message):
    data = message['data']
    if data['e'] != 'trade' or data['s'] not in SYMBOLS or type(data['m']) is not bool:
        raise ValueError(f'Unexpected trade message: {message}')
    # The subscription explicitly requests microseconds, unlike the default REST API.
    return Trade(data['s'], int(data['t']), fixed_decimal(data['p']), fixed_decimal(data['q']),
                 int(data['T']), not data['m'])


class Database:
    def __init__(self, url=None):
        self.url = (url or os.getenv('GREPTIME_URL', 'http://localhost:25400')).rstrip('/')
        self.session = requests.Session()

    def sql(self, statement, database='crypto'):
        for attempt in range(3):
            try:
                response = self.session.post(self.url + '/v1/sql', params={'db': database},
                                             data={'sql': statement}, timeout=60)
                response.raise_for_status()
                result = response.json()
                if result.get('error'):
                    raise RuntimeError(result['error'])
                return result['output']
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def rows(self, statement):
        return self.sql(statement)[0]['records']['rows']

    def initialize(self):
        self.sql('CREATE DATABASE IF NOT EXISTS crypto', 'public')
        self.sql((ROOT / 'schema.sql').read_text())

    def write(self, trades, dataset, origin, text=''):
        if not trades:
            return
        ingested = time.time_ns() // 1000
        statement = ('INSERT INTO trades '
                     '(dataset,symbol,trade_id,price,quantity,notional,taker_buy,event_time,ingested_at,origin) VALUES '
                     + ','.join(t.values(dataset, origin, ingested) for t in trades))
        start = time.monotonic()
        self.sql(statement)
        elapsed = (time.monotonic() - start) * 1000
        for symbol in sorted({t.symbol for t in trades}):
            selected = [t for t in trades if t.symbol == symbol]
            self.status(dataset, symbol, origin, 'writing', len(selected), elapsed,
                        max(t.event_us for t in selected), text=text)

    def status(self, dataset, symbol, worker, state, rows=0, write_ms=0, last_event=None, text=''):
        ts = literal(timestamp(time.time_ns() // 1000))
        last = literal(timestamp(last_event)) if last_event is not None else 'NULL'
        self.sql(f'INSERT INTO ingestion VALUES ({literal(dataset)},{literal(symbol)},'
                 f'{literal(worker)},{ts},{literal(state)},{rows},{write_ms},{last},{literal(text)})')

    def gap(self, dataset, symbol, first_id, last_id):
        text = f'Observed trade ID gap {first_id}..{last_id}; not backfilled'
        self.sql(f'INSERT INTO gaps VALUES ({literal(dataset)},{literal(symbol)},'
                 f'{literal(timestamp(time.time_ns() // 1000))},{first_id},{last_id},{literal(text)})')
        LOG.warning('%s %s', symbol, text)


def download_archive(symbol, day, cache, kind='trades'):
    if kind not in ('trades', 'klines'):
        raise ValueError(kind)
    suffix = f'{symbol}-trades-{day.isoformat()}' if kind == 'trades' else f'{symbol}-1m-{day.isoformat()}'
    relative = f'{kind}/{symbol}/' + ('1m/' if kind == 'klines' else '') + suffix + '.zip'
    url = f'{ARCHIVE}/{relative}'
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (suffix + '.zip')
    checksum = cache / (suffix + '.zip.CHECKSUM')
    if not checksum.exists():
        response = requests.get(url + '.CHECKSUM', timeout=60)
        response.raise_for_status()
        content = response.text.strip()
        if not re.fullmatch(r'[0-9a-fA-F]{64}\s+\S+', content):
            raise ValueError(f'Invalid checksum response for {url}')
        checksum.write_text(content + '\n')
    expected = checksum.read_text().split()[0].lower()
    if target.exists():
        with target.open('rb') as handle:
            actual = hashlib.file_digest(handle, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError(f'Checksum mismatch: {target}; remove this cached ZIP and retry')
        return target
    LOG.info('Downloading %s', url)
    # A unique partial file also permits a history import and replay to share the cache.
    partial = cache / (suffix + f'.{uuid.uuid4().hex}.part')
    try:
        digest = hashlib.sha256()
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with partial.open('wb') as output:
                for block in response.iter_content(1024 * 1024):
                    output.write(block)
                    digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError(f'Checksum mismatch downloading {url}')
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def latest_archive_day(symbols):
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    for offset in range(3):
        day = yesterday - timedelta(days=offset)
        available = True
        for symbol in symbols:
            url = f'{ARCHIVE}/trades/{symbol}/{symbol}-trades-{day}.zip.CHECKSUM'
            response = requests.get(url, timeout=30)
            if response.status_code == 404:
                available = False
                break
            response.raise_for_status()
        if available:
            LOG.info('Latest published archive shared by %s: %s', ','.join(symbols), day)
            return day
    raise RuntimeError('No published archive for all selected symbols in the last three UTC days; specify --date')


def csv_rows(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.namelist()
        if len(entries) != 1 or not entries[0].endswith('.csv'):
            raise ValueError(f'Expected one CSV in {path}')
        with archive.open(entries[0]) as handle:
            yield from csv.reader(io.TextIOWrapper(handle, encoding='utf-8'))


def trades_from_archive(path, symbol, day, start=None, end=None):
    for row in csv_rows(path):
        trade = archive_trade(symbol, row, day)
        if start is not None and trade.event_us < start:
            continue
        if end is not None and trade.event_us >= end:
            continue
        yield trade


def load_history(db, symbols, days, cache, batch_size, dataset='market', start=None, end=None):
    for day in days:
        for symbol in symbols:
            db.status(dataset, symbol, 'history', 'downloading', text=day.isoformat())
            path = download_archive(symbol, day, cache)
            total, batch = 0, []
            started = time.monotonic()
            for trade in trades_from_archive(path, symbol, day, start, end):
                batch.append(trade)
                if len(batch) >= batch_size:
                    db.write(batch, dataset, 'history')
                    total += len(batch)
                    batch = []
            if batch:
                db.write(batch, dataset, 'history')
                total += len(batch)
            if not total:
                raise ValueError(f'No trades in selected interval: {symbol} {day}')
            duration = time.monotonic() - started
            db.status(dataset, symbol, 'history', 'complete', text=f'{day}: {total} trades in {duration:.2f}s')
            LOG.info('%s %s: %d trades in %.2fs (%.0f rows/s)', symbol, day, total, duration, total / duration)


def replay(db, symbols, day, cache, batch_size, speed, dataset, start=None, end=None):
    import heapq
    paths = [download_archive(symbol, day, cache) for symbol in symbols]
    streams = [trades_from_archive(path, symbol, day, start, end) for path, symbol in zip(paths, symbols)]
    started, first_us, last_flush, batch, count = time.monotonic(), None, time.monotonic(), [], 0
    for trade in heapq.merge(*streams, key=lambda t: (t.event_us, t.trade_id, t.symbol)):
        if first_us is None:
            first_us = trade.event_us
            LOG.info('Replay dataset=%s original_start=%s speed=%gx', dataset, timestamp(first_us), speed)
            for symbol in symbols:
                db.status(dataset, symbol, 'replay', 'running', text=f'Original date {day}; speed {speed:g}x')
        delay = started + (trade.event_us - first_us) / 1_000_000 / speed - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        batch.append(trade)
        count += 1
        if len(batch) >= batch_size or time.monotonic() - last_flush >= 0.5:
            db.write(batch, dataset, 'replay', text=f'Original date {day}; speed {speed:g}x')
            batch, last_flush = [], time.monotonic()
    db.write(batch, dataset, 'replay', text=f'Original date {day}; speed {speed:g}x')
    if not count:
        raise ValueError('No trades in selected replay interval')
    for symbol in symbols:
        db.status(dataset, symbol, 'replay', 'complete', text=f'Original date {day}; speed {speed:g}x; {count} total trades')


def live(db, symbols, batch_size, duration=None):
    url = STREAM + '?streams=' + '/'.join(f'{symbol.lower()}@trade' for symbol in symbols) + '&timeUnit=MICROSECOND'
    last_ids = {}
    last_times = {}
    for symbol in symbols:
        rows = db.rows(f"SELECT trade_id,event_time FROM trades WHERE dataset='market' AND symbol={literal(symbol)} "
                       "AND origin='live' ORDER BY event_time DESC,trade_id DESC LIMIT 1")
        if rows:
            last_ids[symbol], last_times[symbol] = rows[0]
    deadline = time.monotonic() + duration if duration else float('inf')
    backoff, batch = 1, []
    while time.monotonic() < deadline and not STOP.is_set():
        try:
            for symbol in symbols:
                db.status('market', symbol, 'live', 'connecting', last_event=last_times.get(symbol))
            with connect(url, open_timeout=20, ping_interval=20, ping_timeout=20, close_timeout=2) as websocket:
                last_flush, last_status = time.monotonic(), time.monotonic()
                for symbol in symbols:
                    db.status('market', symbol, 'live', 'connected', last_event=last_times.get(symbol))
                while time.monotonic() < deadline and not STOP.is_set():
                    try:
                        message = websocket.recv(timeout=min(0.5, max(0.001, deadline - time.monotonic())))
                    except TimeoutError:
                        message = None
                    if message is not None:
                        trade = stream_trade(json.loads(message))
                        if trade.symbol not in symbols:
                            raise ValueError(f'Unsubscribed symbol: {trade.symbol}')
                        previous = last_ids.get(trade.symbol)
                        if previous is not None and trade.trade_id > previous + 1:
                            db.gap('market', trade.symbol, previous + 1, trade.trade_id - 1)
                        last_ids[trade.symbol] = max(previous or 0, trade.trade_id)
                        last_times[trade.symbol] = max(last_times.get(trade.symbol, 0), trade.event_us)
                        batch.append(trade)
                        backoff = 1
                    if batch and (len(batch) >= batch_size or time.monotonic() - last_flush >= 0.5):
                        db.write(batch, 'market', 'live')
                        batch, last_flush = [], time.monotonic()
                    if time.monotonic() - last_status >= 10:
                        for symbol in symbols:
                            db.status('market', symbol, 'live', 'connected', last_event=last_times.get(symbol))
                        last_status = time.monotonic()
        except requests.RequestException:
            raise
        except (ConnectionClosed, InvalidHandshake, OSError, TimeoutError) as error:
            db.write(batch, 'market', 'live')
            batch = []
            for symbol in symbols:
                db.status('market', symbol, 'live', 'disconnected', last_event=last_times.get(symbol), text=str(error))
            LOG.warning('WebSocket disconnected: %s; retry in %ss', error, backoff)
            STOP.wait(min(backoff, max(0, deadline - time.monotonic())))
            backoff = min(backoff * 2, 30)
    db.write(batch, 'market', 'live')
    for symbol in symbols:
        db.status('market', symbol, 'live', 'stopped', last_event=last_times.get(symbol))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['init', 'history', 'live', 'replay'])
    parser.add_argument('--symbols', nargs='+', choices=SYMBOLS, default=list(SYMBOLS))
    parser.add_argument('--date', type=date.fromisoformat, help='UTC archive date; default: latest published day')
    parser.add_argument('--days', type=int, default=1, help='Historical UTC days starting at --date')
    parser.add_argument('--start', type=unix_us, help='Inclusive original event time, with timezone')
    parser.add_argument('--end', type=unix_us, help='Exclusive original event time, with timezone')
    parser.add_argument('--speed', type=float, default=10, help='Replay speed; event timestamps stay unchanged')
    parser.add_argument('--dataset', help='Replay dataset name; defaults to a unique replay ID')
    parser.add_argument('--batch-size', type=int, default=3000)
    parser.add_argument('--cache', type=Path, default=ROOT / 'data')
    parser.add_argument('--duration', type=float, help='Stop live capture after this many seconds')
    args = parser.parse_args()
    if args.days <= 0 or args.batch_size <= 0 or not 0 < args.speed < float('inf'):
        parser.error('days, batch-size, and speed must be positive and finite')
    if args.duration is not None and not 0 < args.duration < float('inf'):
        parser.error('duration must be positive and finite')
    if args.start is not None and args.end is not None and args.start >= args.end:
        parser.error('start must precede end')
    if args.mode == 'replay' and args.days != 1:
        parser.error('Replay accepts a single archive day')
    if args.dataset and (args.mode != 'replay' or not re.fullmatch(r'replay-[a-zA-Z0-9_-]+', args.dataset)):
        parser.error('dataset is only accepted for replay and must start with replay-')
    db = Database()
    if args.mode == 'init':
        db.initialize()
        return
    dataset = args.dataset or ('replay-' + uuid.uuid4().hex[:8] if args.mode == 'replay' else 'market')
    try:
        if args.mode in ('history', 'replay') and args.date is None:
            args.date = latest_archive_day(args.symbols)
        if args.mode == 'history':
            days = [args.date + timedelta(days=i) for i in range(args.days)]
            load_history(db, args.symbols, days, args.cache, args.batch_size, start=args.start, end=args.end)
        elif args.mode == 'live':
            stop_on_sigterm()
            live(db, args.symbols, args.batch_size, args.duration)
        else:
            replay(db, args.symbols, args.date, args.cache, args.batch_size, args.speed, dataset, args.start, args.end)
    except (requests.RequestException, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as error:
        LOG.error('%s failed: %s', args.mode, error)
        for symbol in args.symbols:
            db.status(dataset, symbol, args.mode, 'failed', text=str(error))
        raise


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
