import os
import sqlite3
import random
from datetime import datetime, timedelta
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
    """Populates 500 synthetic records dynamically anchored to the current system date."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM production_records;")
        if cursor.fetchone()[0] > 0:
            return

        cursor.execute("SELECT crop_id, min_growth_days, max_growth_days FROM crops;")
        crops = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT location_id, area_hectares FROM locations;")
        locations = [dict(r) for r in cursor.fetchall()]

        records_to_insert = []
        expenses_to_insert = []

        # DYNAMIC SYSTEM TIME: Automatically grabs today's real-time date
        present_date = datetime.now()

        for i in range(1, 501):
            crop = random.choice(crops)
            loc = random.choice(locations)

            min_days = crop["min_growth_days"]
            max_days = crop["max_growth_days"]

            is_completed = random.random() < 0.90
            status = "Completed" if is_completed else "In Progress"

            if is_completed:
                # Historical: Planted between ~2.5 years ago (900 days) and ~3 months ago (90 days)
                days_ago = random.randint(90, 900)
                plant_dt = present_date - timedelta(days=days_ago)
                
                target_min_dt = plant_dt + timedelta(days=min_days)
                target_max_dt = plant_dt + timedelta(days=max_days)

                actual_harvest_dt = plant_dt + timedelta(days=random.randint(min_days - 3, max_days + 3))
                actual_harvest_str = actual_harvest_dt.strftime("%Y-%m-%d")

                predicted_kg = round(loc["area_hectares"] * random.uniform(3500.0, 6500.0), 2)
                variance_mult = random.uniform(0.88, 1.12)
                actual_kg = round(predicted_kg * variance_mult, 2)
                variance_pct = round(((actual_kg - predicted_kg) / predicted_kg) * 100.0, 2)
            else:
                # ACTIVE IN-PROGRESS: Planted recently (15 to 45 days before TODAY)
                days_ago = random.randint(15, min(45, min_days - 10))
                plant_dt = present_date - timedelta(days=days_ago)

                target_min_dt = plant_dt + timedelta(days=min_days)
                target_max_dt = plant_dt + timedelta(days=max_days)

                actual_harvest_str = None
                predicted_kg = round(loc["area_hectares"] * random.uniform(3500.0, 6500.0), 2)
                actual_kg = 0.0
                variance_pct = 0.0

            plant_str = plant_dt.strftime("%Y-%m-%d")
            records_to_insert.append((
                crop["crop_id"],
                loc["location_id"],
                plant_str,
                target_min_dt.strftime("%Y-%m-%d"),
                target_max_dt.strftime("%Y-%m-%d"),
                actual_harvest_str,
                predicted_kg,
                actual_kg,
                variance_pct,
                0.0,
                status,
                1 if is_completed else 0
            ))

        cursor.executemany("""
            INSERT INTO production_records (
                crop_id, location_id, planting_date, target_min_harvest_date, target_max_harvest_date,
                actual_harvest_date, predicted_yield_kg, actual_yield_kg, yield_variance_pct,
                total_expenses_php, status, is_historical
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, records_to_insert)

        # Seed matching expense receipts for all 500 records
        expense_categories = [
            ('Seeds/Seedlings', 'High-Yield Certified Seeds Batch', 6000.0, 18000.0),
            ('Fertilizer/Soil Inputs', 'Soil Nutrients and Compost Blend', 8000.0, 25000.0),
            ('Labor/Workforce', 'Land Preparation & Planting Labor', 5000.0, 15000.0),
            ('Fuel/Irrigation/Utilities', 'Irrigation Pump Diesel', 3000.0, 10000.0)
        ]

        for rec_id in range(1, 501):
            num_receipts = random.randint(2, 3)
            chosen_cats = random.sample(expense_categories, num_receipts)
            plant_date_str = records_to_insert[rec_id - 1][2]
            
            for cat_name, desc, min_amt, max_amt in chosen_cats:
                amt = round(random.uniform(min_amt, max_amt), 2)
                expenses_to_insert.append((
                    rec_id,
                    cat_name,
                    desc,
                    amt,
                    plant_date_str
                ))

        cursor.executemany("""
            INSERT INTO production_expenses (record_id, expense_category, description, amount_php, date_logged)
            VALUES (?, ?, ?, ?, ?);
        """, expenses_to_insert)

        # Synchronize total cumulative expenses across parent records
        cursor.execute("""
            UPDATE production_records
            SET total_expenses_php = (
                SELECT COALESCE(SUM(amount_php), 0.0)
                FROM production_expenses
                WHERE production_expenses.record_id = production_records.record_id
            );
        """)

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

def fetch_joined_records(order_by: str = "record_id", order_dir: str = "ASC") -> List[Dict[str, Any]]:
    """
    Retrieves production records joined with crop and location metadata.
    Supports dynamic field sorting (default: record_id ASC).
    """
    allowed_sort_fields = {
        "record_id": "p.record_id",
        "crop_name": "c.crop_name",
        "location_name": "l.location_name",
        "planting_date": "p.planting_date",
        "actual_yield_kg": "p.actual_yield_kg",
        "total_expenses_php": "p.total_expenses_php",
        "status": "p.status"
    }

    sort_column = allowed_sort_fields.get(order_by, "p.record_id")
    sort_direction = "DESC" if order_dir.upper() == "DESC" else "ASC"

    query = f"""
        SELECT 
            p.record_id,
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
            p.planting_date,
            p.target_min_harvest_date,
            p.target_max_harvest_date,
            p.actual_harvest_date,
            p.predicted_yield_kg,
            p.actual_yield_kg,
            p.yield_variance_pct,
            p.total_expenses_php,
            p.status,
            p.is_historical
        FROM production_records p
        JOIN crops c ON p.crop_id = c.crop_id
        JOIN locations l ON p.location_id = l.location_id
        ORDER BY {sort_column} {sort_direction};
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

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