import string
import requests
import random
import time
import sys
import ua_generator
import uuid

BASE_URL = "http://nginx"
INTERVAL_MS = 100
WRONG_REQ_RATE = 0.1


print("Request interval (ms) is set to", INTERVAL_MS)

random_words = []
with open("random-words.txt", "r") as f:
    for line in f:
        random_words.append(line.strip())
words_count = len(random_words)
words_per = words_count // 6
namespace_1 = random_words[:words_per]
namespace_2 = random_words[words_per : words_per * 3]
namespace_3 = random_words[words_per * 3 : words_per * 6]


print("Load random words from file, total", words_count, "words")


def random_header():
    ua = ua_generator.generate()
    headers = ua.headers.get()
    headers["referer"] = random.choice(
        [
            "https://www.google.com",
            "https://www.bing.com",
            "https://www.yahoo.com",
            "https://www.github.com",
            "https://www.stackoverflow.com",
            "https://www.reddit.com",
            "https://www.wikipedia.org",
            "https://www.youtube.com",
            "https://www.facebook.com",
            "https://www.twitter.com",
        ]
    )
    return headers


def request_other():
    path_length = random.randint(5, 20)
    random_path = "".join(random.choices(string.ascii_letters, k=path_length))
    url = f"{BASE_URL}/{random_path}"
    print("other requesting ", url)
    _response = requests.get(url, headers=random_header())


def request_query():
    trace_id = "-".join(
        [
            random.choices(namespace_1)[0],
            random.choices(namespace_2)[0],
            random.choices(namespace_3)[0],
            str(uuid.uuid4()),
        ]
    )
    url = f"{BASE_URL}/query/{trace_id}"
    print("query requesting ", url)
    _response = requests.get(url, headers=random_header())


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
