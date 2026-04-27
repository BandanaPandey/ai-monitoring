FROM python:3.11-slim

WORKDIR /app

COPY packages/contracts /app/packages/contracts
COPY services/ingest-api /app/services/ingest-api

RUN pip install --no-cache-dir /app/packages/contracts /app/services/ingest-api

EXPOSE 8001

CMD ["uvicorn", "ingest_api.app:app", "--host", "0.0.0.0", "--port", "8001"]

