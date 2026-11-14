"""PostgreSQL database layer for Agricultural Tracker.

Uses DATABASE_URL from .env. Keep the old SQLite database as a backup;
this module connects only to PostgreSQL.
"""
import os
from decimal import Decimal
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import ForeignKeyViolation, UniqueViolation
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
    """Check that all migrated PostgreSQL tables are present; never reseed."""
    required = (
        "crops", "locations", "production_records", "production_expenses",
        "users", "audit_log", "crop_requests", "location_requests",
    )
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


# ---------------------------------------------------------------------------
# Shared authorization and audit helpers
# ---------------------------------------------------------------------------

def _get_active_user_role(conn, user_id: int) -> str:
    """Return an active user's role or reject the operation."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT role, is_active FROM users WHERE user_id = %s",
            (user_id,),
        )
        user = cur.fetchone()
    if user is None or not user["is_active"]:
        raise PermissionError("User account does not exist or is inactive.")
    return user["role"]


def _require_admin(conn, user_id: int) -> None:
    if _get_active_user_role(conn, user_id) != "admin":
        raise PermissionError("Only administrators can perform this operation.")


def _json_safe(value):
    """Convert common PostgreSQL/Python values into JSON-serializable values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (Decimal,)):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def log_action(
    conn,
    user_id: Optional[int],
    action: str,
    target_table: str,
    target_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an audit entry in the caller's transaction."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_log (user_id, action, target_table, target_id, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, action, target_table, target_id, Jsonb(_json_safe(details or {}))),
        )


# ---------------------------------------------------------------------------
# Public catalog reads
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Production-record reads (scoped to the signed-in user)
# ---------------------------------------------------------------------------

_RECORD_SELECT = """
    SELECT
        p.record_id, p.created_by,
        c.crop_id, c.crop_name, c.category, c.min_growth_days,
        c.max_growth_days, c.preferred_sub_season,
        l.location_id, l.location_name, l.field_type, l.area_hectares,
        p.planting_date::text AS planting_date,
        p.target_min_harvest_date::text AS target_min_harvest_date,
        p.target_max_harvest_date::text AS target_max_harvest_date,
        p.actual_harvest_date::text AS actual_harvest_date,
        p.predicted_yield_kg, p.actual_yield_kg, p.yield_variance_pct,
        p.total_expenses_php, p.status, p.is_historical
    FROM production_records p
    JOIN crops c ON p.crop_id = c.crop_id
    JOIN locations l ON p.location_id = l.location_id
"""


def fetch_joined_records(
    user_id: int,
    order_by: str = "record_id",
    order_dir: str = "ASC",
) -> List[Dict[str, Any]]:
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
        query = (
            _RECORD_SELECT
            + " WHERE (%s = 'admin' OR p.created_by = %s)"
            + f" ORDER BY {sort_column} {sort_direction}"
        )
        with conn.cursor() as cur:
            cur.execute(query, (role, user_id))
            return cur.fetchall()


def fetch_joined_record_by_id(record_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)
        with conn.cursor() as cur:
            cur.execute(
                _RECORD_SELECT
                + """
                WHERE p.record_id = %s
                  AND (%s = 'admin' OR p.created_by = %s)
                """,
                (record_id, role, user_id),
            )
            return cur.fetchone()


def count_production_records(user_id: int) -> int:
    """Count all records for admins, or only the caller's records for staff."""
    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM production_records
                WHERE (%s = 'admin' OR created_by = %s)
                """,
                (role, user_id),
            )
            return cur.fetchone()["count"]


def fetch_expenses_by_record(record_id: int, user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        role = _get_active_user_role(conn, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.expense_id, e.record_id, e.created_by,
                       e.expense_category, e.description, e.amount_php,
                       e.date_logged::text AS date_logged
                FROM production_expenses e
                JOIN production_records p ON e.record_id = p.record_id
                WHERE p.record_id = %s
                  AND (%s = 'admin' OR p.created_by = %s)
                ORDER BY e.expense_id ASC
                """,
                (record_id, role, user_id),
            )
            return cur.fetchall()


