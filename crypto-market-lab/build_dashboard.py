#!/usr/bin/env python3
"""Generate English and Chinese market dashboards with identical SQL."""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DS = {'type': 'grafana-postgresql-datasource', 'uid': 'crypto-pg'}
PANELS = []
TRANSLATIONS = {}
FILTER = 'dataset = ${dataset:sqlstring} AND symbol = ${symbol:sqlstring}'
RAW = f'{FILTER} AND $__timeFilter(event_time)'
SINK = f'{FILTER} AND $__timeFilter(bucket)'
INTERVAL = 'CAST(${resolution:sqlstring} AS INTERVAL)'
CANDLES = f'''SELECT date_bin({INTERVAL}, event_time) AS time,
 CAST(first_value(price ORDER BY event_time,trade_id) AS DOUBLE) AS open,
 CAST(max(price) AS DOUBLE) AS high, CAST(min(price) AS DOUBLE) AS low,
 CAST(last_value(price ORDER BY event_time,trade_id) AS DOUBLE) AS close,
 CAST(sum(quantity) AS DOUBLE) AS volume,
 CAST(sum(notional) AS DOUBLE) AS quote_volume,
 count(*) AS trade_count,
 CAST(sum(CASE WHEN taker_buy THEN quantity ELSE 0 END) AS DOUBLE) AS buy_volume
FROM trades WHERE {RAW} AND ${{resolution:sqlstring}} = '1 second'
GROUP BY time
UNION ALL
SELECT date_bin({INTERVAL}, bucket) AS time,
 CAST(first_value(open ORDER BY bucket) AS DOUBLE) AS open,
 CAST(max(high) AS DOUBLE) AS high, CAST(min(low) AS DOUBLE) AS low,
 CAST(last_value(close ORDER BY bucket) AS DOUBLE) AS close,
 CAST(sum(volume) AS DOUBLE) AS volume,
 CAST(sum(quote_volume) AS DOUBLE) AS quote_volume,
 sum(trade_count) AS trade_count,
 CAST(sum(buy_volume) AS DOUBLE) AS buy_volume
FROM candles_1m WHERE {SINK} AND ${{resolution:sqlstring}} <> '1 second'
GROUP BY time'''


def panel(en, zh, kind, pos, query=None, unit='short', description='', zh_description=''):
    TRANSLATIONS[en] = zh
    if description:
        TRANSLATIONS[description] = zh_description or description
    item = {'id': len(PANELS) + 1, 'title': en, 'type': kind,
            'gridPos': dict(zip(('x','y','w','h'), pos)), 'description': description,
            'fieldConfig': {'defaults': {'unit': unit, 'color': {'mode': 'palette-classic'},
                                         'custom': {}}, 'overrides': []}, 'options': {}}
    if query:
        item['datasource'] = DS
        item['targets'] = [{'datasource': DS, 'refId': 'A', 'editorMode': 'code',
                            'format': 'time_series' if kind in ('timeseries','candlestick') else 'table',
                            'rawQuery': True, 'rawSql': query}]
    if kind == 'stat':
        item['options'] = {'reduceOptions': {'calcs': ['lastNotNull'], 'fields': '', 'values': False},
                           'colorMode': 'value', 'graphMode': 'none'}
    if kind == 'timeseries':
        item['fieldConfig']['defaults']['custom'] = {'drawStyle': 'line', 'lineWidth': 2,
                 'fillOpacity': 8, 'showPoints': 'never', 'spanNulls': False}
        item['options'] = {'tooltip': {'mode': 'multi'}, 'legend': {'displayMode': 'list', 'placement': 'bottom'}}
    PANELS.append(item)
    return item


