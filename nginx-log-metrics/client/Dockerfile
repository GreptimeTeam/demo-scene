FROM docker.io/python:3.12.4

WORKDIR /app

RUN pip install requests ua-generator

COPY client.py .
COPY random-words.txt .

CMD ["python3", "client.py"]