def _authorize_record_access(conn, record_id: int, user_id: int) -> Dict[str, Any]:
    """Lock a record and authorize changes by admins or its owning staff member."""
    role = _get_active_user_role(conn, user_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT created_by, status
            FROM production_records
            WHERE record_id = %s
            FOR UPDATE
            """,
            (record_id,),
        )
        record = cur.fetchone()

    if record is None:
        raise ValueError("Production record not found.")
    if role == "staff":
        if record["created_by"] != user_id:
            raise PermissionError("You can only modify records you created.")
        if record["status"] != "In Progress":
            raise PermissionError("Staff can only modify records that are In Progress.")
    return record


def _refresh_record_expenses_total(conn, record_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE production_records
            SET total_expenses_php = (
                SELECT COALESCE(SUM(amount_php), 0)
                FROM production_expenses
                WHERE record_id = %s
            )
            WHERE record_id = %s
            """,
            (record_id, record_id),
        )


# ---------------------------------------------------------------------------
# Itemized expenses
# ---------------------------------------------------------------------------

def add_itemized_expense(
    record_id: int, category: str, description: str,
    amount_php: float, date_logged: str, user_id: int,
) -> int:
    with get_connection() as conn:
        _authorize_record_access(conn, record_id, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO production_expenses
                    (record_id, expense_category, description, amount_php, date_logged, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING expense_id
                """,
                (record_id, category, description, amount_php, date_logged, user_id),
            )
            expense_id = cur.fetchone()["expense_id"]
        _refresh_record_expenses_total(conn, record_id)
        log_action(conn, user_id, "ADD_EXPENSE", "production_expenses", expense_id, {
            "record_id": record_id, "category": category,
            "description": description, "amount_php": float(amount_php),
        })
        return expense_id


def update_itemized_expense(
    expense_id: int, category: str, description: str,
    amount_php: float, date_logged: str, user_id: int,
) -> Optional[int]:
    with get_connection() as conn:
        # Read parent ID first, then lock the parent before modifying the child.
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record_id, expense_category, description, amount_php
                FROM production_expenses WHERE expense_id = %s
                """,
                (expense_id,),
            )
            expense = cur.fetchone()
        if expense is None:
            return None

        record_id = expense["record_id"]
        _authorize_record_access(conn, record_id, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT expense_id FROM production_expenses
                WHERE expense_id = %s AND record_id = %s
                FOR UPDATE
                """,
                (expense_id, record_id),
            )
            if cur.fetchone() is None:
                return None
            cur.execute(
                """
                UPDATE production_expenses
                SET expense_category = %s, description = %s,
                    amount_php = %s, date_logged = %s
                WHERE expense_id = %s
                """,
                (category, description, amount_php, date_logged, expense_id),
            )
        _refresh_record_expenses_total(conn, record_id)
        log_action(conn, user_id, "UPDATE_EXPENSE", "production_expenses", expense_id, {
            "record_id": record_id,
            "old_category": expense["expense_category"], "new_category": category,
            "old_description": expense["description"], "new_description": description,
            "old_amount_php": float(expense["amount_php"]), "new_amount_php": float(amount_php),
        })
        return record_id


def delete_itemized_expense(expense_id: int, user_id: int) -> Optional[int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT record_id, expense_category, description, amount_php
                FROM production_expenses WHERE expense_id = %s
                """,
                (expense_id,),
            )
            expense = cur.fetchone()
        if expense is None:
            return None

        record_id = expense["record_id"]
        _authorize_record_access(conn, record_id, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM production_expenses
                WHERE expense_id = %s AND record_id = %s
                """,
                (expense_id, record_id),
            )
        _refresh_record_expenses_total(conn, record_id)
        log_action(conn, user_id, "DELETE_EXPENSE", "production_expenses", expense_id, {
            "record_id": record_id, "category": expense["expense_category"],
            "description": expense["description"], "amount_php": float(expense["amount_php"]),
        })
        return record_id


# ---------------------------------------------------------------------------
# Production-record updates and deletion
# ---------------------------------------------------------------------------

def update_production_record(
    record_id: int, crop_id: int, location_id: int,
    planting_date_str: str, target_min: str, target_max: str,
    predicted_yield_kg: float, user_id: int,
) -> bool:
    with get_connection() as conn:
        _authorize_record_access(conn, record_id, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT crop_id, location_id, planting_date::text AS planting_date,
                       target_min_harvest_date::text AS target_min,
                       target_max_harvest_date::text AS target_max,
                       predicted_yield_kg
                FROM production_records WHERE record_id = %s
                """,
                (record_id,),
            )
            old = cur.fetchone()
            cur.execute(
                """
                UPDATE production_records
                SET crop_id = %s, location_id = %s, planting_date = %s,
                    target_min_harvest_date = %s, target_max_harvest_date = %s,
                    predicted_yield_kg = %s
                WHERE record_id = %s
                """,
                (crop_id, location_id, planting_date_str, target_min, target_max,
                 predicted_yield_kg, record_id),
            )
            updated = cur.rowcount > 0
        if updated:
            log_action(conn, user_id, "UPDATE_PRODUCTION_RECORD", "production_records",
                       record_id, {
                "old_values": _json_safe(old),
                "new_values": {
                    "crop_id": crop_id, "location_id": location_id,
                    "planting_date": planting_date_str, "target_min": target_min,
                    "target_max": target_max,
                    "predicted_yield_kg": float(predicted_yield_kg),
                },
            })
        return updated


def delete_production_record(record_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        _require_admin(conn, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT crop_id, location_id, status, created_by
                FROM production_records WHERE record_id = %s FOR UPDATE
                """,
                (record_id,),
            )
            record = cur.fetchone()
            if record is None:
                return False
            cur.execute("DELETE FROM production_records WHERE record_id = %s", (record_id,))
        log_action(conn, user_id, "DELETE_PRODUCTION_RECORD", "production_records",
                   record_id, _json_safe(record))
        return True


# ---------------------------------------------------------------------------
# Crop and location catalog management (admin-only)
# ---------------------------------------------------------------------------

def add_crop_catalog_item(
    crop_name: str, category: str, min_growth_days: int,
    max_growth_days: int, preferred_sub_season: str, performed_by: int,
) -> int:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO crops (crop_name, category, min_growth_days,
                                   max_growth_days, preferred_sub_season)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING crop_id
                """,
                (crop_name, category, min_growth_days, max_growth_days, preferred_sub_season),
            )
            new_id = cur.fetchone()["crop_id"]
        log_action(conn, performed_by, "ADD_CROP_CATALOG_ITEM", "crops", new_id,
                   {"crop_name": crop_name, "category": category})
        return new_id


def add_location_catalog_item(
    location_name: str, field_type: str, area_hectares: float, performed_by: int,
) -> int:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO locations (location_name, field_type, area_hectares)
                VALUES (%s, %s, %s)
                RETURNING location_id
                """,
                (location_name, field_type, area_hectares),
            )
            new_id = cur.fetchone()["location_id"]
        log_action(conn, performed_by, "ADD_LOCATION_CATALOG_ITEM", "locations", new_id,
                   {"location_name": location_name, "field_type": field_type,
                    "area_hectares": float(area_hectares)})
        return new_id


def delete_crop_catalog_item(crop_id: int, performed_by: int) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            _require_admin(conn, performed_by)
            with conn.cursor() as cur:
                cur.execute("SELECT crop_name FROM crops WHERE crop_id = %s FOR UPDATE", (crop_id,))
                crop = cur.fetchone()
                if crop is None:
                    return False, f"Crop ID #{crop_id} not found."
                cur.execute("DELETE FROM crops WHERE crop_id = %s", (crop_id,))
            log_action(conn, performed_by, "DELETE_CROP_CATALOG_ITEM", "crops", crop_id,
                       {"crop_name": crop["crop_name"]})
        return True, f"Crop ID #{crop_id} deleted successfully."
    except ForeignKeyViolation:
        return False, f"Cannot delete Crop ID #{crop_id} because production records reference it."


def delete_location_catalog_item(location_id: int, performed_by: int) -> Tuple[bool, str]:
    try:
        with get_connection() as conn:
            _require_admin(conn, performed_by)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT location_name FROM locations WHERE location_id = %s FOR UPDATE",
                    (location_id,),
                )
                location = cur.fetchone()
                if location is None:
                    return False, f"Location ID #{location_id} not found."
                cur.execute("DELETE FROM locations WHERE location_id = %s", (location_id,))
            log_action(conn, performed_by, "DELETE_LOCATION_CATALOG_ITEM", "locations",
                       location_id, {"location_name": location["location_name"]})
        return True, f"Location ID #{location_id} deleted successfully."
    except ForeignKeyViolation:
        return False, f"Cannot delete Location ID #{location_id} because production records reference it."


# ---------------------------------------------------------------------------
# User management and authentication
# --------------------------------------------------------------------------------------

def create_user(
    username: str, password_hash: str, full_name: str,
    role: str, created_by: Optional[int] = None,
) -> int:
    """Bootstrap the first account only; later account creation is admin-only."""
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
        if created_by is None:
            # Bootstrap exception: only permit this when the users table is empty.
            with conn.cursor() as cur:
                cur.execute("SELECT EXISTS (SELECT 1 FROM users) AS any_users")
                if cur.fetchone()["any_users"]:
                    raise PermissionError(
                        "An acting administrator is required to create additional accounts."
                    )
        else:
            _require_admin(conn, created_by)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password_hash, full_name, role, created_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING user_id
                """,
                (username, password_hash, full_name, role, created_by),
            )
            new_id = cur.fetchone()["user_id"]
        log_action(conn, created_by, "CREATE_USER", "users", new_id,
                   {"username": username, "full_name": full_name, "role": role})
        return new_id


def fetch_auth_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Authentication-only lookup. Never display the returned password hash."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, password_hash, full_name, role, is_active
                FROM users WHERE username = %s
                """,
                (username.strip(),),
            )
            return cur.fetchone()


def fetch_user_by_id(user_id: int, performed_by: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, full_name, role, is_active, created_at, created_by
                FROM users WHERE user_id = %s
                """,
                (user_id,),
            )
            return cur.fetchone()


