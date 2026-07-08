import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


EMAIL_TOKEN_MAX_AGE = int(os.getenv("EMAIL_TOKEN_MAX_AGE", "3600"))  # 1 hour
PASSWORD_RESET_TOKEN_MAX_AGE = int(
    os.getenv("PASSWORD_RESET_TOKEN_MAX_AGE", "3600")
)  # 1 hour
EMAIL_CHANGE_TOKEN_MAX_AGE = int(
    os.getenv("EMAIL_CHANGE_TOKEN_MAX_AGE", "3600")
)  # 1 hour

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

EMAIL_SECURITY_SALT = os.getenv("SECURITY_SALT", "email-verify-salt")
PASSWORD_RESET_SALT = os.getenv("PASSWORD_RESET_SALT", "password-reset-salt")
EMAIL_CHANGE_SALT = os.getenv("EMAIL_CHANGE_SALT", "email-change-salt")

_email_serializer = URLSafeTimedSerializer(
    secret_key=SECRET_KEY,
    salt=EMAIL_SECURITY_SALT,
)

_password_reset_serializer = URLSafeTimedSerializer(
    secret_key=SECRET_KEY,
    salt=PASSWORD_RESET_SALT,
)

_email_change_serializer = URLSafeTimedSerializer(
    secret_key=SECRET_KEY,
    salt=EMAIL_CHANGE_SALT,
)


def generate_email_token(user_id: int, email: str) -> str:
    """Create a signed, timestamped token for account email verification."""
    return _email_serializer.dumps(
        {
            "uid": user_id,
            "email": email,
            "purpose": "email_verify",
        }
    )


def verify_email_token(token: str) -> dict:
    """Return payload if valid, else raise ValueError."""
    try:
        payload = _email_serializer.loads(token, max_age=EMAIL_TOKEN_MAX_AGE)

        if payload.get("purpose") != "email_verify":
            raise ValueError("Invalid token")

        return payload

    except SignatureExpired as e:
        raise ValueError("Token expired") from e

    except BadSignature as e:
        raise ValueError("Invalid token") from e


def generate_password_reset_token(user_id: int, email: str) -> str:
    """Create a signed, timestamped token for password reset."""
    return _password_reset_serializer.dumps(
        {
            "uid": user_id,
            "email": email,
            "purpose": "password_reset",
        }
    )


def verify_password_reset_token(token: str) -> dict:
    """Return payload if valid, else raise ValueError."""
    try:
        payload = _password_reset_serializer.loads(
            token,
            max_age=PASSWORD_RESET_TOKEN_MAX_AGE,
        )

        if payload.get("purpose") != "password_reset":
            raise ValueError("Invalid token")

        return payload

    except SignatureExpired as e:
        raise ValueError("Token expired") from e

    except BadSignature as e:
        raise ValueError("Invalid token") from e


def generate_email_change_token(
    *,
    user_id: int,
    current_email_hash: str,
    new_email: str,
) -> str:
    """
    Create a signed, timestamped token for confirming an email change.

    current_email_hash is included so old email-change links become invalid
    after the user's email has already changed.
    """
    return _email_change_serializer.dumps(
        {
            "uid": user_id,
            "current_email_hash": current_email_hash,
            "new_email": new_email,
            "purpose": "email_change",
        }
    )


def verify_email_change_token(token: str) -> dict:
    """Return payload if valid, else raise ValueError."""
    try:
        payload = _email_change_serializer.loads(
            token,
            max_age=EMAIL_CHANGE_TOKEN_MAX_AGE,
        )

        if payload.get("purpose") != "email_change":
            raise ValueError("Invalid token")

        if not payload.get("uid"):
            raise ValueError("Invalid token")

        if not payload.get("current_email_hash"):
            raise ValueError("Invalid token")

        if not payload.get("new_email"):
            raise ValueError("Invalid token")

        return payload

    except SignatureExpired as e:
        raise ValueError("Token expired") from e

    except BadSignature as e:
        raise ValueError("Invalid token") from e