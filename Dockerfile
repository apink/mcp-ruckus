FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY adapters/ ./adapters/
COPY inventory/ ./inventory/
COPY models/ ./models/
COPY tools/ ./tools/
COPY server.py security.py db.py admin.py ./

# Setup non-root user for security
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Default command (SSE transport on port 8000)
CMD ["python3", "server.py", "--transport", "sse", "--port", "8000"]