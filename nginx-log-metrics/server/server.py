from flask import Flask
import random
import time

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "Hello, World!"


@app.route("/query/<query>")
def query(query: str):
    # Generate random bytes
    random_bytes = bytes(random.getrandbits(8) for _ in range(len(query)))

    # Generate random delay
    delay = random.uniform(0.1, 1.0)
    time.sleep(delay)

    return random_bytes


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5678)