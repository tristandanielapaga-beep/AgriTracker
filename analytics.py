import os
import sqlite3
import database
import matplotlib.pyplot as plt

CHARTS_DIR = "charts"


def ensure_charts_dir():
    """Ensure that the /charts directory exists for saving output images."""
    if not os.path.exists(CHARTS_DIR):
        os.makedirs(CHARTS_DIR)


# --- 3 ANALYTICAL MEASURES ---

def calculate_cost_efficiency_by_crop():
    """Measure 1: Calculate average cost per harvested kg per crop."""
    conn = database.get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            c.crop_name,
            SUM(p.production_cost) AS total_cost,
            SUM(p.harvest_qty_kg) AS total_harvest_kg,
            CASE 
                WHEN SUM(p.harvest_qty_kg) > 0 THEN SUM(p.production_cost) / SUM(p.harvest_qty_kg)
                ELSE 0 
            END AS cost_per_kg
        FROM production_records p
        JOIN crops c ON p.crop_id = c.crop_id
        GROUP BY c.crop_name
        ORDER BY cost_per_kg ASC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def calculate_cost_per_hectare_by_category():
    """Measure 2: Calculate total expense and average cost per hectare across categories."""
    conn = database.get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            c.category,
            COUNT(p.record_id) AS total_records,
            SUM(p.area_hectares) AS total_hectares,
            SUM(p.production_cost) AS total_cost,
            AVG(p.production_cost / p.area_hectares) AS avg_cost_per_hectare
        FROM production_records p
        JOIN crops c ON p.crop_id = c.crop_id
        GROUP BY c.category;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def calculate_production_status_summary():
    """Measure 3: Summarize completed vs. ongoing crops and total capital investment."""
    conn = database.get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            COUNT(CASE WHEN harvest_date IS NOT NULL THEN 1 END) AS completed_crops,
            COUNT(CASE WHEN harvest_date IS NULL THEN 1 END) AS ongoing_crops,
            COALESCE(SUM(harvest_qty_kg), 0) AS total_harvest_kg,
            COALESCE(SUM(production_cost), 0) AS total_investment
        FROM production_records;
    """
    cursor.execute(query)
    summary = cursor.fetchone()
    conn.close()
    return summary


def display_analytical_summaries():
    """Print the 3 analytical measures formatted cleanly in the CLI console."""
    print("\n" + "=" * 80)
    print("                    AGRICULTURAL ANALYTICAL SUMMARIES                   ")
    print("=" * 80)

    # Measure 1 Display
    print("\n--- Measure 1: Crop Cost Efficiency (Cost per Harvested kg) ---")
    efficiency_data = calculate_cost_efficiency_by_crop()
    print(f"{'Crop Name':<20} | {'Total Cost ($)':<15} | {'Total Yield (kg)':<18} | {'Cost / kg ($)':<12}")
    print("-" * 75)
    for row in efficiency_data:
        print(f"{row['crop_name']:<20} | {row['total_cost']:<15.2f} | {row['total_harvest_kg']:<18.1f} | ${row['cost_per_kg']:<12.2f}")

    # Measure 2 Display
    print("\n--- Measure 2: Production Cost per Hectare by Category ---")
    category_data = calculate_cost_per_hectare_by_category()
    print(f"{'Category':<15} | {'Records':<8} | {'Total Area (ha)':<16} | {'Avg Cost / ha ($)':<18}")
    print("-" * 65)
    for row in category_data:
        print(f"{row['category']:<15} | {row['total_records']:<8} | {row['total_hectares']:<16.2f} | ${row['avg_cost_per_hectare']:<18.2f}")

    # Measure 3 Display
    print("\n--- Measure 3: Farm Production Status Summary ---")
    status = calculate_production_status_summary()
    total_records = status['completed_crops'] + status['ongoing_crops']
    completion_rate = (status['completed_crops'] / total_records * 100) if total_records > 0 else 0

    print(f"  • Total Production Records:  {total_records}")
    print(f"  • Harvested Crops:          {status['completed_crops']} ({completion_rate:.1f}%)")
    print(f"  • Crops in Progress:        {status['ongoing_crops']}")
    print(f"  • Cumulative Yield:         {status['total_harvest_kg']:,.1f} kg")
    print(f"  • Total Capital Invested:   ${status['total_investment']:,.2f}")
    print("=" * 80)


# --- 2 CHARTS GENERATION ---

def generate_yield_by_crop_chart():
    """Chart 1: Render and save a Bar Chart of Harvest Yield (kg) by Crop Name."""
    ensure_charts_dir()
    data = calculate_cost_efficiency_by_crop()
    
    crops = [row['crop_name'] for row in data]
    yields = [row['total_harvest_kg'] for row in data]

    plt.figure(figsize=(8, 5))
    bars = plt.bar(crops, yields, color='forestgreen', edgecolor='black', alpha=0.85)

    plt.title('Total Harvested Quantity by Crop Type (kg)', fontsize=14, fontweight='bold')
    plt.xlabel('Crop Name', fontsize=11)
    plt.ylabel('Harvest Yield (kg)', fontsize=11)
    plt.xticks(rotation=20, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.6)

    # Add data values on top of bars
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 100, f'{yval:,.0f} kg', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    chart_path = os.path.join(CHARTS_DIR, "yield_by_crop.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    return chart_path


def generate_cost_by_category_chart():
    """Chart 2: Render and save a Pie Chart of Total Expenses by Crop Category."""
    ensure_charts_dir()
    data = calculate_cost_per_hectare_by_category()

    categories = [row['category'] for row in data]
    costs = [row['total_cost'] for row in data]

    plt.figure(figsize=(7, 7))
    colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']

    plt.pie(
        costs, 
        labels=categories, 
        autopct='%1.1f%%', 
        startangle=140, 
        colors=colors, 
        wedgeprops={'edgecolor': 'black'}
    )
    plt.title('Production Expense Distribution by Crop Category', fontsize=14, fontweight='bold')

    plt.tight_layout()
    chart_path = os.path.join(CHARTS_DIR, "cost_by_category.png")
    plt.savefig(chart_path, dpi=300)
    plt.close()
    return chart_path


def generate_all_charts():
    """Generate both required charts and inform user of file locations."""
    print("\nGenerating charts from SQLite database records...")
    path1 = generate_yield_by_crop_chart()
    path2 = generate_cost_by_category_chart()

    print("\n[SUCCESS] Charts generated successfully!")
    print(f"  1. Yield Bar Chart:     {os.path.abspath(path1)}")
    print(f"  2. Category Expense Pie: {os.path.abspath(path2)}")