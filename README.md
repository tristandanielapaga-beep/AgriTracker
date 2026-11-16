# AgriTracker

**Agricultural Production Tracker & Yield Prediction System**  
DSA 214 – Data Science and Analytics Project | Scenario 3

AgriTracker is a Python command-line application for managing agricultural production operations. It stores crop and farm-location information, records planting and harvest activity, tracks itemized production expenses, estimates crop yield with a machine-learning model, and provides analytics and monitoring reports.

> **Current release:** This repository contains the CLI version of AgriTracker. It does not include a graphical/web interface. The application connects to a shared PostgreSQL database hosted on Neon.

---

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Running AgriTracker](#running-agritracker)
- [Using the Application](#using-the-application)
- [Shared Database and Multiple Devices](#shared-database-and-multiple-devices)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)
- [Project Team](#project-team)

---

## Features

### Production Management
- Register new planting operations.
- View production records in a paginated ledger.
- Search, filter, sort, and inspect production records.
- Edit planting information.
- Record harvest dates and actual harvest yields.
- Delete production records.

### Expense Tracking
- Record itemized expenses for a production operation.
- Categorize expenses such as seeds, fertilizer, labor, utilities, equipment, and other costs.
- Add, edit, and delete expense line items.

### Crop and Location Catalog
- View available crop varieties and farm locations.
- Allow staff to submit crop and location requests.
- Allow administrators to review and approve or reject requests.
- Allow administrators to register crop varieties and farm locations.

### Machine-Learning Yield Prediction
- Estimate crop yield in kilograms when a planting operation is created.
- Uses a Random Forest regression pipeline with crop, field, area, budget, planting-month, and seasonal-overlap inputs.
- The model training data is generated locally when the expected training CSV is absent.

**Important:** Model predictions are estimates. They should not be treated as guaranteed harvest outcomes or as proof of real-world predictive accuracy. The repository includes synthetic training data generation.

### Analytics and Monitoring
- Filter analytics by planting year, crop category, crop, location, record creator, and production status.
- View an executive KPI report.
- Generate up to seven analytical charts.
- View a model monitoring report comparing stored predicted and actual yields.

### Accounts, Roles, and Audit Logs
- Login-based access.
- Administrator and staff roles with different menus and permissions.
- Administrators can create staff accounts and activate or deactivate accounts.
- Important actions are recorded in the audit log.

---

## Technology Stack

- **Python** – application runtime
- **PostgreSQL** – relational database
- **Neon** – hosted PostgreSQL database used by the shared demonstration environment
- **Psycopg 3** – PostgreSQL connectivity
- **Pandas and NumPy** – data handling and numerical calculations
- **Scikit-learn** – Random Forest yield prediction pipeline
- **Matplotlib** – analytical chart generation
- **bcrypt** – password hashing
- **python-dotenv** – loading database configuration from `.env`

---

## Requirements

Before installing the application, make sure you have:

1. Python 3.10 or later installed.
2. Git installed (if cloning the repository).
3. Internet access to connect to the shared Neon database.
4. A valid AgriTracker application account provided by the project administrator.
5. The database connection string supplied privately by the project administrator.

You do **not** need to install PostgreSQL locally, create a Neon project, or restore the database backup to run the application. The demonstration database is hosted remotely.

Check that Python and pip are available:

```bash
python --version
python -m pip --version
```

On some systems, use `py` instead of `python`.

---

## Getting Started

### 1. Download or clone the repository

Using Git:

```bash
git clone <REPOSITORY-URL>
cd <REPOSITORY-FOLDER>
```

Replace the placeholders with the actual GitHub repository URL and folder name.

Alternatively, download the repository as a ZIP file from GitHub, extract it, and open a terminal in the extracted project folder.

### 2. Create a virtual environment (recommended)

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt:

```bat
.venv\Scripts\activate.bat
```

A virtual environment keeps this project's Python packages separate from other Python projects.

### 3. Install dependencies

From the project root, run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The `requirements.txt` file must include the PostgreSQL, environment-variable, authentication, data-science, and charting dependencies used by the current PostgreSQL version of the application.

---

## Configuration

AgriTracker reads its PostgreSQL connection string from an environment file named `.env`, located in the same folder as `Main.py`.

### 1. Create your `.env` file

Copy `.env.example` and name the copy `.env`.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

If you are using Command Prompt:

```bat
copy .env.example .env
```

### 2. Set the database connection string

Open `.env` in a text editor. Set `DATABASE_URL` to the Neon PostgreSQL connection string provided privately by the project administrator.

It should follow this general format:

```dotenv
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOSTNAME/DATABASE?sslmode=require
```

Use the actual connection string supplied for your account. Do not copy the example placeholders literally.

**Use the application connection string for the `agri_groupmate` database role (or the specific restricted role assigned to you), not the database owner's credentials.**

Do not:
- Commit `.env` to Git.
- Upload `.env` to GitHub.
- Send your connection string or password in screenshots, chat messages, or public issue reports.
- Put the connection string directly into Python source code.

The `.env` file is already excluded by the repository's `.gitignore` when that ignore rule is respected.

---

## Running AgriTracker

Make sure your virtual environment is active, your `.env` file is configured, and your computer has internet access.

Start the application from the project root:

```bash
python Main.py
```

On startup, AgriTracker checks that it can connect to PostgreSQL and that the required database tables exist. If the check succeeds, the login screen appears.

The application does **not** automatically recreate or reseed the existing Neon database during normal startup.

Log in using the username and password provided to you by the project administrator.

---

## Using the Application

AgriTracker displays different menu options depending on the role assigned to the logged-in account.

### Staff Menu

Staff users can:

1. View their own production ledger.
2. Log a new planting operation.
3. Edit their own in-progress production records.
4. Log harvest output.
5. Manage expenses for their production records.
6. Submit a crop request.
7. Submit a farm-location request.
8. Log out.
9. Exit the system.

### Administrator Menu

Administrators have the staff functions, along with administrative options to:

- View all production records.
- Register crop varieties and farm locations.
- Delete production records.
- Create staff accounts and activate or deactivate accounts.
- Review crop and location requests.
- View audit logs.
- Open executive analytics and charts.

### Working with the Production Ledger

The ledger supports navigation and record management controls. Depending on the screen, the application may provide options such as:

- **Next / Previous** – move between pages.
- **Jump Page** – go to a selected page.
- **Sort** – change the sort field and direction.
- **Filter / Search** – narrow the displayed records using a keyword.
- **Inspect** – view details for a selected production record.
- **Back** – return to the previous menu.

Follow the prompts shown in the terminal. Dates should be entered in `YYYY-MM-DD` format when requested. Enter numerical values without currency symbols unless the prompt explicitly says otherwise.

### Executive Analytics

Administrators can open **Executive Analytics and Charts** to:

1. Apply filters for year, crop category, crop, location, record creator, or status.
2. View the executive KPI report.
3. Generate the analytical charts.
4. View the model monitoring report.

Generated chart images are saved by the application in its chart output directory when generation succeeds.

---

## Shared Database and Multiple Devices

The demonstration setup uses one shared Neon PostgreSQL database.

This means multiple authorized computers can run their own copy of AgriTracker while connecting to the same cloud database.

For a two-device demonstration:

1. Connect both computers to the internet.
2. Install the repository and dependencies on both computers.
3. Configure each computer's own `.env` file using its assigned database connection string.
4. Start AgriTracker on both computers.
5. Log in using the assigned application accounts.
6. Create or update a record on one computer.
7. Navigate back to the relevant list or open the workflow again on the other computer to retrieve the latest records.

The application reads from the shared database when its workflows retrieve records. Changes saved to Neon can therefore be seen by the other connected device when it fetches the records again.

**Internet access is required.** If the connection is unavailable, the application cannot communicate with the hosted database.

---

## Project Structure

Important files in the repository:

| File | Purpose |
|---|---|
| `Main.py` | Main CLI application, login flow, and user menus |
| `database.py` | PostgreSQL connection, queries, and database operations |
| `auth.py` | User authentication and password verification |
| `functions.py` | Production workflows, validation, and utility functions |
| `ml_model.py` | Random Forest yield prediction pipeline |
| `generate_synthetic_data.py` | Generates synthetic model training data |
| `analytics.py` | KPI calculations, analytics reports, and chart generation |
| `monitoring.py` | Model monitoring calculations and report |
| `evaluate_model.py` | Model evaluation script |
| `postgres_schema.sql` | PostgreSQL table definitions |
| `requirements.txt` | Python package dependencies |
| `.env.example` | Example environment-variable file; contains placeholders only |
| `.gitignore` | Files and folders Git should ignore |

Other backup and migration scripts may be present in the repository. They are not part of the normal startup procedure.

---

## Troubleshooting

### `DATABASE_URL is missing`

- Confirm that the file is named exactly `.env`.
- Confirm that `.env` is in the same directory as `Main.py`.
- Confirm that it contains a `DATABASE_URL=...` entry.
- Make sure you did not save it as `.env.txt`.

### Database connection or timeout error

- Check that your computer is connected to the internet.
- Confirm that the connection string was copied correctly.
- Confirm that the database role and password are valid.
- Ask the project administrator to verify that the Neon database is available and that your role has the required permissions.

Do not post your connection string or password when asking for help.

### `ModuleNotFoundError`

Activate the project's virtual environment and run:

```bash
python -m pip install -r requirements.txt
```

If the error continues, confirm that the same Python interpreter is being used to install packages and run `Main.py`.

### Required database table is missing

AgriTracker checks for the required PostgreSQL tables during startup. If a table is missing, stop and contact the project administrator. Do not run migration or restore scripts against the shared database unless the administrator specifically instructs you to do so.

### Login is unsuccessful

- Check the username and password.
- Confirm that the account has been created and is active.
- Contact the project administrator if the credentials need to be reset or the account needs to be activated.

---

## Security Notes

- Never commit `.env` or share database passwords.
- Use only the database role assigned to you.
- Do not use the Neon owner account for routine application access.
- Do not run database migration, restore, or destructive SQL commands during the demonstration.
- Treat production records and account information as private project data.
- The SQL backup and local database files are not required by a new user to run the hosted demonstration.

---

## Project Team

- Tristan Daniel Apaga
- Tristan James Galpao
- Lanier Celso Caras

---

**AgriTracker – Agricultural Production Tracker & Yield Prediction System**
