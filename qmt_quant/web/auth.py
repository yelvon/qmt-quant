"""Optional Bearer token auth for mutating API routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from qmt_quant.config import get_settings


def require_api_token(request: Request) -> None:
    token = get_settings().web_api_token
    if not token:
        return
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return
    raise HTTPException(status_code=401, detail="invalid_or_missing_api_token")
