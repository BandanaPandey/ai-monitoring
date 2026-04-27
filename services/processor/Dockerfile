FROM python:3.11-slim

WORKDIR /app

COPY packages/contracts /app/packages/contracts
COPY services/processor /app/services/processor

RUN pip install --no-cache-dir /app/packages/contracts /app/services/processor

CMD ["python", "-m", "processor.main", "run-loop"]

