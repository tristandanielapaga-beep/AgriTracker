"""PostgreSQL database layer for Agricultural Tracker.

Uses DATABASE_URL from .env. Keep the old SQLite database as a backup;
this module connects only to PostgreSQL.
"""
import os
from typing import List, Dict, Any, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import ForeignKeyViolation
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Create a .env file beside Main.py "
        "and set DATABASE_URL=postgresql://..."
    )


def get_connection():
    """Open a PostgreSQL connection with dictionary-style query results."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    """Check that the migrated PostgreSQL tables are present; never reseed data."""
    required = ("crops", "locations", "production_records", "production_expenses")
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in required:
                cur.execute("SELECT to_regclass(%s) AS table_name", (f"public.{table}",))
                if cur.fetchone()["table_name"] is None:
                    raise RuntimeError(
                        f"PostgreSQL table '{table}' is missing. "
                        "Run the migration script before starting the application."
                    )
    print("[+] Connected to PostgreSQL. Existing migrated data is ready.")


def fetch_all_crops() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crops ORDER BY crop_id ASC")
            return cur.fetchall()


def fetch_all_locations() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM locations ORDER BY location_id ASC")
            return cur.fetchall()
        
def _get_active_user_role(conn, user_id: int) -> str:
    """Verifies that the acting account exists and is active."""

    with conn.cursor() as cur:
        cur.execute("""
            SELECT role, is_active
            FROM users
            WHERE user_id = %s
        """, (user_id,))

        user = cur.fetchone()

    if user is None or not user["is_active"]:
        raise PermissionError("User account does not exist or is inactive.")

    return user["role"]


def fetch_joined_records(
    user_id: int,
    order_by: str = "record_id",
    order_dir: str = "ASC"
) -> List[Dict[str, Any]]:
    """
    Retrieves production records.
    Administrators see all records.
    Staff see only records they created.
    """

    allowed = {
        "record_id": "p.record_id",
        "crop_name": "c.crop_name",
        "location_name": "l.location_name",
        "planting_date": "p.planting_date",
        "actual_yield_kg": "p.actual_yield_kg",
        "total_expenses_php": "p.total_expenses_php",
        "status": "p.status",
    }

    sort_column = allowed.get(order_by, "p.record_id")
    sort_direction = "DESC" if str(order_dir).upper() == "DESC" else "ASC"

    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)

        query = f"""
            SELECT
                p.record_id,
                p.created_by,
                c.crop_id,
                c.crop_name,
                c.category,
                c.min_growth_days,
                c.max_growth_days,
                c.preferred_sub_season,
                l.location_id,
                l.location_name,
                l.field_type,
                l.area_hectares,
                p.planting_date::text AS planting_date,
                p.target_min_harvest_date::text AS target_min_harvest_date,
                p.target_max_harvest_date::text AS target_max_harvest_date,
                p.actual_harvest_date::text AS actual_harvest_date,
                p.predicted_yield_kg,
                p.actual_yield_kg,
                p.yield_variance_pct,
                p.total_expenses_php,
                p.status,
                p.is_historical
            FROM production_records p
            JOIN crops c ON p.crop_id = c.crop_id
            JOIN locations l ON p.location_id = l.location_id
            WHERE (%s = 'admin' OR p.created_by = %s)
            ORDER BY {sort_column} {sort_direction}
        """

        with conn.cursor() as cur:
            cur.execute(query, (role, user_id))
            return cur.fetchall()


def fetch_joined_record_by_id(
    record_id: int,
    user_id: int
) -> Optional[Dict[str, Any]]:
    """
    Retrieves one production record.
    Staff cannot retrieve another user's record.
    """

    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.record_id,
                    p.created_by,
                    c.crop_id,
                    c.crop_name,
                    c.category,
                    c.min_growth_days,
                    c.max_growth_days,
                    c.preferred_sub_season,
                    l.location_id,
                    l.location_name,
                    l.field_type,
                    l.area_hectares,
                    p.planting_date::text AS planting_date,
                    p.target_min_harvest_date::text AS target_min_harvest_date,
                    p.target_max_harvest_date::text AS target_max_harvest_date,
                    p.actual_harvest_date::text AS actual_harvest_date,
                    p.predicted_yield_kg,
                    p.actual_yield_kg,
                    p.yield_variance_pct,
                    p.total_expenses_php,
                    p.status,
                    p.is_historical
                FROM production_records p
                JOIN crops c ON p.crop_id = c.crop_id
                JOIN locations l ON p.location_id = l.location_id
                WHERE p.record_id = %s
                  AND (%s = 'admin' OR p.created_by = %s)
            """, (record_id, role, user_id))

            return cur.fetchone()


