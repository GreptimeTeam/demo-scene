FROM docker.io/python:3.12.4

WORKDIR /app

RUN pip install flask prometheus-client requests

COPY server.py .

CMD ["python3", "server.py"]
