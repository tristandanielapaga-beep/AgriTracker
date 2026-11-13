import os
from typing import Dict, Any, Optional

# Enforce headless backend for Matplotlib to prevent thread blocking in CLI environments
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

import database_sqlite_backup as db

CHARTS_DIR = "charts"

def fetch_analytics_dataframe(year: Optional[Any] = None, category: Optional[str] = None) -> pd.DataFrame:
    """
    Retrieves operational database records and converts them into a Pandas DataFrame
    with optional multi-criteria filtering by Year and Crop Category.
    """
    records = db.fetch_joined_records()
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df['planting_date'] = pd.to_datetime(df['planting_date'])
    df['year'] = df['planting_date'].dt.year

    # Apply Multi-Criteria Filters
    if year is not None and str(year).strip().lower() != "all":
        df = df[df['year'] == int(year)]
    if category is not None and str(category).strip().lower() != "all":
        df = df[df['category'] == category]

    return df

def compute_kpi_summary(year: Optional[Any] = None, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes high-level executive KPI metrics across selected filter criteria:
    - Total Harvest Mass (kg) & Total Expenses (₱)
    - Average Yield Variance Percentage (±%)
    - Harvest Efficiency (kg harvested per ₱1,000 spent)
    - Land Productivity Density (kg harvested per hectare)
    """
    df = fetch_analytics_dataframe(year, category)
    if df.empty:
        return {
            "total_records": 0,
            "completed_harvests": 0,
            "total_harvest_kg": 0.0,
            "total_expenses_php": 0.0,
            "avg_variance_pct": 0.0,
            "harvest_efficiency_kg_per_k_php": 0.0,
            "avg_yield_density_kg_ha": 0.0
        }

    completed_df = df[df['status'] == 'Completed']
    
    total_records = len(df)
    completed_count = len(completed_df)
    total_harvest_kg = completed_df['actual_yield_kg'].sum()
    total_expenses_php = df['total_expenses_php'].sum()
    
    avg_variance_pct = completed_df['yield_variance_pct'].mean() if not completed_df.empty else 0.0
    
    # Harvest efficiency: kg produced per ₱1,000 spent
    efficiency = (total_harvest_kg / (total_expenses_php / 1000.0)) if total_expenses_php > 0 else 0.0
    
    # Average Yield Density across completed records (kg / ha)
    if not completed_df.empty and completed_df['area_hectares'].sum() > 0:
        avg_density = completed_df['actual_yield_kg'].sum() / completed_df['area_hectares'].sum()
    else:
        avg_density = 0.0

    return {
        "total_records": total_records,
        "completed_harvests": completed_count,
        "total_harvest_kg": round(float(total_harvest_kg), 2),
        "total_expenses_php": round(float(total_expenses_php), 2),
        "avg_variance_pct": round(float(avg_variance_pct), 2),
        "harvest_efficiency_kg_per_k_php": round(float(efficiency), 2),
        "avg_yield_density_kg_ha": round(float(avg_density), 2)
    }

def print_cli_analytics_report(year: Optional[Any] = None, category: Optional[str] = None):
    """Prints a structured tabular KPI summary directly to the CLI menu."""
    kpi = compute_kpi_summary(year, category)
    filter_year = str(year) if year else "All Years"
    filter_cat = category if category else "All Categories"

    print("\n" + "=" * 80)
    print(f"                    EXECUTIVE AGRICULTURAL ANALYTICAL SUMMARY")
    print(f"               Filter Window: Year = {filter_year} | Category = {filter_cat}")
    print("=" * 80)
    print(f"  Total Tracked Operations:       {kpi['total_records']} records ({kpi['completed_harvests']} completed)")
    print(f"  Total Harvest Output Mass:     {kpi['total_harvest_kg']:,.2f} kg")
    print(f"  Total Capital Expenses:         ₱{kpi['total_expenses_php']:,.2f}")
    print(f"  Average Yield Prediction Error: {kpi['avg_variance_pct']:+.2f}%")
    print(f"  Harvest Efficiency Index:       {kpi['harvest_efficiency_kg_per_k_php']:,.2f} kg per ₱1,000 spent")
    print(f"  Land Yield Density:             {kpi['avg_yield_density_kg_ha']:,.2f} kg / hectare")
    print("=" * 80 + "\n")

def generate_all_charts(output_dir: str = CHARTS_DIR) -> Dict[str, str]:
    """
    Generates all 7 visual analytical charts based on actual database records
    and saves them as high-resolution PNG image files in the designated directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = {}

    df = fetch_analytics_dataframe()
    if df.empty:
        print("[!] No records available in database for chart generation.")
        return generated_files

    completed_df = df[df['status'] == 'Completed'].copy()

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    # --- Chart 1: Target vs. Actual Yield Comparison (Grouped Bar Chart) ---
    if not completed_df.empty:
        plt.figure(figsize=(10, 6))
        cat_yield = completed_df.groupby('category')[['predicted_yield_kg', 'actual_yield_kg']].sum()
        
        x = np.arange(len(cat_yield))
        width = 0.35
        
        plt.bar(x - width/2, cat_yield['predicted_yield_kg'], width, label='Predicted Yield (kg)', color='#3498db')
        plt.bar(x + width/2, cat_yield['actual_yield_kg'], width, label='Actual Yield (kg)', color='#2ecc71')
        
        plt.title('Target (ML Predicted) vs. Actual Harvest Yield by Category', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Crop Category', fontweight='bold')
        plt.ylabel('Yield Mass (kg)', fontweight='bold')
        plt.xticks(x, cat_yield.index, rotation=15)
        plt.legend()
        plt.tight_layout()
        
        chart1_path = os.path.join(output_dir, "chart1_target_vs_actual_yield.png")
        plt.savefig(chart1_path, dpi=300)
        plt.close('all')
        generated_files["chart1"] = chart1_path

    # --- Chart 2: Category Investment vs. Output (Dual-Axis Chart) ---
    if not df.empty:
        fig, ax1 = plt.subplots(figsize=(10, 6))
        cat_totals = df.groupby('category').agg({
            'total_expenses_php': 'sum',
            'actual_yield_kg': 'sum'
        })
        
        x = np.arange(len(cat_totals))
        
        ax1.bar(x, cat_totals['total_expenses_php'], color='#e74c3c', alpha=0.7, width=0.4, label='Total Expenses (₱)')
        ax1.set_xlabel('Crop Category', fontweight='bold')
        ax1.set_ylabel('Total Expenses (PHP ₱)', color='#e74c3c', fontweight='bold')
        ax1.tick_params(axis='y', labelcolor='#e74c3c')
        ax1.set_xticks(x)
        ax1.set_xticklabels(cat_totals.index, rotation=15)

        ax2 = ax1.twinx()
        ax2.plot(x, cat_totals['actual_yield_kg'], color='#27ae60', marker='o', linewidth=2.5, label='Actual Harvest (kg)')
        ax2.set_ylabel('Actual Yield Output (kg)', color='#27ae60', fontweight='bold')
        ax2.tick_params(axis='y', labelcolor='#27ae60')
        ax2.grid(False)

        plt.title('Total Capital Expenditure (₱) vs. Harvest Output (kg)', fontsize=14, fontweight='bold', pad=15)
        fig.tight_layout()
        
        chart2_path = os.path.join(output_dir, "chart2_category_investment_vs_output.png")
        plt.savefig(chart2_path, dpi=300)
        plt.close('all')
        generated_files["chart2"] = chart2_path

    # --- Chart 3: Yield Variance (%) Distribution (Scatter / Bar Chart) ---
    if not completed_df.empty:
        plt.figure(figsize=(10, 6))
        colors = ['#2ecc71' if v >= 0 else '#e74c3c' for v in completed_df['yield_variance_pct']]
        
        plt.bar(range(len(completed_df)), completed_df['yield_variance_pct'], color=colors, edgecolor='black', alpha=0.8)
        plt.axhline(0, color='black', linewidth=1, linestyle='--')
        
        plt.title('Yield Prediction Variance Distribution (Over/Under Performance %)', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Production Record Index', fontweight='bold')
        plt.ylabel('Variance Percentage (±%)', fontweight='bold')
        plt.tight_layout()
        
        chart3_path = os.path.join(output_dir, "chart3_yield_variance_distribution.png")
        plt.savefig(chart3_path, dpi=300)
        plt.close('all')
        generated_files["chart3"] = chart3_path

    # --- Chart 4: Expense Category Breakdown (Donut Chart) ---
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT expense_category, SUM(amount_php) as total_amount
            FROM production_expenses
            GROUP BY expense_category;
        """)
        exp_data = cursor.fetchall()
        
    if exp_data:
        exp_df = pd.DataFrame(exp_data, columns=['category', 'amount'])
        plt.figure(figsize=(8, 8))
        
        plt.pie(
            exp_df['amount'], 
            labels=exp_df['category'], 
            autopct='%1.1f%%', 
            startangle=140,
            pctdistance=0.85,
            colors=plt.cm.Paired(np.linspace(0, 1, len(exp_df)))
        )
        
        centre_circle = plt.Circle((0, 0), 0.70, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        plt.title('Production Expenses Distribution by Input Category', fontsize=14, fontweight='bold', pad=15)
        plt.tight_layout()
        
        chart4_path = os.path.join(output_dir, "chart4_expense_category_breakdown.png")
        plt.savefig(chart4_path, dpi=300)
        plt.close('all')
        generated_files["chart4"] = chart4_path

    # --- Chart 5: Plot Productivity Density (kg/ha Bar Chart) ---
    if not completed_df.empty:
        plt.figure(figsize=(10, 6))
        completed_df['yield_density'] = completed_df['actual_yield_kg'] / completed_df['area_hectares']
        loc_density = completed_df.groupby('location_name')['yield_density'].mean().sort_values(ascending=True)
        
        plt.barh(loc_density.index, loc_density.values, color='#9b59b6', edgecolor='black', alpha=0.85)
        plt.title('Land Plot Productivity Density (Average kg harvested per Hectare)', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Average Yield Density (kg / ha)', fontweight='bold')
        plt.ylabel('Farm Location Plot', fontweight='bold')
        plt.tight_layout()
        
        chart5_path = os.path.join(output_dir, "chart5_plot_productivity.png")
        plt.savefig(chart5_path, dpi=300)
        plt.close('all')
        generated_files["chart5"] = chart5_path

    # --- Chart 6: Unit Cost of Production (₱/kg Horizontal Bar Chart) ---
    if not completed_df.empty:
        plt.figure(figsize=(10, 6))
        crop_cost = completed_df.groupby('crop_name').agg({
            'total_expenses_php': 'sum',
            'actual_yield_kg': 'sum'
        })
        
        crop_cost = crop_cost[crop_cost['actual_yield_kg'] > 0]
        crop_cost['unit_cost_php_kg'] = crop_cost['total_expenses_php'] / crop_cost['actual_yield_kg']
        crop_cost = crop_cost.sort_values(by='unit_cost_php_kg', ascending=True)

        plt.barh(crop_cost.index, crop_cost['unit_cost_php_kg'], color='#f39c12', edgecolor='black', alpha=0.85)
        plt.title('Unit Cost of Production (PHP ₱ per kg harvested)', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Unit Cost Baseline (₱ / kg)', fontweight='bold')
        plt.ylabel('Crop Variety', fontweight='bold')
        plt.tight_layout()
        
        chart6_path = os.path.join(output_dir, "chart6_unit_cost_of_production.png")
        plt.savefig(chart6_path, dpi=300)
        plt.close('all')
        generated_files["chart6"] = chart6_path

    # --- Chart 7: Multi-Year Production Timeline (Multi-Line Chart) ---
    if not df.empty:
        plt.figure(figsize=(11, 6))
        df['year_month'] = df['planting_date'].dt.to_period('M').astype(str)
        timeline = df.groupby('year_month').agg({
            'actual_yield_kg': 'sum',
            'total_expenses_php': 'sum'
        }).reset_index()

        plt.plot(timeline['year_month'], timeline['actual_yield_kg'], marker='s', color='#16a085', linewidth=2, label='Actual Yield (kg)')
        plt.title('Multi-Year Production Output Monthly Timeline (2024–2026)', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Year-Month (Planting Cohort)', fontweight='bold')
        plt.ylabel('Total Harvested Output (kg)', fontweight='bold')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        
        chart7_path = os.path.join(output_dir, "chart7_multi_year_timeline.png")
        plt.savefig(chart7_path, dpi=300)
        plt.close('all')
        generated_files["chart7"] = chart7_path

    print(f"[+] Successfully generated {len(generated_files)} analytical charts in '{output_dir}/'.")
    return generated_files