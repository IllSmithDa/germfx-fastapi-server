import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

EMAIL_TOKEN_MAX_AGE = int(os.getenv("EMAIL_TOKEN_MAX_AGE", "3600"))  # 1 hour
PASSWORD_RESET_TOKEN_MAX_AGE = int(os.getenv("PASSWORD_RESET_TOKEN_MAX_AGE", "3600"))  # 1 hour

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
EMAIL_SECURITY_SALT = os.getenv("SECURITY_SALT", "email-verify-salt")
PASSWORD_RESET_SALT = os.getenv("PASSWORD_RESET_SALT", "password-reset-salt")

_email_serializer = URLSafeTimedSerializer(secret_key=SECRET_KEY, salt=EMAIL_SECURITY_SALT)
_password_reset_serializer = URLSafeTimedSerializer(secret_key=SECRET_KEY, salt=PASSWORD_RESET_SALT)


def generate_email_token(user_id: int, email: str) -> str:
    """Create a signed, timestamped token for email verification."""
    return _email_serializer.dumps({
        "uid": user_id,
        "email": email,
        "purpose": "email_verify",
    })


def verify_email_token(token: str) -> dict:
    """Return payload if valid, else raise."""
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
    return _password_reset_serializer.dumps({
        "uid": user_id,
        "email": email,
        "purpose": "password_reset",
    })


def verify_password_reset_token(token: str) -> dict:
    """Return payload if valid, else raise."""
    try:
        payload = _password_reset_serializer.loads(
            token, max_age=PASSWORD_RESET_TOKEN_MAX_AGE
        )
        if payload.get("purpose") != "password_reset":
            raise ValueError("Invalid token")
        return payload
    except SignatureExpired as e:
        raise ValueError("Token expired") from e
    except BadSignature as e:
        raise ValueError("Invalid token") from e