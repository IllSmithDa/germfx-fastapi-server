from app.models import User


def user_has_plus(user: User) -> bool:
    subscription = user.subscription

    return (
        subscription
        and subscription.status in ["active", "trialing"]
    )
