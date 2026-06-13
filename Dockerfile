FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/data/hf_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV EMBEDDING_BACKEND=keyword \
    INGEST_ENABLE_SUMMARY=true \
    HF_HOME=/app/data/hf_cache

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY static ./static
COPY sample_docs ./sample_docs
COPY run.bat .

RUN mkdir -p data/chroma data/uploads data/documents

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --http h11 --timeout-keep-alive 120 --limit-max-requests 10000"]
