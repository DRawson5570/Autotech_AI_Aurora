# Mitchell Agent Docker Image
# ===========================
# Polling agent that runs at customer sites.
# Connects to ShopKeyPro and executes requests from Autotech AI.

FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
RUN pip install playwright && playwright install chromium

# Copy agent code
COPY addons/mitchell_agent /app/addons/mitchell_agent

# Create config directory
RUN mkdir -p /config

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default config location
ENV MITCHELL_CONFIG_PATH=/config/config.json

# Entry point
CMD ["python", "-m", "addons.mitchell_agent.agent.service"]
