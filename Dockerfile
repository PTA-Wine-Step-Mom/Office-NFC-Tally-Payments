# Use Python 3.11 slim image for Raspberry Pi
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including dos2unix for line ending conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ /app/

# Convert line endings to Unix format (fixes Windows CRLF issues)
RUN dos2unix /app/start.sh && chmod +x /app/start.sh

# Create directory for database
RUN mkdir -p /app/data

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Initialize database and run application
CMD ["sh", "start.sh"]
