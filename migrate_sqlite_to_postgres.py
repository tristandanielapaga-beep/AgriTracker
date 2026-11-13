"""
One-time migration from the project's SQLite database to PostgreSQL.

Run from the project root:
    python migrate_sqlite_to_postgres.py

The script expects:
    database/agricultural_tracker.db
and PostgreSQL connection settings in a .env file.
It refuses to import into non-empty PostgreSQL tables.
"""
import os
import sqlite3
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
SQLITE_PATH = ROOT / "database" / "agricultural_tracker.db"
SCHEMA_PATH = ROOT / "postgres_schema.sql"

TABLES = {
    "crops": """
        INSERT INTO crops
        (crop_id, crop_name, category, min_growth_days, max_growth_days, preferred_sub_season)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
    "locations": """
        INSERT INTO locations
        (location_id, location_name, field_type, area_hectares)
        VALUES (%s, %s, %s, %s)
    """,
    "production_records": """
        INSERT INTO production_records
        (record_id, crop_id, location_id, planting_date, target_min_harvest_date,
         target_max_harvest_date, actual_harvest_date, predicted_yield_kg,
         actual_yield_kg, yield_variance_pct, total_expenses_php, status, is_historical)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
    "production_expenses": """
        INSERT INTO production_expenses
        (expense_id, record_id, expense_category, description, amount_php, date_logged)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
}

COLUMNS = {
    "crops": "crop_id, crop_name, category, min_growth_days, max_growth_days, preferred_sub_season",
    "locations": "location_id, location_name, field_type, area_hectares",
    "production_records": """record_id, crop_id, location_id, planting_date, target_min_harvest_date,
        target_max_harvest_date, actual_harvest_date, predicted_yield_kg, actual_yield_kg,
        yield_variance_pct, total_expenses_php, status, is_historical""",
    "production_expenses": "expense_id, record_id, expense_category, description, amount_php, date_logged",
}

def main():
    load_dotenv(ROOT / ".env")

    if not SQLITE_PATH.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {SQLITE_PATH}\n"
            "Run the existing application once to initialize it, or update SQLITE_PATH."
        )

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is missing. Add it to your .env file.")

    with sqlite3.connect(SQLITE_PATH) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        source = {
            table: [tuple(row) for row in sqlite_conn.execute(
                f"SELECT {COLUMNS[table]} FROM {table} ORDER BY 1"
            ).fetchall()]
            for table in TABLES
        }

    print("Source SQLite row counts:")
    for table, rows in source.items():
        print(f"  {table}: {len(rows)}")

    with psycopg.connect(dsn) as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM crops),
                    (SELECT COUNT(*) FROM locations),
                    (SELECT COUNT(*) FROM production_records),
                    (SELECT COUNT(*) FROM production_expenses)
            """)
            existing = cur.fetchone()
            if any(existing):
                raise RuntimeError(
                    "The PostgreSQL tables are not empty. Migration stopped to avoid "
                    "mixing or duplicating data. Use a fresh agri_tracker database."
                )

            # Parent tables first, then dependent tables.
            for table in ("crops", "locations", "production_records", "production_expenses"):
                rows = source[table]
                if rows:
                    cur.executemany(TABLES[table], rows)
                print(f"Imported {len(rows)} rows into {table}.")

            # Ensure future auto-generated IDs continue after the imported IDs.
            for table, id_column in (
                ("crops", "crop_id"),
                ("locations", "location_id"),
                ("production_records", "record_id"),
                ("production_expenses", "expense_id"),
            ):
                cur.execute(
                    f"""SELECT setval(
                        pg_get_serial_sequence(%s, %s),
                        GREATEST(COALESCE((SELECT MAX({id_column}) FROM {table}), 1), 1),
                        EXISTS (SELECT 1 FROM {table})
                    )""",
                    (table, id_column),
                )

    print("\nMigration completed successfully.")
    print("Your original SQLite database was not changed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nMigration failed: {exc}")
        sys.exit(1)
