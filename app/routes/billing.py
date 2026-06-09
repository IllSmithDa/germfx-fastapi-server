# app/routes/billing.py

from http.client import HTTPException
from urllib.request import Request

import stripe

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_authenticated_user
from app.db.session import get_db
from app.models import User

router = APIRouter(tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/create-checkout-session")
def create_checkout_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    session = stripe.checkout.Session.create(
        mode="subscription",

        payment_method_types=["card"],

        line_items=[
            {
                "price": settings.STRIPE_PLUS_PRICE_ID,
                "quantity": 1,
            }
        ],

        success_url=f"{settings.HOST_URL}/billing/success",
        cancel_url=f"{settings.HOST_URL}/pricing",

        customer_email=current_user.email,

        metadata={
            "user_id": current_user.id,
        },
    )

    return {
        "checkout_url": session.url,
    }

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()

    signature = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )

    except Exception:
        raise HTTPException(status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        user_id = int(session["metadata"]["user_id"])

        stripe_customer_id = session["customer"]
        stripe_subscription_id = session["subscription"]

        # activate subscription here

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]

        # downgrade to free here

    return {"received": True}