#!/usr/bin/env python3
"""Run the pinned Astronomy Shop stack in an isolated Compose project."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'
UPSTREAM = RUNTIME / 'opentelemetry-demo'
REVISION = '9bfe486ff48ee8a6ea942be74171342cb71a9327'
PROJECT = 'demo-scene-otel-playground'
CONFIG = RUNTIME / 'compose.json'


def render():
    RUNTIME.mkdir(exist_ok=True)
    if not UPSTREAM.exists():
        subprocess.run(['git', 'init', str(UPSTREAM)], check=True)
        subprocess.run(['git', '-C', str(UPSTREAM), 'remote', 'add', 'origin', 'https://github.com/open-telemetry/opentelemetry-demo.git'], check=True)
        subprocess.run(['git', '-C', str(UPSTREAM), 'fetch', '--depth', '1', 'origin', REVISION], check=True)
        subprocess.run(['git', '-C', str(UPSTREAM), 'checkout', '--detach', REVISION], check=True)
    revision = subprocess.check_output(['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise RuntimeError(f'{UPSTREAM} is at {revision}; expected {REVISION}. Existing checkout was not changed.')
    env = dict(
        os.environ,
        OTEL_COLLECTOR_CONFIG_EXTRAS=str(ROOT / 'otelcol-config-greptime.yml'),
        GRAFANA_ROUTER_COMPOSE=str(ROOT.parent / 'grafana-common/compose.yml'),
        PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT='http://localhost:18080/otlp-http/v1/traces',
    )
    command = ['docker', 'compose', '-f', str(UPSTREAM / 'compose.yaml'), '-f', str(ROOT / 'compose.greptime.yaml'), 'config', '--format', 'json']
    config = json.loads(subprocess.check_output(command, cwd=UPSTREAM, env=env, text=True))
    images = json.loads((ROOT / 'images.lock.json').read_text())
    config['name'] = PROJECT
    config['networks']['default']['name'] = PROJECT
    ports = {'frontend-proxy': {8080: 18080, 10000: 18081}, 'grafana-router': {3000: 13000}, 'greptimedb': {4000: 24000, 4001: 24001, 4002: 24002, 4003: 24003}}
    for name, service in config['services'].items():
        service.pop('container_name', None)
        service['image'] = images[name]
        if name == 'grafana':
            service.pop('ports', None)
        for port in service.get('ports', []):
            port['host_ip'] = '127.0.0.1'
            if port['target'] in ports.get(name, {}):
                port['published'] = str(ports[name][port['target']])
        for volume in service.get('volumes', []):
            if volume['type'] == 'bind':
                source = Path(volume['source'])
                prefix = UPSTREAM / 'greptime'
                if source.is_relative_to(prefix):
                    volume['source'] = str(ROOT / source.relative_to(prefix))
    for name, volume in config.get('volumes', {}).items():
        volume['name'] = f'{PROJECT}_{name}'
    CONFIG.write_text(json.dumps(config, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['up', 'down', 'ps', 'logs', 'config'])
    parser.add_argument('services', nargs='*', help='Optional services for logs')
    args = parser.parse_args()
    if args.action in ('up', 'config'):
        render()
    elif not CONFIG.exists():
        raise RuntimeError('Run demo.py up first')
    if args.action == 'config':
        print(CONFIG)
        return
    command = ['docker', 'compose', '-p', PROJECT, '-f', str(CONFIG)]
    if args.action == 'up':
        command += ['up', '-d', '--no-build', '--wait', '--wait-timeout', '180']
    elif args.action == 'logs':
        command += ['logs', '--tail', '100', *args.services]
    else:
        command += [args.action]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        if args.action == 'up':
            subprocess.run(['docker', 'compose', '-p', PROJECT, '-f', str(CONFIG), 'ps', '--all'])
            print('Inspect failures with: python3 demo.py logs <service>', file=sys.stderr)
        raise
    if args.action == 'up':
        print('Shop: http://localhost:18080')
        print('Grafana: http://localhost:13000/')
        print('GreptimeDB: http://localhost:24000/dashboard')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
