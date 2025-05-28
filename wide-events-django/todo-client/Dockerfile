# Dockerfile (Production)

# Stage 1: Build stage
FROM python:3.11-slim

# Install uv
RUN pip install uv

# Copy the project files
WORKDIR /app
COPY . .

# Install dependencies using uv
RUN uv pip install --system -r requirements.lock

ENV OTEL_SEMCONV_STABILITY_OPT_IN=http,database

# Run the application with Gunicorn
CMD ["python", "src/todo_client/__init__.py"]