header = panel('CRYPTO MARKET LAB / GreptimeDB', '加密货币行情实验室 / GreptimeDB', 'text', (0,0,24,3))
header['options'] = {'mode': 'markdown', 'content': '**Binance spot · real trades · UTC**  |  Dataset: **$dataset** · Symbol: **$symbol**\n\n**market** combines public archives and live capture; gaps stay visible. **replay-…** retains the original date, never masquerading as live. 1s candles query raw trades; 1m/5m candles use GreptimeDB Flow. CVD resets at the selected range start. Double-click or drag on a chart to inspect an interval.'}
TRANSLATIONS[header['options']['content']] = '**Binance 现货 · 真实成交 · UTC**  |  数据集：**$dataset** · 交易对：**$symbol**\n\n**market** 包含公开归档和实时采集，缺失区间保留为空。**replay-…** 保留原始日期，与实时数据隔离。1 秒 K 线查询明细；1/5 分钟 K 线读取 GreptimeDB Flow。累计成交量差从选定区间起点计算。拖动图表可缩小时间范围。'
for i,(en,zh,q,unit) in enumerate([
 ('Last price','最新价格',f'SELECT CAST(last_value(close ORDER BY bucket) AS DOUBLE) AS price FROM candles_1m WHERE {SINK}','suffix: USDT'),
 ('Trades · selected range','选定区间成交笔数',f'SELECT sum(trade_count) AS trades FROM candles_1m WHERE {SINK}','short'),
 ('Quote volume · selected range','选定区间成交额',f'SELECT CAST(sum(quote_volume) AS DOUBLE) AS notional FROM candles_1m WHERE {SINK}','suffix: USDT'),
 ('Live data age','实时数据年龄',f"SELECT date_part('epoch',now()) - date_part('epoch',max(last_event_time)) AS age_seconds FROM ingestion WHERE dataset='market' AND symbol=${{symbol:sqlstring}} AND worker='live'",'s'),
]):
    p=panel(en,zh,'stat',(i*6,3,6,4),q,unit)
    if i==3:
        p['fieldConfig']['defaults']['thresholds']={'mode':'absolute','steps':[{'color':'green','value':None},{'color':'orange','value':10},{'color':'red','value':30}]}
        p['fieldConfig']['defaults']['color']={'mode':'thresholds'}
        p['description']='Wall-clock age of the last live event, independent of the historical time range. A growing value indicates stale data.'
        TRANSLATIONS[p['description']]='最近实时成交距现在的时间，不受历史时间筛选影响。数值持续增长表示数据过期。'

p=panel('Price · OHLC','价格 · K 线','candlestick',(0,7,16,10),f'SELECT time,open,high,low,close,volume FROM ({CANDLES}) ORDER BY time','suffix: USDT')
p['options']={'mode':'candles','candleStyle':'candles','colorStrategy':'open-close','colors':{'up':'green','down':'red'},'fields':{'open':'open','high':'high','low':'low','close':'close','volume':'volume'},'legend':{'displayMode':'hidden'},'tooltip':{'mode':'single'}}
panel('Price versus VWAP','收盘价与 VWAP','timeseries',(16,7,8,10),f'SELECT time,close,quote_volume/nullif(volume,0) AS vwap FROM ({CANDLES}) ORDER BY time','suffix: USDT')
p=panel('Taker buy / sell volume','主动买入 / 卖出成交量','timeseries',(0,17,12,8),f'SELECT time,buy_volume,volume-buy_volume AS sell_volume FROM ({CANDLES}) ORDER BY time')
p['fieldConfig']['defaults']['custom'].update({'drawStyle':'bars','fillOpacity':70,'stacking':{'mode':'normal','group':'A'}})
panel('Cumulative volume delta','累计成交量差','timeseries',(12,17,12,8),f'SELECT time,sum(2*buy_volume-volume) OVER (ORDER BY time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cvd FROM ({CANDLES}) ORDER BY time',description='Taker buy quantity minus taker sell quantity, accumulated within the selected range. This is not net capital inflow.',zh_description='选定区间内主动买入数量减主动卖出数量的累计值，不表示资金净流入。')
panel('Trade activity','成交活跃度','timeseries',(0,25,12,7),f'SELECT time,trade_count FROM ({CANDLES}) ORDER BY time')
p=panel('Trade size distribution','成交金额分布','barchart',(12,25,12,7),f'''SELECT CASE WHEN notional < 100 THEN '<100' WHEN notional < 1000 THEN '100–1k'
WHEN notional < 10000 THEN '1k–10k' WHEN notional < 100000 THEN '10k–100k' ELSE '100k+' END AS size_usdt,
count(*) AS trades FROM trades WHERE {RAW} GROUP BY size_usdt ORDER BY min(notional)''')
p['options']={'orientation':'horizontal','xField':'size_usdt','showValue':'always','legend':{'displayMode':'hidden'}}
panel('Largest trades · selected range','选定区间大额成交','table',(0,32,24,8),f'''SELECT event_time AS time,trade_id,CAST(price AS DOUBLE) AS price,
CAST(quantity AS DOUBLE) AS quantity,CAST(notional AS DOUBLE) AS notional,
CASE WHEN taker_buy THEN 'BUY' ELSE 'SELL' END AS taker_side
FROM trades WHERE {RAW} ORDER BY notional DESC,event_time DESC LIMIT 50''')
panel('Submitted trades / second · last 15m','提交成交数 / 秒 · 最近 15 分钟','timeseries',(0,40,12,7),f'''SELECT date_bin(INTERVAL '5 seconds',ts) AS time, worker,
sum(rows_written)/5.0 AS rows_per_second FROM ingestion
WHERE {FILTER} AND ts > now() - INTERVAL '15 minutes' GROUP BY time,worker ORDER BY time''',description='Rows submitted successfully, including idempotent reimports. Raw trade counts are deduplicated.',zh_description='成功提交的行数，包含幂等重复导入；成交明细按主键去重。')
panel('Batch write time · last 15m','批次写入耗时 · 最近 15 分钟','timeseries',(12,40,12,7),f'''SELECT date_bin(INTERVAL '5 seconds',ts) AS time,worker,max(write_ms) AS write_ms
FROM ingestion WHERE {FILTER} AND ts > now() - INTERVAL '15 minutes' AND rows_written>0
GROUP BY time,worker ORDER BY time''','ms')
panel('Collector status · latest','采集器最新状态','table',(0,47,24,6),'''SELECT dataset,symbol,worker,max(ts) AS last_update,
last_value(state ORDER BY ts) AS state,last_value(status_text ORDER BY ts) AS status_text
FROM ingestion GROUP BY dataset,symbol,worker ORDER BY dataset,symbol,worker''',description='Replay speed and original date appear here. Compare last_update with wall-clock time; a stopped process cannot publish its own status.',zh_description='回放倍速和原始日期显示在此。last_update 应与当前时间比较；进程停止后无法继续报告状态。')
panel('Observed live trade ID gaps · last 24h','实时成交 ID 缺口记录 · 最近 24 小时','table',(0,53,24,6),'''SELECT ts AS time,symbol,first_missing_id,last_missing_id,status_text
FROM gaps WHERE ts > now() - INTERVAL '24 hours' ORDER BY ts DESC LIMIT 100''',description='Discontinuities observed on the live feed; no automatic backfill. Historical imports may cover these IDs later. Empty means no gap has been observed, not proof of complete history.',zh_description='实时流中观察到的 ID 不连续记录，不自动补齐；后续历史导入可能覆盖这些 ID。空表表示未观察到缺口，不代表历史完整。')

