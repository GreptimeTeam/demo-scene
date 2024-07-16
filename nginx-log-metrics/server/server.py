from flask import Flask
import random
import time
from prometheus_client import Histogram, start_http_server
import requests
import json
import datetime

ERROR_RATE = 0.1
EXTRA_DELAY_RATE = 0.002

app = Flask(__name__)
request_latency = Histogram("query_latency", "Latency of query method")


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/query/<trace_id>")
@request_latency.time()
def query(trace_id: str):
    # Generate random bytes
    random_bytes = random.randbytes(len(trace_id) * 8)

    # Generate random delay
    delay = random.uniform(0.1, 1.0)
    time.sleep(delay)

    # Extra long delay with small probability
    if random.random() < EXTRA_DELAY_RATE:
        time.sleep(10)

    # compose json log
    log = {
        "timestamp": str(datetime.datetime.now()),
        "trace_id": trace_id,
        "delay": delay,
        "payload_size": len(random_bytes),
    }
    log = json.dumps(log)
    requests.post(
        "http://greptimedb:4000/v1/events/logs?db=public&table=server_log&pipeline_name=server_log",
        data=log,
        headers={"Content-Type": "application/json"},
    )

    if random.random() < ERROR_RATE:
        return "ERROR", random.choice([400, 401, 408, 409, 500, 502, 503, 504])
    else:
        return random_bytes


if __name__ == "__main__":
    start_http_server(5679)
    app.run(host="0.0.0.0", port=5678)
