from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from ai_monitoring_contracts.models import (
    AuthToken,
    CompareLogsRequest,
    CompareLogsResponse,
    DashboardSummary,
    LogDetail,
    LogListResponse,
    LogQueryFilters,
)

from .auth import build_auth_manager
from .config import Settings
from .query_service import build_query_facade

settings = Settings.from_env()
query_service = build_query_facade(settings.storage_backend, settings.file_store_path, settings.clickhouse_dsn)
auth_manager = build_auth_manager(settings)

app = FastAPI(title="AI Monitoring Gateway API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def require_identity(payload: Annotated[dict, Depends(auth_manager.validate_token)]) -> dict:
    return payload


@app.on_event("startup")
def bootstrap_services() -> None:
    auth_manager.bootstrap()
    query_service.bootstrap()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "gateway-api"}


@app.post("/v1/auth/login", response_model=AuthToken)
def login(payload: LoginRequest) -> AuthToken:
    return auth_manager.authenticate(payload.email, payload.password)


@app.get("/v1/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(identity: dict = Depends(require_identity)) -> DashboardSummary:
    return query_service.get_dashboard_summary(identity["workspace_id"])


@app.get("/v1/logs", response_model=LogListResponse)
def list_logs(
    identity: dict = Depends(require_identity),
    limit: int = Query(default=50, le=200),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    model: str | None = Query(default=None),
    feature: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    from_timestamp: str | None = Query(default=None, alias="from"),
    to_timestamp: str | None = Query(default=None, alias="to"),
) -> LogListResponse:
    filters = LogQueryFilters.model_validate(
        {
            "limit": limit,
            "search": search,
            "status": status,
            "model": model,
            "feature": feature,
            "user_id": user_id,
            "from": from_timestamp,
            "to": to_timestamp,
        }
    )
    return query_service.list_logs(identity["workspace_id"], filters=filters)


@app.get("/v1/logs/{request_id}", response_model=LogDetail)
def get_log(request_id: str, identity: dict = Depends(require_identity)) -> LogDetail:
    item = query_service.get_log_detail(identity["workspace_id"], request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="log_not_found")
    return item


@app.post("/v1/logs/compare", response_model=CompareLogsResponse)
def compare_logs(payload: CompareLogsRequest, identity: dict = Depends(require_identity)) -> CompareLogsResponse:
    response = query_service.compare_logs(identity["workspace_id"], payload.left_request_id, payload.right_request_id)
    if response is None:
        raise HTTPException(status_code=404, detail="compare_target_missing")
    return response
