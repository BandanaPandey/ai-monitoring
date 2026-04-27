from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

import httpx

from ai_monitoring_contracts.models import IngestLogRequest


class MonitorClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._buffer: list[IngestLogRequest] = []

    def log(self, payload: dict[str, Any] | IngestLogRequest) -> IngestLogRequest:
        event = payload if isinstance(payload, IngestLogRequest) else IngestLogRequest.model_validate(payload)
        self._buffer.append(event)
        return event

    def flush(self) -> list[dict[str, Any]]:
        responses: list[dict[str, Any]] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            while self._buffer:
                event = self._buffer.pop(0)
                response = client.post(
                    f"{self.base_url}/v1/logs",
                    json=event.model_dump(mode="json"),
                    headers={"x-api-key": self.api_key},
                )
                response.raise_for_status()
                responses.append(response.json())
        return responses

    @contextmanager
    def track(self, *, provider: str, model: str, system_prompt: str | None = None, **metadata: Any):
        start = time.perf_counter()
        context: dict[str, Any] = {
            "request_id": metadata.pop("request_id", str(uuid.uuid4())),
            "provider": provider,
            "model": model,
            "system_prompt": system_prompt,
            **metadata,
        }
        try:
            yield context
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.log({**context, "latency_ms": latency_ms})
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.log(
                {
                    **context,
                    "latency_ms": latency_ms,
                    "status": "error",
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                }
            )
            raise


def monitor_call(client: MonitorClient, *, provider: str, model: str, system_prompt: str | None = None) -> Callable:
    def decorator(fn: Callable) -> Callable:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            with client.track(provider=provider, model=model, system_prompt=system_prompt):
                return fn(*args, **kwargs)

        return wrapped

    return decorator

