# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright and Chrome
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
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Playwright cache paths
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV XDG_CACHE_HOME=/cache

# Store/pull Playwright cache with build cache optimization
RUN if [ ! -d $PLAYWRIGHT_BROWSERS_PATH ]; then \
        echo "...Copying Playwright Cache from Build Cache" && \
        mkdir -p $PLAYWRIGHT_BROWSERS_PATH && \
        if [ -d $XDG_CACHE_HOME/playwright/ ]; then \
            cp -R $XDG_CACHE_HOME/playwright/* $PLAYWRIGHT_BROWSERS_PATH/; \
        fi; \
    else \
        echo "...Storing Playwright Cache in Build Cache" && \
        mkdir -p $XDG_CACHE_HOME && \
        cp -R $PLAYWRIGHT_BROWSERS_PATH $XDG_CACHE_HOME/; \
    fi

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Store Playwright cache after installation
RUN echo "...Storing Playwright Cache in Build Cache" && \
    mkdir -p $XDG_CACHE_HOME && \
    cp -R $PLAYWRIGHT_BROWSERS_PATH $XDG_CACHE_HOME/

# Copy application code
COPY . .

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check using MCP endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.post('http://localhost:8000/mcp', json={'method': 'ping', 'jsonrpc': '2.0', 'id': 1}, timeout=5)"

# Run the server
CMD ["python", "server.py"]