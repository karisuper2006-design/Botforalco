# Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variable for token (override at runtime)
ENV TELEGRAM_BOT_TOKEN=""

# Run the bot
CMD ["python", "Untitled-1.py"]
