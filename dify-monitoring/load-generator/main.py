# load-generator/main.py
"""
Simulates realistic Dify usage patterns with three scenarios:
- normal:   steady 2 RPS, varied questions, all succeed
- degraded: inject slow responses (simulate model overload)
- failure:  inject errors (simulate API key expiry, context overflow)
"""
import os, time, random, requests

DIFY_API = os.getenv("DIFY_API_ENDPOINT")
API_KEY  = os.getenv("DIFY_API_KEY")
SCENARIO = os.getenv("SCENARIO", "normal")
RPS      = float(os.getenv("RPS", "2"))

QUESTIONS_NORMAL = [
    "What is GreptimeDB?",
    "How does GreptimeDB handle high cardinality?",
    "Compare GreptimeDB with InfluxDB",
    "What protocols does GreptimeDB support?",
    "How to set up TTL in GreptimeDB?",
]

QUESTIONS_LONG = [
    # These trigger longer context / slower responses
    "Give me a detailed architecture comparison of GreptimeDB vs "
    "ClickHouse vs TimescaleDB vs InfluxDB covering storage engine, "
    "query language, scalability, and cost efficiency. " * 3,
]

def send_query(question: str):
    try:
        resp = requests.post(
            f"{DIFY_API}/chat-messages",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "inputs": {},
                "query": question,
                "response_mode": "blocking",
                "user": f"load-test-user-{random.randint(1,10)}",
            },
            timeout=60,
        )
        return resp.status_code, resp.elapsed.total_seconds()
    except Exception as e:
        return 0, str(e)

def main():
    print(f"Starting load generator: scenario={SCENARIO}, rps={RPS}")
    cycle = 0
    while True:
        cycle += 1

        if SCENARIO == "normal":
            q = random.choice(QUESTIONS_NORMAL)
        elif SCENARIO == "degraded":
            # Every 10th request is a long one
            q = random.choice(QUESTIONS_LONG) if cycle % 10 == 0 \
                else random.choice(QUESTIONS_NORMAL)
        elif SCENARIO == "failure":
            # Every 5th request uses invalid params to trigger errors
            if cycle % 5 == 0:
                q = ""  # empty query → triggers Dify validation error
            else:
                q = random.choice(QUESTIONS_NORMAL)

        status, duration = send_query(q)
        print(f"[{cycle}] status={status} duration={duration:.2f}s "
              f"question={q[:50]}...")

        time.sleep(1.0 / RPS)

if __name__ == "__main__":
    main()
