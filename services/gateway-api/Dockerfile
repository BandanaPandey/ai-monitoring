FROM python:3.11-slim

WORKDIR /app

COPY packages/contracts /app/packages/contracts
COPY services/gateway-api /app/services/gateway-api

RUN pip install --no-cache-dir /app/packages/contracts /app/services/gateway-api

EXPOSE 8000

CMD ["uvicorn", "gateway_api.app:app", "--host", "0.0.0.0", "--port", "8000"]

