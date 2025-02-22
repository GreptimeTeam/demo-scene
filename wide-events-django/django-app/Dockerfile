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

# Expose the port the app runs on
EXPOSE 8000

ENV DJANGO_SETTINGS_MODULE=myproject.settings

# Run the application with Gunicorn
CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000"]
