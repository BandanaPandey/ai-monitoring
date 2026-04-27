from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status

from ai_monitoring_contracts.models import IngestLogRequest, IngestLogResponse

from .config import Settings
from .storage import build_store, redact_payload

settings = Settings.from_env()
store = build_store(settings.storage_backend, settings.clickhouse_dsn, settings.file_store_path)

app = FastAPI(title="AI Monitoring Ingest API", version="0.1.0")


def require_api_key(x_api_key: str = Header(default="")) -> str:
    if x_api_key not in settings.api_keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")
    return x_api_key


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ingest-api"}


@app.post("/v1/logs", response_model=IngestLogResponse)
def ingest_log(payload: IngestLogRequest, _: str = Depends(require_api_key)) -> IngestLogResponse:
    sanitized = redact_payload(payload, settings.redact_emails, settings.redact_phones)
    inserted = store.write_log(sanitized)
    return IngestLogResponse(accepted=True, request_id=payload.request_id, deduplicated=not inserted)
