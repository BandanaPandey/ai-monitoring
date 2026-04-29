from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, status

from ai_monitoring_contracts.models import AuthToken, AuthenticatedIdentity
from ai_monitoring_contracts.persistence import ensure_postgres_schema, hash_password, seed_workspace_auth


@dataclass
class StaticAuthBackend:
    email: str
    password: str
    workspace_id: str
    user_id: str

    def bootstrap(self) -> None:
        return None

    def authenticate_user(self, email: str, password: str) -> AuthenticatedIdentity:
        if email != self.email or password != self.password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
        return AuthenticatedIdentity(
            user_id=self.user_id,
            email=self.email,
            workspace_id=self.workspace_id,
        )


@dataclass
class PostgresAuthBackend:
    postgres_dsn: str
    workspace_id: str
    workspace_name: str
    workspace_slug: str
    user_id: str
    email: str
    password: str
    api_key: str

    def _conn(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for Postgres auth") from exc
        return psycopg.connect(self.postgres_dsn, autocommit=True)

    def bootstrap(self) -> None:
        with self._conn() as conn:
            ensure_postgres_schema(conn)
            seed_workspace_auth(
                conn,
                workspace_id=self.workspace_id,
                workspace_name=self.workspace_name,
                workspace_slug=self.workspace_slug,
                user_id=self.user_id,
                user_email=self.email,
                password=self.password,
                api_key=self.api_key,
            )

    def authenticate_user(self, email: str, password: str) -> AuthenticatedIdentity:
        hashed = hash_password(password)
        with self._conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT users.id, users.email, memberships.workspace_id
                    FROM users
                    JOIN memberships ON memberships.user_id = users.id
                    WHERE users.email = %s AND users.password_hash = %s
                    """,
                    (email, hashed),
                )
                row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
        return AuthenticatedIdentity(user_id=row[0], email=row[1], workspace_id=row[2])


class AuthManager:
    def __init__(self, backend: StaticAuthBackend | PostgresAuthBackend, secret: str, ttl_seconds: int):
        self.backend = backend
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def bootstrap(self) -> None:
        self.backend.bootstrap()

    def authenticate(self, email: str, password: str) -> AuthToken:
        identity = self.backend.authenticate_user(email, password)
        payload = {
            "sub": identity.email,
            "user_id": identity.user_id,
            "workspace_id": identity.workspace_id,
            "exp": int(time.time()) + self.ttl_seconds,
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        signature = hmac.new(self.secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return AuthToken(
            access_token=f"{encoded}.{signature}",
            expires_in_seconds=self.ttl_seconds,
            workspace_id=identity.workspace_id,
            user_id=identity.user_id,
        )

    def validate_token(self, authorization: str = Header(default="")) -> dict:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            encoded, signature = token.split(".", maxsplit=1)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc
        expected = hmac.new(self.secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8"))
        if int(payload["exp"]) < int(time.time()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired_token")
        return payload


def build_auth_manager(settings: Any) -> AuthManager:
    if settings.storage_backend == "clickhouse":
        backend = PostgresAuthBackend(
            postgres_dsn=settings.postgres_dsn,
            workspace_id=settings.default_workspace_id,
            workspace_name=settings.default_workspace_name,
            workspace_slug=settings.default_workspace_slug,
            user_id=settings.default_user_id,
            email=settings.auth_email,
            password=settings.auth_password,
            api_key=settings.default_api_key,
        )
    else:
        backend = StaticAuthBackend(
            email=settings.auth_email,
            password=settings.auth_password,
            workspace_id=settings.default_workspace_id,
            user_id=settings.default_user_id,
        )
    return AuthManager(backend=backend, secret=settings.auth_secret, ttl_seconds=settings.access_token_ttl_seconds)
