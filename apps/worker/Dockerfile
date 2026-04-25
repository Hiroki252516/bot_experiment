FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/backend:/app/apps/worker
ENV HF_HOME=/app/model_cache/huggingface
ENV TRANSFORMERS_CACHE=/app/model_cache/huggingface/transformers
ENV SENTENCE_TRANSFORMERS_HOME=/app/model_cache/sentence-transformers

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY apps/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/backend /app/apps/backend
COPY apps/worker /app/apps/worker
COPY packages /app/packages
COPY seeds /app/seeds

RUN mkdir -p /app/data/uploads /app/data/exports /app/model_cache/huggingface/transformers /app/model_cache/sentence-transformers

CMD ["python", "-m", "app.main"]
