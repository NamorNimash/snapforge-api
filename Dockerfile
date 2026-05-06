FROM python:3.11-slim

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/src

# Install Python deps
COPY requirements.txt ../
RUN pip install --no-cache-dir -r ../requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Install minimal fonts for rendering (skip deprecated ones that install-deps tries)
RUN apt-get update && apt-get install -y fonts-noto-core && rm -rf /var/lib/apt/lists/*

# Copy app
COPY src/ .

# Create data dir
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
