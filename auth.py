
"""Authentication and password management for AgriTracker."""

import bcrypt
import database as db


def hash_password(password: str) -> str:
    """Convert a plaintext password into a secure bcrypt hash."""
    if not password:
        raise ValueError("Password cannot be empty.")

    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)

    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check whether a password matches its stored bcrypt hash."""
    if not password or not password_hash:
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def authenticate_user(username: str, password: str):
    """
    Authenticate a user against PostgreSQL.

    Returns public user information if successful.
    Returns None if the credentials are invalid or the account is inactive.
    """
    if not username or not password:
        return None

    user = db.fetch_auth_user_by_username(username.strip())

    if user is None:
        return None

    if not user["is_active"]:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    # Do not expose the password hash to the application.
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role"]
    }