variables=[
 {'name':'dataset','label':'Dataset','type':'query','datasource':DS,'query':'SELECT DISTINCT dataset FROM candles_1m ORDER BY dataset','refresh':1,'current':{'text':'market','value':'market'},'includeAll':False,'multi':False},
 {'name':'symbol','label':'Symbol','type':'custom','query':'BTCUSDT,ETHUSDT','current':{'text':'BTCUSDT','value':'BTCUSDT'},'options':[{'text':s,'value':s,'selected':s=='BTCUSDT'} for s in ('BTCUSDT','ETHUSDT')]},
 {'name':'resolution','label':'Candle interval','type':'custom','query':'1s : 1 second,1m : 1 minute,5m : 5 minutes','current':{'text':'1m','value':'1 minute'},'options':[{'text':t,'value':v,'selected':t=='1m'} for t,v in [('1s','1 second'),('1m','1 minute'),('5m','5 minutes')]]},
]
links=[{'title':title,'type':'link','url':url,'includeVars':True,'keepTime':keep,'targetBlank':False} for title,url,keep in [
 ('English','/d/crypto-market',True),('简体中文','/d/crypto-market-zh',True),
 ('Live · 15m','/d/crypto-market?from=now-15m&to=now&var-dataset=market',False),
 ('History · 3d','/d/crypto-market?from=now-3d&to=now&var-dataset=market',False)]]
dashboard={'uid':'crypto-market','title':'Crypto Market Lab','id':None,'schemaVersion':39,'version':1,
           'tags':['GreptimeDB','crypto'],'timezone':'utc','editable':False,'refresh':'5s',
           'time':{'from':'now-15m','to':'now'},'timepicker':{'refresh_intervals':['1s','5s','10s','30s','1m']},
           'templating':{'list':variables},'links':links,'panels':PANELS}
TRANSLATIONS.update({'Crypto Market Lab':'加密货币行情实验室','Dataset':'数据集','Symbol':'交易对','Candle interval':'K 线周期'})

def translate(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('title','description','content','label') and isinstance(item,str):
                value[key]=TRANSLATIONS.get(item,item)
            elif key not in ('targets','query','datasource'):
                translate(item)
    elif isinstance(value,list):
        for item in value: translate(item)

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    directory=ROOT/'grafana/dashboards'
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'crypto.json').write_text(json.dumps(dashboard,ensure_ascii=False,indent=2)+'\n')
    chinese=copy.deepcopy(dashboard)
    translate(chinese)
    chinese['uid']+='-zh'
    (directory/'crypto-zh.json').write_text(json.dumps(chinese,ensure_ascii=False,indent=2)+'\n')
    print(f'Generated two dashboards with {len(PANELS)} panels each')
