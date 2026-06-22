from typing import Literal

from pydantic import BaseModel, Field


BillingPlan = Literal["plus"]
BillingProvider = Literal[
    "paddle",
    "stripe",
    "google_play",
    "app_store",
]


class BillingCheckoutRequest(BaseModel):
    plan: BillingPlan = "plus"

    # If omitted, backend uses BILLING_PROVIDER env.
    provider: BillingProvider | None = None


class BillingCheckoutResponse(BaseModel):
    provider: str
    plan: str
    checkout_url: str