"""PostgreSQL database layer for Agricultural Tracker.

Uses DATABASE_URL from .env. Keep the old SQLite database as a backup;
this module connects only to PostgreSQL.
"""
import os
from typing import List, Dict, Any, Optional, Tuple

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import ForeignKeyViolation
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


def fetch_joined_records(order_by: str = "record_id", order_dir: str = "ASC") -> List[Dict[str, Any]]:
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
    query = f"""
        SELECT
            p.record_id, c.crop_id, c.crop_name, c.category,
            c.min_growth_days, c.max_growth_days, c.preferred_sub_season,
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
        ORDER BY {sort_column} {sort_direction}
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()


def fetch_joined_record_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    query = """
        SELECT
            p.record_id, c.crop_id, c.crop_name, c.category,
            c.min_growth_days, c.max_growth_days, c.preferred_sub_season,
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
        WHERE p.record_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (record_id,))
            return cur.fetchone()


def count_production_records() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM production_records")
            return cur.fetchone()["count"]


def fetch_expenses_by_record(record_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT expense_id, record_id, expense_category, description,
                       amount_php, date_logged::text AS date_logged
                FROM production_expenses
                WHERE record_id = %s
                ORDER BY expense_id ASC
            """, (record_id,))
            return cur.fetchall()


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


def add_itemized_expense(record_id: int, category: str, description: str,
                         amount_php: float, date_logged: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO production_expenses
                    (record_id, expense_category, description, amount_php, date_logged)
                VALUES (%s, %s, %s, %s, %s)
            """, (record_id, category, description, amount_php, date_logged))
        _refresh_record_expenses_total(conn, record_id)


def update_itemized_expense(expense_id: int, category: str, description: str,
                            amount_php: float, date_logged: str) -> Optional[int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT record_id FROM production_expenses WHERE expense_id = %s",
                (expense_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            record_id = row["record_id"]
            cur.execute("""
                UPDATE production_expenses
                SET expense_category = %s, description = %s,
                    amount_php = %s, date_logged = %s
                WHERE expense_id = %s
            """, (category, description, amount_php, date_logged, expense_id))
        _refresh_record_expenses_total(conn, record_id)
        return record_id


def delete_itemized_expense(expense_id: int) -> Optional[int]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT record_id FROM production_expenses WHERE expense_id = %s",
                (expense_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            record_id = row["record_id"]
            cur.execute("DELETE FROM production_expenses WHERE expense_id = %s", (expense_id,))
        _refresh_record_expenses_total(conn, record_id)
        return record_id


def update_production_record(record_id: int, crop_id: int, location_id: int,
                             planting_date_str: str, target_min: str,
                             target_max: str, predicted_yield_kg: float) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE production_records
                SET crop_id = %s, location_id = %s, planting_date = %s,
                    target_min_harvest_date = %s, target_max_harvest_date = %s,
                    predicted_yield_kg = %s
                WHERE record_id = %s
            """, (crop_id, location_id, planting_date_str, target_min, target_max,
                  predicted_yield_kg, record_id))
            return cur.rowcount > 0


def delete_production_record(record_id: int) -> bool:
    """Delete a production record; its itemized expenses cascade automatically."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM production_records WHERE record_id = %s", (record_id,))
            return cur.rowcount > 0


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
