AGRICULTURAL TRACKER - POSTGRESQL SETUP

WHAT THIS PACKAGE DOES
- Creates PostgreSQL versions of the four tables currently defined in database.py.
- Migrates existing SQLite rows into PostgreSQL while preserving primary-key IDs.
- Leaves the original SQLite database untouched.
- Stops if the destination PostgreSQL tables already contain data.

BEFORE RUNNING
1. In pgAdmin, confirm the agri_tracker database exists and your server is connected.
2. Copy .env.example to .env in your project root.
3. Replace YOUR_POSTGRES_PASSWORD with your PostgreSQL password.
   Do not share or upload your .env file.
4. Install the extra dependencies:
      pip install -r requirements-postgres.txt
5. Make sure your SQLite database exists at:
      database/agricultural_tracker.db

RUN
From the project root:
    python migrate_sqlite_to_postgres.py

IMPORTANT
- This is a migration step, not yet a replacement for database.py.
- Do not delete the SQLite database.
- Do not manually create the same tables in pgAdmin before running the script.
- If the migration reports that PostgreSQL tables are not empty, stop and inspect
  the database rather than dropping tables blindly.
- The next development step is to replace SQLite-specific queries in the app
  with PostgreSQL queries and test all existing workflows.
