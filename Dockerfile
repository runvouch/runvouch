# RunVouch server: FastAPI + SQLite in one process. No external services needed.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RUNVOUCH_DB=/data/runvouch.db \
    RUNVOUCH_PROOF_DIR=/data/proof/days

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY runvouch/ ./runvouch/
COPY templates/verify_proof.py ./templates/verify_proof.py
COPY LICENSE README.md ./

RUN useradd --system --uid 1000 --create-home runvouch \
 && mkdir -p /data && chown -R runvouch:runvouch /data /app
USER runvouch
VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "runvouch.server:app", "--host", "0.0.0.0", "--port", "8787", "--log-level", "warning"]
