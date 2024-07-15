FROM docker.io/python:3.12.4

WORKDIR /app

COPY server.py .

RUN pip install flask prometheus-client

CMD ["python3", "server.py"]
