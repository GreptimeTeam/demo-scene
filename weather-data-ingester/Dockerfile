FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ingest.py regions.py verify.py verify_grafana.py test_ingest.py ./
ENTRYPOINT ["python", "-u", "ingest.py"]
