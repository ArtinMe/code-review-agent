FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY codereview ./codereview

# Render and similar hosts set PORT and sit behind one proxy.
ENV PORT=8000 TRUST_PROXY=1 PYTHONUNBUFFERED=1
EXPOSE 8000

# One worker keeps the per-minute and per-day limits accurate; threads handle concurrency.
CMD gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT codereview.web.app:app
