import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

SAMPLE_RATE = 1024
SCENARIOS = ('normal', 'imbalance', 'looseness')
scenario = 'normal'
lock = threading.Lock()


def signal_window(mode, rng):
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    signal = 0.15 * np.sin(2 * np.pi * 30 * t) + rng.normal(0, 0.02, SAMPLE_RATE)
    if mode == 'imbalance':
        signal += 0.75 * np.sin(2 * np.pi * 30 * t)
    elif mode == 'looseness':
        signal += 0.35 * np.sin(2 * np.pi * 60 * t) + 0.2 * np.sin(2 * np.pi * 90 * t)
        signal[::128] += 2.0
    elif mode != 'normal':
        raise ValueError(f'Unknown scenario: {mode}')
    return signal


def features(signal):
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak = float(np.max(np.abs(signal)))
    window = np.hanning(len(signal))
    spectrum = 2 * np.abs(np.fft.rfft(signal * window)) / window.sum()
    spectrum[0] /= 2
    spectrum[-1] /= 2
    return rms, peak, peak / rms if rms else 0.0, spectrum


def post(path, body, content_type):
    req = urllib.request.Request(os.environ['GREPTIME_URL'] + path, data=body.encode(), headers={'Content-Type': content_type})
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.read()


def collect():
    rng = np.random.default_rng()
    while True:
        started = time.monotonic()
        with lock:
            mode = scenario
        signal = signal_window(mode, rng)
        rms, peak, crest, spectrum = features(signal)
        # Each window represents the preceding second of synthetic acceleration in g.
        end_ns = time.time_ns()
        start_ns = end_ns - 1_000_000_000
        rows = [f'vibration_raw,device=motor-01 scenario="{mode}",acceleration={value} {start_ns + i * 1_000_000_000 // SAMPLE_RATE}' for i, value in enumerate(signal)]
        rows += [f'vibration_spectrum,device=motor-01,frequency={i} scenario="{mode}",amplitude={value} {end_ns}' for i, value in enumerate(spectrum)]
        rows.append(f'vibration_features,device=motor-01 scenario="{mode}",rms={rms},peak={peak},crest_factor={crest} {end_ns}')
        try:
            post('/v1/influxdb/write?db=public&precision=ns', '\n'.join(rows), 'text/plain')
        except (OSError, urllib.error.HTTPError) as error:
            print(f'Vibration write failed: {error}', flush=True)
        time.sleep(max(0, 1 - (time.monotonic() - started)))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            body = Path('/app/index.html').read_bytes()
            content_type = 'text/html; charset=utf-8'
        elif self.path == '/state':
            with lock:
                body = json.dumps({'scenario': scenario, 'source': 'synthetic', 'sample_rate_hz': SAMPLE_RATE}).encode()
            content_type = 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(body)

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


if __name__ == '__main__':
    threading.Thread(target=collect, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