def fetch_all_users(performed_by: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, full_name, role, is_active, created_at, created_by
                FROM users ORDER BY user_id ASC
                """
            )
            return cur.fetchall()


def set_user_active_status(
    target_user_id: int, is_active: bool, performed_by: int,
) -> bool:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, role, is_active
                FROM users WHERE user_id = %s FOR UPDATE
                """,
                (target_user_id,),
            )
            user = cur.fetchone()
            if user is None:
                return False

            if target_user_id == performed_by and not is_active:
                raise ValueError("You cannot deactivate your own account while signed in.")

            if not is_active and user["role"] == "admin" and user["is_active"]:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = TRUE"
                )
                if cur.fetchone()["n"] <= 1:
                    raise ValueError("Cannot deactivate the last active administrator.")

            cur.execute(
                "UPDATE users SET is_active = %s WHERE user_id = %s",
                (bool(is_active), target_user_id),
            )
        log_action(conn, performed_by,
                   "ACTIVATE_USER" if is_active else "DEACTIVATE_USER",
                   "users", target_user_id, {"username": user["username"]})
        return True


# ---------------------------------------------------------------------------
# Audit-log retrieval (admin-only)
# ---------------------------------------------------------------------------

def fetch_audit_logs(
    performed_by: int, limit: int = 100, filter_user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 1000))
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            query = """
                SELECT a.log_id, a.user_id, u.username, a.action,
                       a.target_table, a.target_id, a.details, a.created_at
                FROM audit_log a
                LEFT JOIN users u ON a.user_id = u.user_id
            """
            if filter_user_id is not None:
                query += " WHERE a.user_id = %s"
                params = (filter_user_id, safe_limit)
            else:
                params = (safe_limit,)
            query += " ORDER BY a.created_at DESC, a.log_id DESC LIMIT %s"
            cur.execute(query, params)
            return cur.fetchall()


