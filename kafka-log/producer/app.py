from kafka import KafkaProducer
import time
import os

topic = os.environ["KAFKA_TOPIC_NAME"]

producer = KafkaProducer(bootstrap_servers="kafka:9092")
while True:
    producer.send(topic, "this is a test message")
    time.sleep(3000)
