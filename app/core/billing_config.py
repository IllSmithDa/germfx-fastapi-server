# app/core/billing_config.py

import os


BILLING_PROVIDER = os.getenv(
    "BILLING_PROVIDER",
    "paddle",
)

HOST_URL = os.getenv(
    "HOST_URL",
    "http://localhost:3000",
)

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost:8000",
)


# Paddle
PADDLE_ENVIRONMENT = os.getenv(
    "PADDLE_ENVIRONMENT",
    "sandbox",
)

PADDLE_API_KEY = os.getenv(
    "PADDLE_API_KEY",
)

PADDLE_PLUS_PRICE_ID = os.getenv(
    "PADDLE_PLUS_PRICE_ID",
)

PADDLE_CHECKOUT_URL = os.getenv(
    "PADDLE_CHECKOUT_URL",
    f"{HOST_URL.rstrip('/')}/billing/success",
)

PADDLE_WEBHOOK_SECRET = os.getenv(
    "PADDLE_WEBHOOK_SECRET",
)

PADDLE_WEBHOOK_TOLERANCE_SECONDS = int(
    os.getenv(
        "PADDLE_WEBHOOK_TOLERANCE_SECONDS",
        "300",
    )
)