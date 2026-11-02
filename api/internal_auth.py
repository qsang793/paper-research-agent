from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Header, HTTPException


def require_internal_api_token(
    provided_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    expected_token = os.getenv("BACKEND_INTERNAL_TOKEN")
    is_production = os.getenv("APP_ENV", "development").lower() == "production"

    if not expected_token:
        if is_production:
            raise HTTPException(status_code=503, detail="Internal API authentication is not configured")
        return

    if not provided_token or not hmac.compare_digest(
        provided_token.encode(), expected_token.encode()
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
