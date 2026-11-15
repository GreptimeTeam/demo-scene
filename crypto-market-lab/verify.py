#!/usr/bin/env python3
"""Verify trade identity, Flow aggregates, public candles, and Grafana queries."""
import argparse
import json
import time
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import requests

from ingest import Database, Trade, csv_rows, download_archive, literal, unix_us

ROOT = Path(__file__).resolve().parent


def verify_identity(db):
    dataset = 'verify-' + uuid.uuid4().hex[:10]
    base = unix_us('2025-01-01T00:00:00Z')
    initial = [Trade('BTCUSDT', 12, Decimal('102'), Decimal('3'), base + 123456, False),
               Trade('BTCUSDT', 11, Decimal('101'), Decimal('2'), base + 123456, True)]
    late = Trade('BTCUSDT', 10, Decimal('99'), Decimal('1'), base + 1, True)
    try:
        for batch in (initial, initial):
            db.write(batch, dataset, 'verify')
            db.sql("ADMIN FLUSH_FLOW('crypto_candles_1m')")
            raw = db.rows(f'SELECT count(*),sum(quantity) FROM trades WHERE dataset={literal(dataset)}')[0]
            assert raw[0] == 2 and Decimal(raw[1]) == 5, raw
            candle = db.rows(f'SELECT open,close,volume,trade_count FROM candles_1m WHERE dataset={literal(dataset)}')[0]
            assert [Decimal(x) for x in candle[:3]] == [Decimal(101), Decimal(102), Decimal(5)] and candle[3] == 2, candle
        db.write([late], dataset, 'verify')
        db.sql("ADMIN FLUSH_FLOW('crypto_candles_1m')")
        candle = db.rows(f'SELECT open,high,low,close,volume,quote_volume,trade_count,buy_volume FROM candles_1m WHERE dataset={literal(dataset)}')[0]
        assert [Decimal(x) for x in candle] == [Decimal(x) for x in (99,102,99,102,6,607,3,3)], candle
        print('PASS identity: same-microsecond trades, duplicate write, event ordering, late arrival, Flow totals')
    finally:
        db.sql(f'DELETE FROM trades WHERE dataset={literal(dataset)}')
        db.sql("ADMIN FLUSH_FLOW('crypto_candles_1m')")
        db.sql(f'DELETE FROM candles_1m WHERE dataset={literal(dataset)}')
        db.sql(f'DELETE FROM ingestion WHERE dataset={literal(dataset)}')


def verify_history(db, day, symbols):
    db.sql("ADMIN FLUSH_FLOW('crypto_candles_1m')")
    for symbol in symbols:
        path = download_archive(symbol, day, ROOT / 'data', kind='klines')
        expected = {}
        multiplier = 1000 if day < date(2025,1,1) else 1
        for row in csv_rows(path):
            expected[int(row[0]) * multiplier] = [Decimal(row[i]) for i in (1,2,3,4,5,7,8,9)]
        low = unix_us(day.isoformat()+'T00:00:00Z')
        high = low + 86400 * 1_000_000
        rows = db.rows(f'''SELECT bucket,open,high,low,close,volume,quote_volume,trade_count,buy_volume
            FROM candles_1m WHERE dataset='market' AND symbol={literal(symbol)}
            AND bucket >= CAST({low} AS TIMESTAMP(6)) AND bucket < CAST({high} AS TIMESTAMP(6)) ORDER BY bucket''')
        actual = {row[0]: [Decimal(x) for x in row[1:]] for row in rows}
        if set(actual) != set(expected):
            raise AssertionError(f'{symbol}: expected {len(expected)} complete minutes, found {len(actual)}')
        for bucket, reference in expected.items():
            if any(abs(a-b) > Decimal('0.00000001') for a,b in zip(actual[bucket],reference)):
                raise AssertionError(f'{symbol} {bucket}: database={actual[bucket]}, official={reference}')
        raw = db.rows(f'''SELECT count(*),sum(quantity),sum(notional) FROM trades WHERE dataset='market'
            AND symbol={literal(symbol)} AND event_time >= CAST({low} AS TIMESTAMP(6))
            AND event_time < CAST({high} AS TIMESTAMP(6))''')[0]
        assert raw[0] == sum(int(v[6]) for v in expected.values()), raw
        assert Decimal(raw[1]) == sum(v[4] for v in expected.values()), raw
        assert abs(Decimal(raw[2])-sum(v[5] for v in expected.values())) <= Decimal('0.00000001'), raw
        print(f'PASS {symbol} {day}: {raw[0]} trades, {len(expected)} official OHLCV/quote-volume/taker-buy candles')


def verify_grafana(base, dataset, symbol, start_ms=None, end_ms=None):
    now = int(time.time()*1000)
    start_ms, end_ms = start_ms or now-15*60*1000, end_ms or now
    dashboards = []
    report = []
    for uid in ('crypto-market','crypto-market-zh'):
        response = requests.get(base+'/api/dashboards/uid/'+uid,timeout=30)
        response.raise_for_status()
        dashboard = response.json()['dashboard']
        dashboards.append(dashboard)
        for interval in ('1 second','1 minute','5 minutes'):
            for panel in dashboard['panels']:
                for target in panel.get('targets',[]):
                    query = target['rawSql']
                    for variable,value in [('dataset',dataset),('symbol',symbol),('resolution',interval)]:
                        query=query.replace('${'+variable+':sqlstring}',literal(value))
                    started=time.monotonic()
                    response=requests.post(base+'/api/ds/query',json={'from':str(start_ms),'to':str(end_ms),
                        'queries':[{**target,'rawSql':query,'intervalMs':1000,'maxDataPoints':5000}]},timeout=120)
                    response.raise_for_status()
                    result=response.json()['results']['A']
                    if result.get('error') or result.get('status',200)!=200:
                        raise AssertionError(f'{uid}/{panel["title"]}/{interval}: {result}')
                    count=sum(len(frame['data']['values'][0]) for frame in result.get('frames',[]) if frame.get('data',{}).get('values'))
                    # ID gaps are exceptional; an empty result is correct for an uninterrupted feed.
                    if not count and panel['id'] != 16:
                        raise AssertionError(f'{uid}/{panel["title"]}/{interval}: empty result')
                    report.append({'dashboard':uid,'panel':panel['title'],'interval':interval,'rows':count,
                                   'http_ms':round((time.monotonic()-started)*1000,2)})
    assert [p.get('targets') for p in dashboards[0]['panels']]==[p.get('targets') for p in dashboards[1]['panels']]
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data/grafana-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'PASS Grafana: {len(report)} queries across both languages and all three intervals; slowest={max(r["http_ms"] for r in report):.1f}ms')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grafana',default='http://localhost:25300')
    parser.add_argument('--history-date',type=date.fromisoformat)
    parser.add_argument('--symbols',nargs='+',default=['BTCUSDT','ETHUSDT'])
    parser.add_argument('--dataset',default='market')
    parser.add_argument('--skip-grafana',action='store_true')
    args=parser.parse_args()
    db=Database()
    verify_identity(db)
    if args.history_date:
        verify_history(db,args.history_date,args.symbols)
    if not args.skip_grafana:
        verify_grafana(args.grafana,args.dataset,args.symbols[0])

if __name__=='__main__':
    main()
