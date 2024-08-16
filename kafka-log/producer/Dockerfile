FROM docker.io/python:3.12.4

WORKDIR /app

RUN pip install kafka-python

COPY app.py .

CMD ["python3", "app.py"]
