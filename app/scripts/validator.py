import re
from better_profanity import profanity
from app.util.security import canonicalize_email

RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "api",
    "app",
    "auth",
    "billing",
    "contact",
    "dashboard",
    "help",
    "home",
    "info",
    "login",
    "logout",
    "me",
    "null",
    "privacy",
    "register",
    "root",
    "settings",
    "sidefx",
    "sidefxai",
    "support",
    "system",
    "terms",
    "user",
    "users",
    "www",
}

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

CUSTOM_BLOCKLIST = {
    # Keep this small at first. Add obvious abusive terms you want blocked.
    # You can expand it later as needed.
}

def normalize_username_for_moderation(username: str) -> str:
    value = username.lower().strip()

    # Remove separators so hidden phrases are easier to catch
    value = value.replace("_", "").replace("-", "").replace(".", "")

    # Light leetspeak normalization
    value = (
        value.replace("0", "o")
        .replace("1", "i")
        .replace("3", "e")
        .replace("4", "a")
        .replace("5", "s")
        .replace("7", "t")
    )

    return value

def contains_blocked_username_content(username: str) -> bool:
    normalized = normalize_username_for_moderation(username)

    if profanity.contains_profanity(normalized):
        return True

    return any(term in normalized for term in CUSTOM_BLOCKLIST)

def validate_new_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if len(password) > 128:
        return "Password must be 128 characters or fewer"
    if password.strip() != password:
        return "Password cannot start or end with spaces"
    return None


def validate_username(username: str) -> str | None:
    value = username.strip()

    if len(value) < 4:
        return "Username must be at least 4 characters long"

    if len(value) > 20:
        return "Username must be 20 characters or fewer"

    if " " in value:
        return "Username cannot contain spaces"

    if not USERNAME_PATTERN.fullmatch(value):
        return "Username can only contain letters, numbers, and underscores"

    if value.startswith("_") or value.endswith("_"):
        return "Username cannot start or end with an underscore"

    if "__" in value:
        return "Username cannot contain consecutive underscores"

    if value.lower() in RESERVED_USERNAMES:
        return "That username is not allowed"

    if contains_blocked_username_content(value):
        return "That username is not allowed"

    return None

def validate_new_email(email: str) -> str | None:
    value = canonicalize_email(email)

    if len(value) > 254:
        return "Email must be 254 characters or fewer"

    return None