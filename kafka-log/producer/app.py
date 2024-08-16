from kafka import KafkaProducer
import time

producer = KafkaProducer(bootstrap_servers="kafka:9092")
while True:
    producer.send("test-topic", "this is a test message")
    time.sleep(3000)