def count_production_records() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM production_records")
            return cur.fetchone()["count"]


def fetch_expenses_by_record(
    record_id: int,
    user_id: int
) -> List[Dict[str, Any]]:
    """
    Retrieves expenses only if the user can access the parent record.
    """

    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.expense_id,
                    e.record_id,
                    e.created_by,
                    e.expense_category,
                    e.description,
                    e.amount_php,
                    e.date_logged::text AS date_logged
                FROM production_expenses e
                JOIN production_records p
                    ON e.record_id = p.record_id
                WHERE p.record_id = %s
                  AND (%s = 'admin' OR p.created_by = %s)
                ORDER BY e.expense_id ASC
            """, (record_id, role, user_id))

            return cur.fetchall()


def _authorize_record_access(
    conn,
    record_id: int,
    user_id: int
) -> Dict[str, Any]:
    """
    Verifies that the user can access and modify a production record.

    Admins can manage all records.
    Staff can manage only their own In Progress records.
    """

    role = _get_active_user_role(conn, user_id)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT created_by, status
            FROM production_records
            WHERE record_id = %s
            FOR UPDATE
        """, (record_id,))

        record = cur.fetchone()

    if record is None:
        raise ValueError("Production record not found.")

    if role == "staff":
        if record["created_by"] != user_id:
            raise PermissionError(
                "You can only manage expenses on your own records."
            )

        if record["status"] != "In Progress":
            raise PermissionError(
                "Expenses can only be modified while your record is In Progress."
            )

    return record

def _refresh_record_expenses_total(conn, record_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE production_records
            SET total_expenses_php = (
                SELECT COALESCE(SUM(amount_php), 0)
                FROM production_expenses
                WHERE record_id = %s
            )
            WHERE record_id = %s
        """, (record_id, record_id))


def add_itemized_expense(
    record_id: int,
    category: str,
    description: str,
    amount_php: float,
    date_logged: str,
    user_id: int
) -> int:

    with get_connection() as conn:
        _authorize_record_access(conn, record_id, user_id)

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO production_expenses (
                    record_id,
                    expense_category,
                    description,
                    amount_php,
                    date_logged,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING expense_id
            """, (
                record_id,
                category,
                description,
                amount_php,
                date_logged,
                user_id
            ))

            expense_id = cur.fetchone()["expense_id"]

        _refresh_record_expenses_total(conn, record_id)

        log_action(
            conn,
            user_id,
            "ADD_EXPENSE",
            "production_expenses",
            expense_id,
            {
                "record_id": record_id,
                "category": category,
                "description": description,
                "amount_php": float(amount_php)
            }
        )

        return expense_id


def update_itemized_expense(
    expense_id: int,
    category: str,
    description: str,
    amount_php: float,
    date_logged: str,
    user_id: int
) -> Optional[int]:

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    record_id,
                    expense_category,
                    description,
                    amount_php
                FROM production_expenses
                WHERE expense_id = %s
                FOR UPDATE
            """, (expense_id,))

            expense = cur.fetchone()

        if expense is None:
            return None

        record_id = expense["record_id"]

        _authorize_record_access(conn, record_id, user_id)

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE production_expenses
                SET
                    expense_category = %s,
                    description = %s,
                    amount_php = %s,
                    date_logged = %s
                WHERE expense_id = %s
            """, (
                category,
                description,
                amount_php,
                date_logged,
                expense_id
            ))

        _refresh_record_expenses_total(conn, record_id)

        log_action(
            conn,
            user_id,
            "UPDATE_EXPENSE",
            "production_expenses",
            expense_id,
            {
                "record_id": record_id,
                "old_category": expense["expense_category"],
                "new_category": category,
                "old_description": expense["description"],
                "new_description": description,
                "old_amount_php": float(expense["amount_php"]),
                "new_amount_php": float(amount_php)
            }
        )

        return record_id


