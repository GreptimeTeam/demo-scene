"""Run with `python3 smoke_test.py` after `docker compose up -d --build`."""
import base64
import json
import os
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


def grafana(path, body=None):
    credentials = 'admin:' + os.getenv('GRAFANA_PASSWORD', 'admin')
    headers = {'Authorization': 'Basic ' + base64.b64encode(credentials.encode()).decode()}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = Request('http://localhost:3000' + path, headers=headers,
                      data=None if body is None else json.dumps(body).encode())
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    # Give this request a known trace ID so old 404s cannot make the check pass.
    trace_id = uuid.uuid4().hex
    request = Request('http://localhost:8000/todos/0/', headers={
        'traceparent': f'00-{trace_id}-0123456789abcdef-01',
    })
    try:
        urlopen(request, timeout=10).close()
    except HTTPError as error:
        assert error.code == 404, error.code
    else:
        raise AssertionError('Missing TODO must return 404')

    dashboard = grafana('/api/dashboards/uid/todo-api-trace-v2')['dashboard']
    summary, failed = dashboard['panels']
    for _ in range(30):
        result = grafana('/api/ds/query', {
            'from': str(int((time.time() - 900) * 1000)),
            'to': str(int(time.time() * 1000)),
            'queries': failed['targets'],
        })['results']['A']
        assert not result.get('error'), result
        frames = result.get('frames', [])
        if frames and trace_id in frames[0]['data']['values'][-1]:
            break
        time.sleep(1)
    else:
        raise AssertionError('New 404 trace did not appear in the failed-request panel')

    result = grafana('/api/ds/query', {
        'from': str(int((time.time() - 900) * 1000)),
        'to': str(int(time.time() * 1000)), 'queries': summary['targets'],
    })['results']['A']
    assert not result.get('error'), result
    assert 404 in result['frames'][0]['data']['values'][2], result

    link = failed['fieldConfig']['overrides'][-1]['properties'][0]['value'][0]['url']
    panes = json.loads(parse_qs(urlsplit(link.replace('${__value.raw}', trace_id)).query)['panes'][0])
    pane = panes['trace']
    assert pane['queries'][0]['query'] == trace_id
    trace = grafana(f"/api/datasources/proxy/uid/{pane['datasource']}/api/traces/{trace_id}")['data'][0]
    assert trace['traceID'] == trace_id and len(trace['spans']) >= 2, trace
    print('PASS: 404 → JSON2 summary/filter → trace link → Django/SQLite spans')


if __name__ == '__main__':
    main()
