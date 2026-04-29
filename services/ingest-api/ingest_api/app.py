from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status

from ai_monitoring_contracts.models import IngestLogRequest, IngestLogResponse

from .config import Settings
from .storage import build_store, redact_payload

settings = Settings.from_env()
store = build_store(settings)

app = FastAPI(title="AI Monitoring Ingest API", version="0.1.0")


@app.on_event("startup")
def bootstrap_storage() -> None:
    store.bootstrap()


def require_workspace(x_api_key: str = Header(default="")) -> str:
    workspace_id = store.resolve_workspace(x_api_key)
    if workspace_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")
    return workspace_id


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ingest-api"}


@app.post("/v1/logs", response_model=IngestLogResponse)
def ingest_log(payload: IngestLogRequest, workspace_id: str = Depends(require_workspace)) -> IngestLogResponse:
    scoped_payload = payload.model_copy(update={"workspace_id": workspace_id})
    sanitized = redact_payload(scoped_payload, settings.redact_emails, settings.redact_phones)
    inserted = store.write_log(sanitized)
    return IngestLogResponse(accepted=True, request_id=payload.request_id, deduplicated=not inserted)