def delete_itemized_expense(
    expense_id: int,
    user_id: int
) -> Optional[int]:

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    record_id,
                    expense_category,
                    description,
                    amount_php
                FROM production_expenses
                WHERE expense_id = %s
                FOR UPDATE
            """, (expense_id,))

            expense = cur.fetchone()

        if expense is None:
            return None

        record_id = expense["record_id"]

        _authorize_record_access(conn, record_id, user_id)

        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM production_expenses
                WHERE expense_id = %s
            """, (expense_id,))

        _refresh_record_expenses_total(conn, record_id)

        log_action(
            conn,
            user_id,
            "DELETE_EXPENSE",
            "production_expenses",
            expense_id,
            {
                "record_id": record_id,
                "category": expense["expense_category"],
                "description": expense["description"],
                "amount_php": float(expense["amount_php"])
            }
        )

        return record_id


def update_production_record(
    record_id: int,
    crop_id: int,
    location_id: int,
    planting_date_str: str,
    target_min: str,
    target_max: str,
    predicted_yield_kg: float,
    user_id: int
) -> bool:

    with get_connection() as conn:
        _authorize_record_access(conn, record_id, user_id)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    crop_id,
                    location_id,
                    planting_date::text AS planting_date,
                    target_min_harvest_date::text AS target_min,
                    target_max_harvest_date::text AS target_max,
                    predicted_yield_kg
                FROM production_records
                WHERE record_id = %s
            """, (record_id,))

            old_record = cur.fetchone()

            cur.execute("""
                UPDATE production_records
                SET
                    crop_id = %s,
                    location_id = %s,
                    planting_date = %s,
                    target_min_harvest_date = %s,
                    target_max_harvest_date = %s,
                    predicted_yield_kg = %s
                WHERE record_id = %s
            """, (
                crop_id,
                location_id,
                planting_date_str,
                target_min,
                target_max,
                predicted_yield_kg,
                record_id
            ))

            updated = cur.rowcount > 0

        if updated:
            log_action(
                conn,
                user_id,
                "UPDATE_PRODUCTION_RECORD",
                "production_records",
                record_id,
                {
                    "old_values": old_record,
                    "new_values": {
                        "crop_id": crop_id,
                        "location_id": location_id,
                        "planting_date": planting_date_str,
                        "target_min": target_min,
                        "target_max": target_max,
                        "predicted_yield_kg": float(predicted_yield_kg)
                    }
                }
            )

        return updated


def delete_production_record(record_id: int, user_id: int) -> bool:
    """
    Deletes a production record.
    Admin-only operation.
    Associated expenses are deleted through ON DELETE CASCADE.
    """

    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)

        if role != "admin":
            raise PermissionError(
                "Only administrators can delete production records."
            )

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    crop_id,
                    location_id,
                    status,
                    created_by
                FROM production_records
                WHERE record_id = %s
                FOR UPDATE
            """, (record_id,))

            record = cur.fetchone()

            if record is None:
                return False

            cur.execute("""
                DELETE FROM production_records
                WHERE record_id = %s
            """, (record_id,))

        log_action(
            conn,
            user_id,
            "DELETE_PRODUCTION_RECORD",
            "production_records",
            record_id,
            {
                "crop_id": record["crop_id"],
                "location_id": record["location_id"],
                "status": record["status"],
                "original_created_by": record["created_by"]
            }
        )

        return True


def delete_crop_catalog_item(crop_id: int) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM crops WHERE crop_id = %s", (crop_id,))
                if cur.rowcount == 0:
                    return False, f"Crop ID #{crop_id} not found."
        return True, f"Crop ID #{crop_id} deleted successfully."
    except ForeignKeyViolation:
        return False, f"Cannot delete Crop ID #{crop_id} because production records reference it."


def delete_location_catalog_item(location_id: int) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM locations WHERE location_id = %s", (location_id,))
                if cur.rowcount == 0:
                    return False, f"Location ID #{location_id} not found."
        return True, f"Location ID #{location_id} deleted successfully."
    except ForeignKeyViolation:
        return False, f"Cannot delete Location ID #{location_id} because production records reference it."


# ============================================================
# PHASE 2: USER MANAGEMENT AND AUTHENTICATION DATABASE LAYER
# ============================================================

