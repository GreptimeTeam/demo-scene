from flask import Flask
import random
import time
from prometheus_client import Histogram, Gauge, start_http_server

ERROR_RATE = 0.1

app = Flask(__name__)
request_latency = Histogram("query_latency", "Latency of query method")


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/query/<query>")
@request_latency.time()
def query(query: str):
    # Generate random bytes
    random_bytes = bytes(random.getrandbits(8) for _ in range(len(query)))

    # Generate random delay
    delay = random.uniform(0.1, 1.0)
    time.sleep(delay)

    if random.random() < ERROR_RATE:
        return "ERROR", random.choice([400, 401, 408, 409, 500, 502, 503, 504])
    else:
        return random_bytes


if __name__ == "__main__":
    start_http_server(5679)
    app.run(host="0.0.0.0", port=5678)
