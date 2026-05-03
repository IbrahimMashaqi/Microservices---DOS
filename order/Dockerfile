# Order Server Dockerfile
# Lightweight Python 3.11 slim image for minimal container size

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .

EXPOSE 5002

CMD ["python", "app.py"]