def create_user(
    username: str,
    password_hash: str,
    full_name: str,
    role: str,
    created_by: Optional[int] = None
) -> int:
    """
    Creates an admin or staff account.
    Passwords must already be hashed before reaching this function.
    Returns the new user ID.
    """
    username = username.strip()
    full_name = full_name.strip()
    role = role.strip().lower()

    if not username or not full_name:
        raise ValueError("Username and full name are required.")

    if role not in ("admin", "staff"):
        raise ValueError("Role must be 'admin' or 'staff'.")

    if not password_hash:
        raise ValueError("Password hash cannot be empty.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (
                    username, password_hash, full_name, role, created_by
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING user_id
            """, (username, password_hash, full_name, role, created_by))

            user_id = cur.fetchone()["user_id"]

            log_action(
                conn,
                user_id=created_by,
                action="CREATE_USER",
                target_table="users",
                target_id=user_id,
                details={
                    "username": username,
                    "full_name": full_name,
                    "role": role
                }
            )

            return user_id


def fetch_auth_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves account information required for password verification.
    Includes password_hash; never display or expose this result to users.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, password_hash,
                       full_name, role, is_active
                FROM users
                WHERE username = %s
            """, (username.strip(),))

            return cur.fetchone()


def fetch_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves public account information without password hashes."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, full_name, role,
                       is_active, created_at, created_by
                FROM users
                WHERE user_id = %s
            """, (user_id,))

            return cur.fetchone()


def fetch_all_users() -> List[Dict[str, Any]]:
    """Retrieves all user accounts without exposing password hashes."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, full_name, role,
                       is_active, created_at, created_by
                FROM users
                ORDER BY user_id ASC
            """)

            return cur.fetchall()


def set_user_active_status(
    target_user_id: int,
    is_active: bool,
    performed_by: int
) -> bool:
    """
    Activates or deactivates an account.
    Prevents deactivation of the last active administrator.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, username, role, is_active
                FROM users
                WHERE user_id = %s
                FOR UPDATE
            """, (target_user_id,))

            user = cur.fetchone()

            if user is None:
                return False

            if not is_active and user["role"] == "admin" and user["is_active"]:
                cur.execute("""
                    SELECT COUNT(*) AS admin_count
                    FROM users
                    WHERE role = 'admin' AND is_active = TRUE
                """)

                if cur.fetchone()["admin_count"] <= 1:
                    raise ValueError(
                        "Cannot deactivate the last active administrator."
                    )

            cur.execute("""
                UPDATE users
                SET is_active = %s
                WHERE user_id = %s
            """, (is_active, target_user_id))

            log_action(
                conn,
                user_id=performed_by,
                action="ACTIVATE_USER" if is_active else "DEACTIVATE_USER",
                target_table="users",
                target_id=target_user_id,
                details={"username": user["username"]}
            )

            return cur.rowcount > 0


# ============================================================
# PHASE 2: AUDIT LOGGING
# ============================================================

def log_action(
    conn,
    user_id: Optional[int],
    action: str,
    target_table: str,
    target_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Writes an audit entry using an existing database connection.

    Passing the connection allows the audit entry and the operation
    being recorded to commit or roll back together.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO audit_log (
                user_id, action, target_table, target_id, details
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id,
            action,
            target_table,
            target_id,
            Jsonb(details or {})
        ))


def fetch_audit_logs(
    limit: int = 100,
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Retrieves recent audit entries, optionally filtered by user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute("""
                    SELECT
                        a.log_id,
                        a.user_id,
                        u.username,
                        a.action,
                        a.target_table,
                        a.target_id,
                        a.details,
                        a.created_at
                    FROM audit_log a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    WHERE a.user_id = %s
                    ORDER BY a.created_at DESC, a.log_id DESC
                    LIMIT %s
                """, (user_id, limit))
            else:
                cur.execute("""
                    SELECT
                        a.log_id,
                        a.user_id,
                        u.username,
                        a.action,
                        a.target_table,
                        a.target_id,
                        a.details,
                        a.created_at
                    FROM audit_log a
                    LEFT JOIN users u ON a.user_id = u.user_id
                    ORDER BY a.created_at DESC, a.log_id DESC
                    LIMIT %s
                """, (limit,))

            return cur.fetchall()
