Agricultural Production Tracker CLI

DSA 214 Data Science and Analytics Project — Scenario 3

A robust, Python-based command-line interface (CLI) system designed to manage agricultural production records, track itemized farm expenses, and forecast crop yields using a machine learning model integrated with local climate sub-season metrics.

🚀 Key Features

Year-Grouped Macro-Chronology Seeding: Automatically populates realistic multi-year historical and active farm data (2024–2026) with natural intra-year chronological progression and shuffling.

Machine Learning Yield Forecaster: Utilizes a trained RandomForestRegressor (ml_model.py) to predict crop yields dynamically during seeding based on field area, budgeting, crop category, and planting schedules.

PAGASA Climate Engine: Incorporates Philippine climate sub-season overlap ratios (0.0–1.0) to model seasonal impacts (e.g., peak vs. transition/off-season conditions) on crop performance.

Itemized Expense Management: Child-linked expense records (seeds, fertilizers, labor, utilities) that automatically synchronize with parent production record totals.

Interactive Paginated CLI: Features full pagination, dynamic sorting ([S]), keyword search/filtering ([F]), and detailed record inspection ([I]).

Executive Analytics & Visualization: Generates analytical summaries and visual data export charts using matplotlib.

🛠️ Project Architecture

agricultural-tracker/
│
├── Main.py                     # Main CLI controller and interactive user menus
├── database.py                 # SQLite database schema, connections, and CRUD operations
├── ml_model.py                 # RandomForestRegressor pipeline and live yield prediction engine
├── analytics.py                # Statistical analysis and chart generation workflows
├── generate_synthetic_data.py  # Synthetic dataset generator with climate overlap ratios
├── functions.py                # Core utilities, table renderers, and pagination logic
├── requirements.txt            # Project dependencies
└── README.md                   # Project documentation


⚙️ Prerequisites & Installation

Ensure you have Python 3.x installed on your system.

Clone or download the repository to your local machine.

Open your terminal or command prompt inside the project root folder.

Install the required external libraries using pip:

pip install -r requirements.txt


🎮 Running the Application

To start the CLI application, execute:

python Main.py


Note: On your first launch, the system will automatically generate the historical dataset (data/historical_farm_data.csv) and initialize/seed the SQLite database (database/agricultural_tracker.db) with complete macro-chronological data.

👥 Authors & Contributions

Tristan Daniel Apaga 
Tristan James Galpao
Lanier Celso Caras