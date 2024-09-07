from kafka import KafkaProducer
import time
import os

print("starting producer", flush=True)

log_topic = os.environ["KAFKA_LOG_TOPIC_NAME"]
print("using topic: ", log_topic, flush=True)
metric_topic = os.environ["KAFKA_METRIC_TOPIC_NAME"]
print("using topic: ", metric_topic, flush=True)

producer = KafkaProducer(bootstrap_servers="kafka:9092")
print("using producer: ", producer, flush=True)

while True:
    producer.send(
        log_topic,
        b'127.0.0.1 - - [04/Sep/2024:15:46:13 -0700] "GET / HTTP/1.1" 200 615 "-" "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"',
    )
    producer.send(
        metric_topic,
        b"monitor,host=host1 cpu=1.2",
    )
    print("message sent", flush=True)
    time.sleep(3)
