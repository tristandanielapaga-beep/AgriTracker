import sqlite3
import os

# Define database directory and file path
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "agricultural_tracker.db")

def get_connection():
    """Establish and return a connection to the SQLite database.
    
    Creates the database directory if it does not exist and enables
    foreign key constraints.
    """
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    conn = sqlite3.connect(DB_PATH)
    # Enable Foreign Key support in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dictionary-like objects for easier column access
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """Create relational tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: Crop Types (Lookup Table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crops (
            crop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            typical_growth_days INTEGER NOT NULL CHECK (typical_growth_days > 0)
        );
    """)

    # Table 2: Production Records (Transaction Table)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_id INTEGER NOT NULL,
            farm_location TEXT NOT NULL,
            area_hectares REAL NOT NULL CHECK (area_hectares > 0),
            planting_date TEXT NOT NULL,  -- Format: YYYY-MM-DD
            harvest_date TEXT,           -- Format: YYYY-MM-DD (NULL if unharvested)
            harvest_qty_kg REAL DEFAULT 0.0 CHECK (harvest_qty_kg >= 0),
            production_cost REAL NOT NULL CHECK (production_cost >= 0),
            FOREIGN KEY (crop_id) REFERENCES crops (crop_id) ON DELETE RESTRICT
        );
    """)

    conn.commit()
    conn.close()


def seed_sample_data():
    """Populate database with realistic baseline data for testing."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM crops;")
    if cursor.fetchone()[0] == 0:
        # Seed Crops
        crops_data = [
            ("Rice (Inbred)", "Grains", 115),
            ("Yellow Corn", "Grains", 105),
            ("Tomato", "Vegetables", 75),
            ("Eggplant", "Vegetables", 85),
            ("Banana (Lakatan)", "Fruits", 365)
        ]
        cursor.executemany(
            "INSERT INTO crops (crop_name, category, typical_growth_days) VALUES (?, ?, ?);",
            crops_data
        )

        # Seed Production Records
        records_data = [
            (1, "Field Alpha - North", 2.5, "2026-01-15", "2026-05-10", 11250.0, 45000.0),
            (2, "Field Beta - East", 1.8, "2026-02-01", "2026-05-18", 7800.0, 32000.0),
            (3, "Greenhouse 1", 0.5, "2026-03-10", "2026-05-25", 2100.0, 15500.0),
            (4, "Plot Gamma", 1.0, "2026-04-01", None, 0.0, 18000.0),  # Ongoing crop
            (1, "Field Alpha - South", 3.0, "2026-05-01", None, 0.0, 52000.0)   # Ongoing crop
        ]
        cursor.executemany(
            """INSERT INTO production_records 
               (crop_id, farm_location, area_hectares, planting_date, harvest_date, harvest_qty_kg, production_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?);""",
            records_data
        )

        conn.commit()
        print("Database seeded with sample records successfully.")
    else:
        print("Database already contains data. Skipping seeding.")

    conn.close()


# --- SQL CRUD OPERATIONS ---

def fetch_all_crops():
    """Retrieve all stored crops sorted by name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crops ORDER BY crop_name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_joined_records():
    """Retrieve production records combined with crop lookup details."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            p.record_id,
            c.crop_name,
            c.category,
            p.farm_location,
            p.area_hectares,
            p.planting_date,
            COALESCE(p.harvest_date, 'In Progress') AS harvest_status,
            p.harvest_qty_kg,
            p.production_cost
        FROM production_records p
        JOIN crops c ON p.crop_id = c.crop_id
        ORDER BY p.record_id DESC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def insert_production_record(crop_id, location, area, planting_date, harvest_date, harvest_qty, cost):
    """Insert a new validated production record using parameterized queries."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO production_records 
           (crop_id, farm_location, area_hectares, planting_date, harvest_date, harvest_qty_kg, production_cost)
           VALUES (?, ?, ?, ?, ?, ?, ?);""",
        (crop_id, location, area, planting_date, harvest_date, harvest_qty, cost)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def delete_record_by_id(record_id):
    """Delete a record by ID after CLI user confirmation."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM production_records WHERE record_id = ?;", (record_id,))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


if __name__ == "__main__":
    # Setup test run when running database.py directly
    print("Initializing Agricultural Tracker Database...")
    initialize_database()
    seed_sample_data()
    print(f"Database location: {os.path.abspath(DB_PATH)}")