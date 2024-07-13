import string
import requests
import random
import time
import sys

BASE_URL = "http://nginx"
INTERVAL_MS = 1000
WRONG_REQ_RATE = 0.1


print("Request interval (ms) is set to", INTERVAL_MS)

random_words = []
with open("random-words.txt", "r") as f:
    for line in f:
        random_words.append(line.strip())
words_count = len(random_words)


print("Load random words from file, total", words_count, "words")


def request_other():
    path_length = random.randint(5, 20)
    random_path = "".join(random.choices(string.ascii_letters, k=path_length))
    url = f"{BASE_URL}/{random_path}"
    print("other requesting ", url)
    _response = requests.get(url)


def request_query():
    query_length = random.randint(5, 10)
    random_query = "-".join(random.choices(random_words, k=query_length))
    url = f"{BASE_URL}/query/{random_query}"
    print("query requesting ", url)
    _response = requests.get(url)


print("HTTP Client is running...")
while True:
    time.sleep(INTERVAL_MS / 1000)

    try:
        if random.random() < WRONG_REQ_RATE:
            request_other()
        else:
            request_query()

    except KeyboardInterrupt:
        print("KeyboardInterrupt caught")
        sys.exit(0)
    except requests.exceptions.ConnectionError:
        print("ConnectionError caught")
