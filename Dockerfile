# TaxSaathi API + UI. Ollama is expected on the host (set OLLAMA_URL, e.g. http://host.docker.internal:11434).
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
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
