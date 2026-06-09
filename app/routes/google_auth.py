from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.services.google_auth import (
    build_google_authorization_url,
    handle_google_callback,
    is_google_oauth_configured,
)

router = APIRouter(prefix="", tags=["google-auth"])


@router.get("/status")
def google_auth_status():
    return {
        "enabled": is_google_oauth_configured(),
        "provider": "google",
    }


@router.get("/login")
def google_login():
    if not is_google_oauth_configured():
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={
                "detail": "Google OAuth is not configured yet.",
                "provider": "google",
                "enabled": False,
            },
        )

    try:
        auth_url = build_google_authorization_url()
        return RedirectResponse(auth_url)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc


@router.get("/callback")
def google_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google OAuth error: {error}",
        )

    if not is_google_oauth_configured():
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={
                "detail": "Google OAuth callback is not configured yet.",
                "provider": "google",
                "enabled": False,
            },
        )

    try:
        return handle_google_callback(code=code, state=state)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc