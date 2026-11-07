import os
import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join("database", "agricultural_tracker.db")

def get_connection() -> sqlite3.Connection:
    """
    Establishes connection to the SQLite database and enforces Foreign Key constraints.
    """
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes database tables and populates default catalogs and multi-year historical records.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Crops Catalog Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crops (
                crop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL CHECK(category IN (
                    'Grains', 'Vegetables', 'Fruits', 'Root Crops / Tubers', 'Legumes / Pulses'
                )),
                min_growth_days INTEGER NOT NULL CHECK(min_growth_days > 0),
                max_growth_days INTEGER NOT NULL CHECK(max_growth_days >= min_growth_days),
                preferred_sub_season TEXT NOT NULL CHECK(preferred_sub_season IN (
                    'Cool Dry', 'Hot Dry', 'Wet', 'Year-Round'
                ))
            );
        """)

        # 2. Locations Lookup Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_name TEXT UNIQUE NOT NULL,
                field_type TEXT NOT NULL CHECK(field_type IN (
                    'Irrigated Lowland', 'Rainfed Upland', 'Greenhouse/Controlled'
                )),
                area_hectares REAL NOT NULL CHECK(area_hectares > 0)
            );
        """)

        # 3. Production Records Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS production_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                planting_date TEXT NOT NULL,
                target_min_harvest_date TEXT NOT NULL,
                target_max_harvest_date TEXT NOT NULL,
                actual_harvest_date TEXT,
                predicted_yield_kg REAL NOT NULL CHECK(predicted_yield_kg >= 0),
                actual_yield_kg REAL DEFAULT 0.0 CHECK(actual_yield_kg >= 0),
                yield_variance_pct REAL DEFAULT 0.0,
                total_expenses_php REAL DEFAULT 0.0 CHECK(total_expenses_php >= 0),
                status TEXT NOT NULL CHECK(status IN ('In Progress', 'Completed', 'Cancelled')),
                is_historical INTEGER NOT NULL DEFAULT 0 CHECK(is_historical IN (0, 1)),
                FOREIGN KEY (crop_id) REFERENCES crops(crop_id) ON DELETE RESTRICT,
                FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE RESTRICT
            );
        """)

        # 4. Itemized Production Expenses Table ($1:N$ Child Table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS production_expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                expense_category TEXT NOT NULL CHECK(expense_category IN (
                    'Seeds/Seedlings', 'Fertilizer/Soil Inputs', 'Pesticides/Crop Protection', 
                    'Labor/Workforce', 'Fuel/Irrigation/Utilities', 'Equipment/Maintenance', 'Other'
                )),
                description TEXT NOT NULL,
                amount_php REAL NOT NULL CHECK(amount_php > 0),
                date_logged TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES production_records(record_id) ON DELETE CASCADE
            );
        """)

        conn.commit()

    # Seed default baseline data if tables are empty
    _seed_default_catalogs()
    _seed_multi_year_records()

def _seed_default_catalogs():
    """Seeds baseline crops and farm locations into SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Seed Crops Catalog
        cursor.execute("SELECT COUNT(*) FROM crops")
        if cursor.fetchone()[0] == 0:
            default_crops = [
                ("Lowland Rice", "Grains", 100, 120, "Wet"),
                ("Yellow Corn", "Grains", 85, 105, "Hot Dry"),
                ("Tomato", "Vegetables", 60, 80, "Hot Dry"),
                ("Cabbage", "Vegetables", 70, 90, "Cool Dry"),
                ("Bitter Gourd (Ampalaya)", "Vegetables", 60, 80, "Hot Dry"),
                ("Banana (Saba)", "Fruits", 270, 365, "Year-Round"),
                ("Watermelon", "Fruits", 75, 90, "Hot Dry"),
                ("Cassava", "Root Crops / Tubers", 180, 240, "Wet"),
                ("Taro (Gabi)", "Root Crops / Tubers", 150, 210, "Wet"),
                ("Mungbean (Mongo)", "Legumes / Pulses", 55, 70, "Cool Dry")
            ]
            cursor.executemany("""
                INSERT INTO crops (crop_name, category, min_growth_days, max_growth_days, preferred_sub_season)
                VALUES (?, ?, ?, ?, ?)
            """, default_crops)

        # Seed Locations Catalog
        cursor.execute("SELECT COUNT(*) FROM locations")
        if cursor.fetchone()[0] == 0:
            default_locations = [
                ("Barangay San Isidro - Main Paddy", "Irrigated Lowland", 2.50),
                ("Purok 5 - Upper Ridge Parcel", "Rainfed Upland", 1.20),
                ("Highland Nursery Bay 1", "Greenhouse/Controlled", 0.75),
                ("Riverside Field Sector A", "Irrigated Lowland", 3.00),
                ("East Slope Upland Plot", "Rainfed Upland", 1.80)
            ]
            cursor.executemany("""
                INSERT INTO locations (location_name, field_type, area_hectares)
                VALUES (?, ?, ?)
            """, default_locations)

        conn.commit()

def _seed_multi_year_records():
    """Seeds multi-year historical operational records (2024–2026) for testing analytics and pagination."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM production_records")
        if cursor.fetchone()[0] > 0:
            return

        sample_records = [
            # 2024 Harvests
            (1, 1, "2024-06-15", "2024-09-23", "2024-10-13", "2024-10-01", 11200.00, 11800.00, 5.36, 45000.00, "Completed", 1),
            (3, 3, "2024-03-01", "2024-04-30", "2024-05-20", "2024-05-10", 9400.00, 9100.00, -3.19, 28000.00, "Completed", 1),
            (4, 3, "2024-11-10", "2025-01-19", "2025-02-08", "2025-01-25", 8500.00, 8900.00, 4.71, 22000.00, "Completed", 1),
            
            # 2025 Harvests
            (1, 4, "2025-06-01", "2025-09-09", "2025-09-29", "2025-09-18", 13500.00, 14100.00, 4.44, 52000.00, "Completed", 1),
            (2, 2, "2025-03-15", "2025-06-08", "2025-06-28", "2025-06-15", 5800.00, 5400.00, -6.90, 18500.00, "Completed", 1),
            (10, 5, "2025-11-01", "2025-12-26", "2026-01-10", "2026-01-05", 3800.00, 3950.00, 3.95, 14000.00, "Completed", 1),

            # 2026 Active / Recent Harvests
            (3, 3, "2026-03-10", "2026-05-09", "2026-05-29", "2026-05-18", 9200.00, 9500.00, 3.26, 26500.00, "Completed", 0),
            (1, 1, "2026-06-01", "2026-09-09", "2026-09-29", None, 11500.00, 0.0, 0.0, 38000.00, "In Progress", 0)
        ]

        cursor.executemany("""
            INSERT INTO production_records (
                crop_id, location_id, planting_date, target_min_harvest_date, target_max_harvest_date,
                actual_harvest_date, predicted_yield_kg, actual_yield_kg, yield_variance_pct,
                total_expenses_php, status, is_historical
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_records)

        # Seed corresponding itemized expense logs
        sample_expenses = [
            (1, 'Seeds/Seedlings', 'Certified Inbred Rice Seeds', 12000.00, '2024-06-15'),
            (1, 'Fertilizer/Soil Inputs', '14-14-14 & Urea Fertilizer Bags', 23000.00, '2024-07-01'),
            (1, 'Labor/Workforce', 'Transplanting and Harvesting Labor', 10000.00, '2024-10-01'),
            (7, 'Seeds/Seedlings', 'Hybrid Tomato Seedlings', 8500.00, '2026-03-10'),
            (7, 'Fertilizer/Soil Inputs', 'Foliar & Organic Composting', 10000.00, '2026-03-20'),
            (7, 'Labor/Workforce', 'Pruning & Harvesting Crews', 8000.00, '2026-05-18'),
            (8, 'Seeds/Seedlings', 'Palay Seeds (Submariner Variety)', 13000.00, '2026-06-01'),
            (8, 'Fuel/Irrigation/Utilities', 'Irrigation Pump Diesel Fuel', 25000.00, '2026-06-15')
        ]

        cursor.executemany("""
            INSERT INTO production_expenses (record_id, expense_category, description, amount_php, date_logged)
            VALUES (?, ?, ?, ?, ?)
        """, sample_expenses)

        conn.commit()

# --- SQLite Query Helpers (Strict ASC Ordering Enforced) ---

def fetch_all_crops() -> List[Dict[str, Any]]:
    """Retrieves all registered crops sorted by crop_id ASC."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM crops ORDER BY crop_id ASC;")
        return [dict(row) for row in cursor.fetchall()]