# ---------------------------------------------------------------------------
# Staff-submitted catalog requests and administrator review
# ---------------------------------------------------------------------------

def submit_crop_request(
    requested_by: int, crop_name: str, category: str,
    min_growth_days: int, max_growth_days: int, preferred_sub_season: str,
) -> int:
    with get_connection() as conn:
        _get_active_user_role(conn, requested_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO crop_requests
                    (requested_by, crop_name, category, min_growth_days,
                     max_growth_days, preferred_sub_season)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING request_id
                """,
                (requested_by, crop_name, category, min_growth_days,
                 max_growth_days, preferred_sub_season),
            )
            request_id = cur.fetchone()["request_id"]
        log_action(conn, requested_by, "SUBMIT_CROP_REQUEST", "crop_requests",
                   request_id, {"crop_name": crop_name, "category": category})
        return request_id


def submit_location_request(
    requested_by: int, location_name: str, field_type: str, area_hectares: float,
) -> int:
    with get_connection() as conn:
        _get_active_user_role(conn, requested_by)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO location_requests
                    (requested_by, location_name, field_type, area_hectares)
                VALUES (%s, %s, %s, %s)
                RETURNING request_id
                """,
                (requested_by, location_name, field_type, area_hectares),
            )
            request_id = cur.fetchone()["request_id"]
        log_action(conn, requested_by, "SUBMIT_LOCATION_REQUEST", "location_requests",
                   request_id, {"location_name": location_name, "field_type": field_type})
        return request_id


