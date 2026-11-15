"""Sample the latest changed Binance best quote once per second."""
import json
import logging
import time

import requests

from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.sync.client import connect

from ingest import STOP, Database, STREAM, SYMBOLS, fixed_decimal, literal, stop_on_sigterm, timestamp


def parse_quote(data, received_us):
    if data['s'] not in SYMBOLS:
        raise ValueError('Unexpected quote symbol')
    bid, bid_qty, ask, ask_qty = [fixed_decimal(data[key]) for key in ('b', 'B', 'a', 'A')]
    if bid > ask:
        raise ValueError('Crossed best quote')
    return (data['s'], int(data['u']), bid, bid_qty, ask, ask_qty, received_us)


def write_quotes(db, pending):
    sampled = time.time_ns() // 1000
    rows = []
    for symbol, update, bid, bid_qty, ask, ask_qty, received in pending.values():
        rows.append(f"('market',{literal(symbol)},{literal(timestamp(sampled))},{update},"
                    f"{bid},{bid_qty},{ask},{ask_qty},{literal(timestamp(received))})")
    if rows:
        db.sql('INSERT INTO quotes VALUES ' + ','.join(rows))


def main():
    stop_on_sigterm()
    db = Database()
    url = STREAM + '?streams=' + '/'.join(s.lower() + '@bookTicker' for s in SYMBOLS)
    backoff = 1
    while not STOP.is_set():
        pending = {}
        try:
            with connect(url, open_timeout=20, ping_interval=20, ping_timeout=20, close_timeout=2) as ws:
                flushed = time.monotonic()
                for symbol in SYMBOLS:
                    db.status('market', symbol, 'quotes', 'connected')
                while not STOP.is_set():
                    try:
                        message = ws.recv(timeout=0.25)
                    except TimeoutError:
                        message = None
                    if message is not None:
                        quote = parse_quote(json.loads(message)['data'], time.time_ns() // 1000)
                        pending[quote[0]] = quote
                        backoff = 1
                    if time.monotonic() - flushed >= 1:
                        write_quotes(db, pending)
                        pending.clear()
                        flushed = time.monotonic()
            write_quotes(db, pending)
        except requests.RequestException:
            raise
        except (ConnectionClosed, InvalidHandshake, OSError, TimeoutError) as error:
            write_quotes(db, pending)
            for symbol in SYMBOLS:
                db.status('market', symbol, 'quotes', 'disconnected', text=str(error))
            logging.warning('Quote stream disconnected: %s', error)
            STOP.wait(backoff)
            backoff = min(30, backoff * 2)
    for symbol in SYMBOLS:
        db.status('market', symbol, 'quotes', 'stopped')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
