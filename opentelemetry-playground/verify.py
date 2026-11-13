#!/usr/bin/env python3
"""Validate live telemetry and Grafana queries against the provisioned dashboards."""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--greptime', default='http://localhost:24000')
    parser.add_argument('--grafana', default='http://localhost:13000')
    parser.add_argument('--shop', default='http://localhost:18080')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(url, data=None, headers=None):
        headers = dict(headers or {})
        if data is not None:
            headers['Content-Type'] = 'application/json'
        payload = json.dumps(data).encode() if data is not None else None
        try:
            with http.open(urllib.request.Request(url, payload, headers), timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{url}: HTTP {error.code}: {error.read().decode()}') from error

    def sql(statement):
        url = args.greptime + '/v1/sql?' + urllib.parse.urlencode({'sql': statement})
        result = json.loads(request(url))
        if result.get('error'):
            raise RuntimeError(result['error'])
        return result['output'][0]['records']['rows']

    def literal(value):
        return "'" + value.replace("'", "''") + "'"

    request(args.shop)
    print('PASS shop HTTP')
    for endpoint in ('/api/products/0PUK6V6EV0', '/api/currency', '/api/recommendations?productIds=0PUK6V6EV0', '/api/data?contextKeys=assembly'):
        result = json.loads(request(args.shop + endpoint))
        if not result:
            raise RuntimeError(f'Empty response from {endpoint}')
        print('PASS shop', endpoint)
    for uid in ('greptimedb', 'greptimedb-promql'):
        result = json.loads(request(args.grafana + '/api/datasources/uid/' + uid + '/health'))
        if result.get('status') != 'OK':
            raise RuntimeError(f'{uid}: {result}')
        print('PASS datasource', uid)

    query = urllib.parse.urlencode({'query': 'up{job=~"node|greptimedb|ad"}'})
    scrape = json.loads(request(args.greptime + '/v1/prometheus/api/v1/query?' + query))
    targets = scrape.get('data', {}).get('result', [])
    if {target['metric']['job'] for target in targets} != {'node', 'greptimedb', 'ad'} or any(float(target['value'][1]) != 1 for target in targets):
        raise RuntimeError(f'Scrape targets are missing or down: {targets}')
    print('PASS scrape targets: node, greptimedb, ad')

    checkout_trace = uuid.uuid4().hex
    trace_headers = {'traceparent': f'00-{checkout_trace}-{uuid.uuid4().hex[:16]}-01'}
    person = json.loads((root / '.runtime/opentelemetry-demo/src/load-generator/people.json').read_text())[0]
    person['userId'] = 'verify-' + checkout_trace
    request(args.shop + '/api/cart', {'userId': person['userId'], 'item': {'productId': '0PUK6V6EV0', 'quantity': 1}}, trace_headers)
    order = json.loads(request(args.shop + '/api/checkout', person, trace_headers))
    if not order.get('orderId'):
        raise RuntimeError(f'Checkout did not create an order: {order}')
    deadline = time.monotonic() + 30
    while True:
        quote_spans = sql(f'''SELECT "span_attributes.http.request.body.size", "span_attributes.http.response.body.size"
            FROM opentelemetry_traces WHERE trace_id = {literal(checkout_trace)}
            AND service_name = 'quote' AND span_name = 'POST /getquote' ''')
        if quote_spans:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Checkout succeeded but its quote server span was not ingested')
        time.sleep(1)
    if any(not isinstance(size, int) or size <= 0 or response_size is not None for size, response_size in quote_spans):
        raise RuntimeError(f'Quote HTTP body sizes were not normalized correctly: {quote_spans}')
    print(f'PASS checkout and quote span ingestion: {checkout_trace}')

    namespace = '\"resource_attributes.service.namespace\" = \'opentelemetry-demo\''
    services = [row[0] for row in sql(f'SELECT DISTINCT service_name FROM opentelemetry_traces WHERE {namespace}')]
    if not services:
        raise RuntimeError('No Astronomy Shop services have emitted traces')
    trace = sql(f'SELECT trace_id, COUNT(*) AS spans FROM opentelemetry_traces WHERE {namespace} AND "timestamp" > now() - INTERVAL \'30 minutes\' GROUP BY trace_id ORDER BY spans DESC LIMIT 1')
    if not trace:
        raise RuntimeError('No Astronomy Shop trace in the last 30 minutes')
    trace_id = trace[0][0]
    log_namespace = '''json_get_string(resource_attributes, '["service.namespace"]') = 'opentelemetry-demo' '''.strip()
    for name, statement in {
        'server spans': f'SELECT COUNT(*) FROM opentelemetry_traces WHERE {namespace} AND span_kind = \'SPAN_KIND_SERVER\' AND "timestamp" > now() - INTERVAL \'5 minutes\'',
        'application logs': f'SELECT COUNT(*) FROM opentelemetry_logs WHERE {log_namespace} AND "timestamp" > now() - INTERVAL \'5 minutes\'',
        'host metrics': 'SELECT COUNT(*) FROM node_cpu_seconds_total WHERE greptime_timestamp > now() - INTERVAL \'5 minutes\'',
        'flow output': 'SELECT COUNT(*) FROM service_error_rate_1m WHERE time_window > now() - INTERVAL \'5 minutes\'',
    }.items():
        count = sql(statement)[0][0]
        if count == 0:
            raise RuntimeError(f'No recent {name}')
        print(f'PASS {name}: {count} rows')

    instance = sql('SELECT DISTINCT instance FROM node_uname_info')[0][0]
    variables = {'level': 'All', 'search': ''}
    now = int(time.time() * 1000)
    failures = []
    checked = 0
    dashboard_root = root / 'grafana/dashboards'
    for english_path in dashboard_root.glob('*.json'):
        english = json.loads(english_path.read_text())
        chinese = json.loads((dashboard_root / 'zh-CN' / english_path.name).read_text())
        english_queries = {panel['id']: panel.get('targets', []) for panel in english['panels']}
        chinese_queries = {panel['id']: panel.get('targets', []) for panel in chinese['panels']}
        if english_queries != chinese_queries:
            raise RuntimeError(f'{english_path.name}: English and Chinese queries differ')
    for path in sorted(dashboard_root.rglob('*.json')):
        dashboard = json.loads(path.read_text())
        saved = json.loads(request(args.grafana + '/api/dashboards/uid/' + dashboard['uid']))
        if saved['dashboard']['panels'] != dashboard['panels']:
            raise RuntimeError(f'{path.name}: Grafana has not loaded the dashboard file')
        for variable in dashboard.get('templating', {}).get('list', []):
            query = variable.get('query')
            if isinstance(query, dict) and query.get('rawSql') and not sql(query['rawSql']):
                raise RuntimeError(f'{path.name}: empty variable {variable["name"]}')
        for panel in dashboard['panels']:
            if not panel.get('targets'):
                continue
            queries = json.loads(json.dumps(panel['targets']))
            for query in queries:
                query.update({'intervalMs': 15000, 'maxDataPoints': 300})
                if 'rawSql' in query:
                    selected_trace = trace_id if query.get('queryType') == 'traces' else ''
                    query['rawSql'] = query['rawSql'].replace('${trace_id:sqlstring}', literal(selected_trace))
                    query['rawSql'] = query['rawSql'].replace('${service:sqlstring}', ','.join(map(literal, services)))
                    for key, value in variables.items():
                        query['rawSql'] = query['rawSql'].replace('${' + key + ':sqlstring}', literal(value))
                if 'expr' in query:
                    query['expr'] = query['expr'].replace('$instance', re.escape(instance).replace('\\', '\\\\')).replace('${service:regex}', '(' + '|'.join(map(re.escape, services)) + ')')
            label = f'{path.relative_to(dashboard_root)} / {panel["title"]}'
            try:
                response = json.loads(request(args.grafana + '/api/ds/query', {'from': str(now - 1800000), 'to': str(now), 'queries': queries}))
                if not response.get('results'):
                    raise RuntimeError(f'No query results: {response}')
                missing = {query['refId'] for query in queries} - response['results'].keys()
                if missing:
                    raise RuntimeError(f'Missing query results: {sorted(missing)}')
                rows = 0
                for ref, result in response['results'].items():
                    if result.get('error') or result.get('status', 200) >= 400:
                        raise RuntimeError(result.get('error', str(result)))
                    query_rows = sum(len(frame.get('data', {}).get('values', [[]])[0]) for frame in result.get('frames', []) if frame.get('data', {}).get('values'))
                    if query_rows == 0:
                        raise RuntimeError(f'Query {ref} returned no data')
                    rows += query_rows
                print(f'PASS {label}: {rows} rows')
            except (RuntimeError, urllib.error.URLError) as error:
                failures.append(label)
                print(f'FAIL {label}: {error}')
            checked += 1
    logs = json.loads((root / 'grafana/dashboards/logs-traces.json').read_text())
    expected_spans = sql(f'SELECT COUNT(*) FROM opentelemetry_traces WHERE trace_id = {literal(trace_id)}')[0][0]
    for panel in logs['panels']:
        for target in panel.get('targets', []):
            if target.get('queryType') != 'traces':
                continue
            for selected, expected in ((trace_id, expected_spans), ('', 0)):
                query = dict(target)
                query['rawSql'] = query['rawSql'].replace('${trace_id:sqlstring}', literal(selected))
                response = json.loads(request(args.grafana + '/api/ds/query', {'from': '0', 'to': '1', 'queries': [query]}))
                result = response['results'][query['refId']]
                if result.get('error'):
                    raise RuntimeError(result['error'])
                count = sum(len(frame['data']['values'][0]) for frame in result.get('frames', []) if frame.get('data', {}).get('values'))
                if count != expected:
                    raise RuntimeError(f'{panel["title"]}: expected {expected} spans outside the time range, got {count}')
            print(f'PASS {panel["title"]}: complete trace outside time range and empty ID')
    log_target = next(panel for panel in logs['panels'] if panel['type'] == 'logs')['targets'][0]
    for service in ('frontend', 'cart'):
        query = dict(log_target)
        for variable, value in {'service': service, 'level': 'INFO', 'search': '', 'trace_id': ''}.items():
            query['rawSql'] = query['rawSql'].replace('${' + variable + ':sqlstring}', literal(value))
        response = json.loads(request(args.grafana + '/api/ds/query', {'from': str(now - 1800000), 'to': str(now), 'queries': [query]}))
        levels = []
        for result in response['results'].values():
            if result.get('error'):
                raise RuntimeError(result['error'])
            for frame in result.get('frames', []):
                for index, field in enumerate(frame['schema']['fields']):
                    if field['name'] == 'severity':
                        levels.extend(frame['data']['values'][index])
        if not levels or set(levels) != {'INFO'}:
            raise RuntimeError(f'{service}: INFO filter failed to normalize SDK severity')
        print(f'PASS {service}: INFO log filter')
    print(f'{checked - len(failures)}/{checked} panels passed')
    return bool(failures)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, urllib.error.URLError, TimeoutError) as error:
        print(f'FAIL {error}', file=sys.stderr)
        sys.exit(1)
