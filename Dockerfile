# Taxot API + UI.
#   docker build -t taxot .
#   docker run -p 8000:8000 --env-file .env -v taxot-logs:/app/logs taxot
# (the volume keeps agent task checkpoints, logs/tasks.sqlite, and the query logs across restarts)
# API keys come from --env-file (never baked into the image; .dockerignore excludes .env).
# Ollama (Ask/Compare answer writer) is optional and runs on the host: -e OLLAMA_URL=http://host.docker.internal:11434
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/app/.hf
COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
COPY src ./src
COPY app ./app
COPY data ./data
COPY experiments ./experiments
# Pre-download models and build chunks + intent model at build time
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('intfloat/multilingual-e5-small'); CrossEncoder('BAAI/bge-reranker-base')" \
 && python -m src.ingest.ingest && python -m src.guardrails.intent --train
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8)"
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
