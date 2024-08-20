from kafka import KafkaProducer
import time
import os

print("starting producer", flush=True)

topic = os.environ["KAFKA_TOPIC_NAME"]
print("using topic: ", topic, flush=True)

producer = KafkaProducer(bootstrap_servers="kafka:9092")
print("using producer: ", producer, flush=True)

while True:
    producer.send(topic, b"this is a test message")
    print("message sent", flush=True)
    time.sleep(3)
