FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir mcp-proxy

COPY . .

EXPOSE 8080

ENV PORT=8080

CMD ["mcp-proxy", "--port=8080", "--host=0.0.0.0", "--", "python", "server.py"]
