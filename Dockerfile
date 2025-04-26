FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    git build-essential linux-headers-amd64 tzdata && \
    rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Asia/Dhaka

# Upgrade pip and install wheel
RUN pip install --no-cache-dir -U pip wheel==0.45.1

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt /app
# Add aiohttp for health check server
RUN pip install -U -r requirements.txt aiohttp

# Copy application code
COPY . /app

# Expose port 8000 for health checks
EXPOSE 8000

# Run the bot
CMD ["python3", "main.py"]
