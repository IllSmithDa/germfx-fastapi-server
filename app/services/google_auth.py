from __future__ import annotations

import os
from typing import Optional


def is_google_oauth_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_CLIENT_ID")
        and os.getenv("GOOGLE_CLIENT_SECRET")
        and os.getenv("GOOGLE_REDIRECT_URI")
    )


def build_google_authorization_url(state: Optional[str] = None) -> str:
    if not is_google_oauth_configured():
        raise RuntimeError("Google OAuth is not configured yet.")

    # Placeholder until OAuth library is added.
    # Later, this should generate the real Google consent URL.
    raise NotImplementedError("Google OAuth authorization URL generation is not implemented yet.")


def handle_google_callback(code: Optional[str], state: Optional[str] = None):
    if not is_google_oauth_configured():
        raise RuntimeError("Google OAuth is not configured yet.")

    if not code:
        raise ValueError("Missing Google OAuth code.")

    # Placeholder until token exchange + user lookup/create is implemented.
    raise NotImplementedError("Google OAuth callback handling is not implemented yet.")