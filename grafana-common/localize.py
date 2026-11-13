#!/usr/bin/env python3
"""Generate Chinese dashboards without changing queries or datasource identifiers."""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    'native-histogram-lab/grafana/dashboards/latency.json',
    'vibration-lab/grafana/dashboards/vibration.json',
    'cloudflare-workers/grafana/dashboards/edge-traffic.json',
    'dify-monitoring/grafana/dashboards/dify.json',
    'flight-data-ingester/grafana_provisioning/dashboards/map.json',
    'genai-observability/grafana/dashboards/genai.json',
    'grafana-alloy/grafana_provisioning/dashboards/node_exporter_full.json',
    'nginx-log-metrics/grafana_provisioning/dashboards/analysis.json',
    'nginx-log-metrics/grafana_provisioning/dashboards/nginx.json',
    'opentelemetry-trace-django/grafana_provisioning/dashboards/todo-api.json',
    'self-hosted-game-analytics/grafana_provisioning/dashboards/game-telemetry.json',
]
DISPLAY_KEYS = {'title', 'description', 'displayName', 'label'}


def translate(value, translations):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in DISPLAY_KEYS and isinstance(item, str):
                value[key] = translations.get(item, item)
            elif key not in {'targets', 'query', 'datasource'}:
                translate(item, translations)
    elif isinstance(value, list):
        for item in value:
            translate(item, translations)


def language_links(dashboard, uid):
    links = [link for link in dashboard.get('links', [])
             if link.get('title') not in {'English', '简体中文'}]
    for title, target in [('English', uid), ('简体中文', uid + '-zh')]:
        links.append({'title': title, 'type': 'link', 'url': '/d/' + target,
                      'includeVars': True, 'keepTime': True, 'targetBlank': False})
    dashboard['links'] = links


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    translations = json.loads((ROOT / 'grafana-common/zh-CN.json').read_text())
    stale = []
    for source in SOURCES:
        path = ROOT / source
        original = json.loads(path.read_text())
        english = copy.deepcopy(original)
        language_links(english, english['uid'])
        chinese = copy.deepcopy(english)
        translate(chinese, translations)
        chinese['uid'] += '-zh'
        chinese['id'] = None
        if chinese['title'] == english['title']:
            chinese['title'] += '（中文）'
        target = path.parent / 'zh-CN' / path.name
        for output, data in [(path, english), (target, chinese)]:
            if args.check:
                if not output.exists() or json.loads(output.read_text()) != data:
                    stale.append(str(output.relative_to(ROOT)))
            elif not output.exists() or json.loads(output.read_text()) != data:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    if stale:
        raise SystemExit('Run python3 grafana-common/localize.py: ' + ', '.join(stale))
    print(f'{len(SOURCES)} dashboard pairs verified' if args.check else f'{len(SOURCES)} dashboard pairs generated')


if __name__ == '__main__':
    main()
