import json
import os
import random
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExponentialBucketHistogramAggregation, View
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

SCENARIOS = ('normal', 'long-tail', 'burst')
scenario = 'normal'
lock = threading.Lock()
histogram = None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            body = Path('/app/index.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/state':
            with lock:
                body = json.dumps({'scenario': scenario}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/work':
            with lock:
                current = scenario
            started = time.perf_counter()
            delay = random.uniform(0.015, 0.025)
            if current == 'long-tail' and random.random() < 0.05:
                delay = random.uniform(0.8, 1.2)
            time.sleep(delay)
            histogram.record(time.perf_counter() - started, {'scenario': current})
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        global scenario
        if self.path != '/scenario':
            self.send_error(404)
            return
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 1024:
            self.send_error(400)
            return
        try:
            value = json.loads(self.rfile.read(size))['scenario']
        except (ValueError, KeyError, TypeError):
            self.send_error(400)
            return
        if value not in SCENARIOS:
            self.send_error(400)
            return
        with lock:
            scenario = value
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


def load():
    while True:
        with lock:
            rate = 10 if scenario == 'burst' else 2.5
        started = time.monotonic()
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/work', timeout=5):
                pass
        except OSError as error:
            print(f'Load request failed: {error}', flush=True)
        time.sleep(max(0, 1 / rate - (time.monotonic() - started)))


if __name__ == '__main__':
    exporter = OTLPMetricExporter(endpoint=os.environ['OTEL_EXPORTER_OTLP_METRICS_ENDPOINT'])
    provider = MeterProvider(
        metric_readers=[PeriodicExportingMetricReader(exporter, export_interval_millis=5000)],
        views=[View(instrument_name='lab.request.duration', aggregation=ExponentialBucketHistogramAggregation())],
    )
    histogram = provider.get_meter('latency-lab').create_histogram('lab.request.duration', unit='s')
    server = ThreadingHTTPServer(('0.0.0.0', 8080), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(4):
        threading.Thread(target=load, daemon=True).start()
    try:
        threading.Event().wait()
    finally:
        provider.shutdown()
        server.shutdown()
