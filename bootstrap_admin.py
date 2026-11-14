
"""One-time initial administrator setup for AgriTracker."""

from getpass import getpass

import psycopg
import database_backup as db
import auth


def main():
    print("=== AgriTracker Initial Administrator Setup ===")

    # Check whether an administrator already exists.
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1
                    FROM users
                    WHERE role = 'admin'
                ) AS admin_exists
            """)
            admin_exists = cur.fetchone()["admin_exists"]

    if admin_exists:
        print("An administrator account already exists.")
        print("Initial setup is no longer available.")
        return

    username = input("Administrator username: ").strip()
    full_name = input("Administrator full name: ").strip()

    if not username or not full_name:
        print("Username and full name are required.")
        return

    password = getpass("Administrator password: ")
    confirm_password = getpass("Confirm password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    if len(password.encode("utf-8")) > 72:
        print("Password must not exceed 72 UTF-8 bytes.")
        return

    try:
        password_hash = auth.hash_password(password)

        user_id = db.create_user(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            role="admin",
            created_by=None
        )

        print("\nAdministrator account created successfully.")
        print(f"User ID: {user_id}")
        print(f"Username: {username}")

    except psycopg.errors.UniqueViolation:
        print("That username is already registered.")

    except (ValueError, psycopg.Error) as error:
        print(f"Administrator creation failed: {error}")


if __name__ == "__main__":
    main()
