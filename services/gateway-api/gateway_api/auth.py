from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException, status

from ai_monitoring_contracts.models import AuthToken


class AuthManager:
    def __init__(self, email: str, password: str, secret: str, ttl_seconds: int):
        self.email = email
        self.password = password
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def authenticate(self, email: str, password: str) -> AuthToken:
        if email != self.email or password != self.password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
        payload = {"sub": email, "workspace_id": "demo-workspace", "exp": int(time.time()) + self.ttl_seconds}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        signature = hmac.new(self.secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return AuthToken(access_token=f"{encoded}.{signature}", expires_in_seconds=self.ttl_seconds)

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