def fetch_all_locations() -> List[Dict[str, Any]]:
    """Retrieves all farm locations sorted by location_id ASC."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations ORDER BY location_id ASC;")
        return [dict(row) for row in cursor.fetchall()]

def fetch_joined_records(limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieves operational production records joined with crop and location metadata,
    ordered by record_id ASC. Supports terminal table pagination.
    """
    query = """
        SELECT 
            pr.record_id,
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
            pr.planting_date,
            pr.target_min_harvest_date,
            pr.target_max_harvest_date,
            pr.actual_harvest_date,
            pr.predicted_yield_kg,
            pr.actual_yield_kg,
            pr.yield_variance_pct,
            pr.total_expenses_php,
            pr.status,
            pr.is_historical
        FROM production_records pr
        JOIN crops c ON pr.crop_id = c.crop_id
        JOIN locations l ON pr.location_id = l.location_id
        ORDER BY pr.record_id ASC
    """
    if limit is not None and offset is not None:
        query += f" LIMIT {int(limit)} OFFSET {int(offset)}"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def count_production_records() -> int:
    """Returns total count of production records for pagination math."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM production_records;")
        return cursor.fetchone()[0]

def fetch_expenses_by_record(record_id: int) -> List[Dict[str, Any]]:
    """Fetches itemized expenses linked to a specific production record ordered by expense_id ASC."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM production_expenses 
            WHERE record_id = ? 
            ORDER BY expense_id ASC;
        """, (record_id,))
        return [dict(row) for row in cursor.fetchall()]

def add_itemized_expense(record_id: int, category: str, description: str, amount_php: float, date_logged: str):
    """Logs an expense line-item and automatically updates the record's total_expenses_php sum."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO production_expenses (record_id, expense_category, description, amount_php, date_logged)
            VALUES (?, ?, ?, ?, ?);
        """, (record_id, category, description, amount_php, date_logged))

        # Recalculate and update parent total expenses
        cursor.execute("""
            UPDATE production_records
            SET total_expenses_php = (
                SELECT COALESCE(SUM(amount_php), 0.0)
                FROM production_expenses
                WHERE record_id = ?
            )
            WHERE record_id = ?;
        """, (record_id, record_id))

        conn.commit()
        
def update_itemized_expense(expense_id: int, category: str, description: str, amount_php: float, date_logged: str) -> Optional[int]:
    """
    Updates an itemized expense line item and automatically recalculates 
    the parent record's total_expenses_php. Returns the parent record_id.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT record_id FROM production_expenses WHERE expense_id = ?;", (expense_id,))
        row = cursor.fetchone()
        if not row:
            return None
        record_id = row["record_id"]

        cursor.execute("""
            UPDATE production_expenses
            SET expense_category = ?, description = ?, amount_php = ?, date_logged = ?
            WHERE expense_id = ?;
        """, (category, description, amount_php, date_logged, expense_id))

        # Automatically recalculate parent record total expenses
        cursor.execute("""
            UPDATE production_records
            SET total_expenses_php = (
                SELECT COALESCE(SUM(amount_php), 0.0)
                FROM production_expenses
                WHERE record_id = ?
            )
            WHERE record_id = ?;
        """, (record_id, record_id))

        conn.commit()
        return record_id


def delete_itemized_expense(expense_id: int) -> Optional[int]:
    """
    Deletes an itemized expense line item and automatically recalculates 
    the parent record's total_expenses_php. Returns the parent record_id.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT record_id FROM production_expenses WHERE expense_id = ?;", (expense_id,))
        row = cursor.fetchone()
        if not row:
            return None
        record_id = row["record_id"]

        cursor.execute("DELETE FROM production_expenses WHERE expense_id = ?;", (expense_id,))

        # Automatically recalculate parent record total expenses
        cursor.execute("""
            UPDATE production_records
            SET total_expenses_php = (
                SELECT COALESCE(SUM(amount_php), 0.0)
                FROM production_expenses
                WHERE record_id = ?
            )
            WHERE record_id = ?;
        """, (record_id, record_id))

        conn.commit()
        return record_id