def fetch_crop_requests(performed_by: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            if status is None:
                cur.execute("SELECT * FROM crop_requests ORDER BY created_at DESC, request_id DESC")
            else:
                cur.execute(
                    """
                    SELECT * FROM crop_requests
                    WHERE status = %s ORDER BY created_at DESC, request_id DESC
                    """,
                    (status,),
                )
            return cur.fetchall()


def fetch_location_requests(performed_by: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        _require_admin(conn, performed_by)
        with conn.cursor() as cur:
            if status is None:
                cur.execute(
                    "SELECT * FROM location_requests ORDER BY created_at DESC, request_id DESC"
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM location_requests
                    WHERE status = %s ORDER BY created_at DESC, request_id DESC
                    """,
                    (status,),
                )
            return cur.fetchall()


def review_crop_request(
    request_id: int, reviewed_by: int, decision: str,
    rejection_reason: Optional[str] = None,
) -> bool:
    decision = decision.strip().capitalize()
    if decision not in ("Approved", "Rejected"):
        raise ValueError("Decision must be Approved or Rejected.")
    if decision == "Rejected" and not (rejection_reason or "").strip():
        raise ValueError("A rejection reason is required.")

    with get_connection() as conn:
        _require_admin(conn, reviewed_by)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM crop_requests WHERE request_id = %s FOR UPDATE",
                (request_id,),
            )
            request = cur.fetchone()
            if request is None:
                return False
            if request["status"] != "Pending":
                raise ValueError("This crop request has already been reviewed.")

            approved_crop_id = None
            if decision == "Approved":
                cur.execute(
                    """
                    INSERT INTO crops
                        (crop_name, category, min_growth_days, max_growth_days, preferred_sub_season)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING crop_id
                    """,
                    (request["crop_name"], request["category"], request["min_growth_days"],
                     request["max_growth_days"], request["preferred_sub_season"]),
                )
                approved_crop_id = cur.fetchone()["crop_id"]

            cur.execute(
                """
                UPDATE crop_requests
                SET status = %s, reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP,
                    rejection_reason = %s
                WHERE request_id = %s
                """,
                (decision, reviewed_by,
                 rejection_reason.strip() if decision == "Rejected" else None,
                 request_id),
            )
        log_action(conn, reviewed_by, f"{decision.upper()}_CROP_REQUEST",
                   "crop_requests", request_id, {"approved_crop_id": approved_crop_id,
                   "rejection_reason": rejection_reason})
        return True


def review_location_request(
    request_id: int, reviewed_by: int, decision: str,
    rejection_reason: Optional[str] = None,
) -> bool:
    decision = decision.strip().capitalize()
    if decision not in ("Approved", "Rejected"):
        raise ValueError("Decision must be Approved or Rejected.")
    if decision == "Rejected" and not (rejection_reason or "").strip():
        raise ValueError("A rejection reason is required.")

    with get_connection() as conn:
        _require_admin(conn, reviewed_by)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM location_requests WHERE request_id = %s FOR UPDATE",
                (request_id,),
            )
            request = cur.fetchone()
            if request is None:
                return False
            if request["status"] != "Pending":
                raise ValueError("This location request has already been reviewed.")

            approved_location_id = None
            if decision == "Approved":
                cur.execute(
                    """
                    INSERT INTO locations (location_name, field_type, area_hectares)
                    VALUES (%s, %s, %s)
                    RETURNING location_id
                    """,
                    (request["location_name"], request["field_type"], request["area_hectares"]),
                )
                approved_location_id = cur.fetchone()["location_id"]

            cur.execute(
                """
                UPDATE location_requests
                SET status = %s, reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP,
                    rejection_reason = %s
                WHERE request_id = %s
                """,
                (decision, reviewed_by,
                 rejection_reason.strip() if decision == "Rejected" else None,
                 request_id),
            )
        log_action(conn, reviewed_by, f"{decision.upper()}_LOCATION_REQUEST",
                   "location_requests", request_id,
                   {"approved_location_id": approved_location_id,
                    "rejection_reason": rejection_reason})
        return True
