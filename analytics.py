
import os
from typing import Dict, Any, Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import numpy as np

import database as db


CHARTS_DIR = "charts"
HISTORICAL_CREATOR = "__historical__"

# Executive dashboard palette
NAVY = "#243B53"
GREEN = "#27866B"
LIGHT_GREEN = "#75B798"
RED = "#D65A5A"
GOLD = "#D9A441"
PURPLE = "#8174B8"
GRAY = "#64748B"
LIGHT_GRAY = "#E8EDF2"


def configure_chart_style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": LIGHT_GRAY,
        "axes.labelcolor": NAVY,
        "axes.titlecolor": NAVY,
        "xtick.color": GRAY,
        "ytick.color": GRAY,
        "text.color": NAVY,
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "legend.frameon": False,
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
    })


def empty_filters() -> Dict[str, Any]:
    return {
        "year": None,
        "category": None,
        "crop_name": None,
        "location_name": None,
        "created_by": None,
        "status": None,
    }


def get_filter_options(admin_user_id: int) -> Dict[str, Any]:
    """Return available filter values from the administrator's records."""
    df = fetch_analytics_dataframe(admin_user_id)

    if df.empty:
        return {
            "years": [],
            "categories": [],
            "crops": [],
            "locations": [],
            "creators": [],
            "statuses": [],
        }

    years = sorted(
        df["year"].dropna().astype(int).unique().tolist(),
        reverse=True,
    )

    categories = sorted(
        df["category"].dropna().astype(str).unique().tolist()
    )

    crops = sorted(
        df["crop_name"].dropna().astype(str).unique().tolist()
    )

    locations = sorted(
        df["location_name"].dropna().astype(str).unique().tolist()
    )

    statuses = sorted(
        df["status"].dropna().astype(str).unique().tolist()
    )

    # Only show users who have created at least one production record.
    creator_ids = set(
        pd.to_numeric(df["created_by"], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )

    users = db.fetch_all_users(admin_user_id)
    creators = []

    for user in users:
        user_id = int(user["user_id"])

        if user_id in creator_ids:
            creators.append({
                "value": user_id,
                "label": (
                    f'{user["full_name"]} '
                    f'(@{user["username"]}, ID #{user_id})'
                ),
            })

    if df["created_by"].isna().any():
        creators.append({
            "value": HISTORICAL_CREATOR,
            "label": "Historical / Unassigned records",
        })

    return {
        "years": years,
        "categories": categories,
        "crops": crops,
        "locations": locations,
        "creators": creators,
        "statuses": statuses,
    }


def fetch_analytics_dataframe(
    admin_user_id: int,
    filters: Optional[Dict[str, Any]] = None,
    year: Optional[Any] = None,
    category: Optional[str] = None,
) -> pd.DataFrame:
    """
    Retrieve administrator-only analytics records and apply all active
    filters consistently.

    Year is derived from planting_date.
    The year/category arguments remain available for compatibility
    with earlier calls.
    """
    records = db.fetch_analytics_records(admin_user_id)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    for column in ("planting_date", "actual_harvest_date"):
        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
        )

    df["year"] = df["planting_date"].dt.year

    numeric_columns = [
        "record_id",
        "created_by",
        "predicted_yield_kg",
        "actual_yield_kg",
        "yield_variance_pct",
        "total_expenses_php",
        "area_hectares",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    active = empty_filters()

    if filters:
        active.update(filters)

    # Backward compatibility for older year/category calls.
    if year is not None:
        active["year"] = year

    if category is not None:
        active["category"] = category

    if active["year"] is not None:
        df = df[df["year"] == int(active["year"])]

    for key in ("category", "crop_name", "location_name", "status"):
        value = active.get(key)

        if value is not None:
            df = df[df[key] == value]

    creator = active.get("created_by")

    if creator == HISTORICAL_CREATOR:
        df = df[df["created_by"].isna()]
    elif creator is not None:
        df = df[df["created_by"] == int(creator)]

    return df.copy()


def compute_kpi_summary(
    admin_user_id: int,
    filters: Optional[Dict[str, Any]] = None,
    year: Optional[Any] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute executive KPI metrics using the active filters."""

    df = fetch_analytics_dataframe(
        admin_user_id,
        filters=filters,
        year=year,
        category=category,
    )

    if df.empty:
        return {
            "total_records": 0,
            "completed_harvests": 0,
            "total_harvest_kg": 0.0,
            "total_expenses_php": 0.0,
            "avg_variance_pct": 0.0,
            "harvest_efficiency_kg_per_k_php": 0.0,
            "avg_yield_density_kg_ha": 0.0,
        }

    completed_df = df[df["status"] == "Completed"].copy()

    valid_harvests = completed_df.dropna(
        subset=["actual_yield_kg"]
    ).copy()

    total_harvest_kg = valid_harvests["actual_yield_kg"].sum()

    total_expenses_php = df["total_expenses_php"].fillna(0).sum()

    avg_variance_pct = completed_df["yield_variance_pct"].mean()

    if pd.isna(avg_variance_pct):
        avg_variance_pct = 0.0

    efficiency = (
        total_harvest_kg / (total_expenses_php / 1000.0)
        if total_expenses_php > 0 else 0.0
    )

    valid_area = valid_harvests[
        valid_harvests["area_hectares"] > 0
    ]

    if not valid_area.empty:
        avg_density = (
            valid_area["actual_yield_kg"].sum()
            / valid_area["area_hectares"].sum()
        )
    else:
        avg_density = 0.0

    return {
        "total_records": len(df),
        "completed_harvests": len(completed_df),
        "total_harvest_kg": round(float(total_harvest_kg), 2),
        "total_expenses_php": round(float(total_expenses_php), 2),
        "avg_variance_pct": round(float(avg_variance_pct), 2),
        "harvest_efficiency_kg_per_k_php": round(float(efficiency), 2),
        "avg_yield_density_kg_ha": round(float(avg_density), 2),
    }


def format_filter_value(value, all_label):
    return all_label if value is None else str(value)


def print_active_filters(
    filters: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
):
    """Print a readable summary of the currently selected filters."""
    active = empty_filters()

    if filters:
        active.update(filters)

    creator_label = "All Users"

    if active["created_by"] == HISTORICAL_CREATOR:
        creator_label = "Historical / Unassigned"
    elif active["created_by"] is not None:
        creator_label = f"User ID #{active['created_by']}"

        if options:
            for creator in options.get("creators", []):
                if creator["value"] == active["created_by"]:
                    creator_label = creator["label"]
                    break

    print("\nACTIVE FILTERS")
    print("-" * 65)
    print(f"Year (planting): {format_filter_value(active['year'], 'All Years')}")
    print(f"Crop Category:   {format_filter_value(active['category'], 'All Categories')}")
    print(f"Crop:            {format_filter_value(active['crop_name'], 'All Crops')}")
    print(f"Location:        {format_filter_value(active['location_name'], 'All Locations')}")
    print(f"Created By:      {creator_label}")
    print(f"Status:          {format_filter_value(active['status'], 'All Statuses')}")
    print("-" * 65)


def print_cli_analytics_report(
    admin_user_id: int,
    filters: Optional[Dict[str, Any]] = None,
    year: Optional[Any] = None,
    category: Optional[str] = None,
):
    """Print the executive KPI report using the active filters."""

    kpi = compute_kpi_summary(
        admin_user_id,
        filters=filters,
        year=year,
        category=category,
    )

    active = empty_filters()

    if filters:
        active.update(filters)

    print("\n" + "=" * 80)
    print("                    EXECUTIVE AGRICULTURAL ANALYTICAL SUMMARY")
    print("=" * 80)

    print_active_filters(active)

    print(
        f"  Total Tracked Operations:       "
        f"{kpi['total_records']} records "
        f"({kpi['completed_harvests']} completed)"
    )
    print(
        f"  Total Harvest Output Mass:      "
        f"{kpi['total_harvest_kg']:,.2f} kg"
    )
    print(
        f"  Total Capital Expenses:         "
        f"₱{kpi['total_expenses_php']:,.2f}"
    )
    print(
        f"  Average Yield Prediction Error: "
        f"{kpi['avg_variance_pct']:+.2f}%"
    )
    print(
        f"  Harvest Efficiency Index:       "
        f"{kpi['harvest_efficiency_kg_per_k_php']:,.2f} "
        f"kg per ₱1,000 spent"
    )
    print(
        f"  Land Yield Density:             "
        f"{kpi['avg_yield_density_kg_ha']:,.2f} kg / hectare"
    )

    print("=" * 80 + "\n")


def generate_all_charts(
    admin_user_id: int,
    filters: Optional[Dict[str, Any]] = None,
    output_dir: str = CHARTS_DIR,
) -> Dict[str, str]:
    """
    Generate seven executive-style charts using the same active
    filters as the KPI report.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = {}

    df = fetch_analytics_dataframe(
        admin_user_id,
        filters=filters,
    )

    if df.empty:
        print("[!] No records match the selected filters.")
        return generated_files

    completed_df = df[df["status"] == "Completed"].copy()

    configure_chart_style()

    # Chart 1: Predicted vs actual yield by crop category
    chart1_df = completed_df.dropna(
        subset=["predicted_yield_kg", "actual_yield_kg", "category"]
    )

    if not chart1_df.empty:
        category_yield = chart1_df.groupby("category")[
            ["predicted_yield_kg", "actual_yield_kg"]
        ].sum()

        x = np.arange(len(category_yield))
        width = 0.36

        fig, ax = plt.subplots(figsize=(11, 6))
        ax.bar(
            x - width / 2,
            category_yield["predicted_yield_kg"],
            width,
            label="Predicted Yield",
            color=NAVY,
        )
        ax.bar(
            x + width / 2,
            category_yield["actual_yield_kg"],
            width,
            label="Actual Yield",
            color=GREEN,
        )

        ax.set_title("Predicted vs. Actual Harvest Yield", pad=20)
        ax.set_xlabel("Crop Category")
        ax.set_ylabel("Yield (kg)")
        ax.set_xticks(x)
        ax.set_xticklabels(category_yield.index)
        ax.yaxis.set_major_formatter(
            ticker.StrMethodFormatter("{x:,.0f}")
        )
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        ax.legend()

        fig.tight_layout()
        path = os.path.join(output_dir, "chart1_target_vs_actual_yield.png")
        fig.savefig(path, dpi=300)
        plt.close(fig)
        generated_files["chart1"] = path

    # Chart 2: Investment vs harvest output
    chart2_df = completed_df.dropna(
        subset=["total_expenses_php", "actual_yield_kg"]
    )

    if not chart2_df.empty:
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.scatter(
            chart2_df["total_expenses_php"],
            chart2_df["actual_yield_kg"],
            s=75,
            color=GREEN,
            alpha=0.75,
            edgecolors="white",
            linewidths=0.8,
        )

        ax.set_title("Production Investment vs. Harvest Output", pad=20)
        ax.set_xlabel("Total Production Expenses (₱)")
        ax.set_ylabel("Actual Harvest Output (kg)")
        ax.xaxis.set_major_formatter(
            ticker.StrMethodFormatter("₱{x:,.0f}")
        )
        ax.yaxis.set_major_formatter(
            ticker.StrMethodFormatter("{x:,.0f}")
        )
        ax.grid(alpha=0.2)
        ax.set_axisbelow(True)

        fig.tight_layout()
        path = os.path.join(output_dir, "chart2_investment_vs_output.png")
        fig.savefig(path, dpi=300)
        plt.close(fig)
        generated_files["chart2"] = path

    # Chart 3: Prediction variance by production record
    chart3_df = completed_df.dropna(
        subset=["yield_variance_pct"]
    ).sort_values("record_id")

    if not chart3_df.empty:
        fig, ax = plt.subplots(figsize=(12, 6))

        colors = [
            GREEN if value >= 0 else RED
            for value in chart3_df["yield_variance_pct"]
        ]

        x = np.arange(len(chart3_df))
        ax.bar(
            x,
            chart3_df["yield_variance_pct"],
            color=colors,
            width=0.75,
        )
        ax.axhline(0, color=NAVY, linewidth=1.2)

        ax.set_title("Yield Prediction Variance by Production Record", pad=20)
        ax.set_xlabel("Production Record")
        ax.set_ylabel("Prediction Variance (%)")

        if len(chart3_df) <= 25:
            ax.set_xticks(x)
            ax.set_xticklabels(
                chart3_df["record_id"].astype(int).astype(str),
                rotation=45,
            )
        else:
            ax.set_xticks([])

        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)

        fig.tight_layout()
        path = os.path.join(output_dir, "chart3_yield_prediction_variance.png")
        fig.savefig(path, dpi=300)
        plt.close(fig)
        generated_files["chart3"] = path

    # Chart 4: Expense category breakdown for filtered record IDs
    record_ids = df["record_id"].dropna().astype(int).tolist()

    exp_data = db.fetch_expense_category_totals(
        admin_user_id,
        record_ids=record_ids,
    )

    if exp_data:
        exp_df = pd.DataFrame(exp_data).rename(
            columns={"total_amount": "amount"}
        )

        exp_df = exp_df.dropna(
            subset=["category", "amount"]
        ).sort_values("amount", ascending=True)

        if not exp_df.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(
                exp_df["category"],
                exp_df["amount"],
                color=GREEN,
                height=0.65,
            )

            ax.set_title("Production Expenses by Category", pad=20)
            ax.set_xlabel("Total Expenses (₱)")
            ax.set_ylabel("Expense Category")
            ax.xaxis.set_major_formatter(
                ticker.StrMethodFormatter("₱{x:,.0f}")
            )
            ax.grid(axis="x", alpha=0.2)
            ax.set_axisbelow(True)

            fig.tight_layout()
            path = os.path.join(output_dir, "chart4_expense_category_breakdown.png")
            fig.savefig(path, dpi=300)
            plt.close(fig)
            generated_files["chart4"] = path

    # Chart 5: Productivity by farm location
    chart5_df = completed_df.dropna(
        subset=["actual_yield_kg", "area_hectares", "location_name"]
    ).copy()

    chart5_df = chart5_df[chart5_df["area_hectares"] > 0]

    if not chart5_df.empty:
        location_stats = chart5_df.groupby("location_name").agg(
            total_yield_kg=("actual_yield_kg", "sum"),
            total_area_ha=("area_hectares", "sum"),
            record_count=("record_id", "count"),
        )

        location_stats["yield_density"] = (
            location_stats["total_yield_kg"]
            / location_stats["total_area_ha"]
        )

        location_stats = location_stats.sort_values(
            "yield_density",
            ascending=True,
        )

        fig, ax = plt.subplots(figsize=(10, 7))
        ax.barh(
            location_stats.index,
            location_stats["yield_density"],
            color=PURPLE,
            height=0.65,
        )

        ax.set_title("Agricultural Plot Productivity", pad=20)
        ax.set_xlabel("Harvested Yield (kg per hectare)")
        ax.set_ylabel("Farm Location")
        ax.xaxis.set_major_formatter(
            ticker.StrMethodFormatter("{x:,.0f}")
        )
        ax.grid(axis="x", alpha=0.2)
        ax.set_axisbelow(True)

        labels = [
            f"{name} (n={count})"
            for name, count in zip(
                location_stats.index,
                location_stats["record_count"],
            )
        ]

        ax.set_yticks(np.arange(len(location_stats)))
        ax.set_yticklabels(labels)

        fig.tight_layout()
        path = os.path.join(output_dir, "chart5_plot_productivity.png")
        fig.savefig(path, dpi=300)
        plt.close(fig)
        generated_files["chart5"] = path

    # Chart 6: Unit cost of production by crop
    chart6_df = completed_df.dropna(
        subset=["crop_name", "total_expenses_php", "actual_yield_kg"]
    ).copy()

    chart6_df = chart6_df[chart6_df["actual_yield_kg"] > 0]

    if not chart6_df.empty:
        crop_cost = chart6_df.groupby("crop_name").agg(
            total_expenses=("total_expenses_php", "sum"),
            total_yield=("actual_yield_kg", "sum"),
            record_count=("record_id", "count"),
        )

        crop_cost["unit_cost_php_kg"] = (
            crop_cost["total_expenses"] / crop_cost["total_yield"]
        )

        crop_cost = crop_cost.sort_values(
            "unit_cost_php_kg",
            ascending=True,
        )

        fig, ax = plt.subplots(figsize=(10, 7))
        ax.barh(
            crop_cost.index,
            crop_cost["unit_cost_php_kg"],
            color=GOLD,
            height=0.65,
        )

        ax.set_title("Production Cost per Kilogram by Crop", pad=20)
        ax.set_xlabel("Production Cost (₱ per kg)")
        ax.set_ylabel("Crop")
        ax.xaxis.set_major_formatter(
            ticker.StrMethodFormatter("₱{x:,.2f}")
        )
        ax.grid(axis="x", alpha=0.2)
        ax.set_axisbelow(True)

        labels = [
            f"{name} (n={count})"
            for name, count in zip(
                crop_cost.index,
                crop_cost["record_count"],
            )
        ]

        ax.set_yticks(np.arange(len(crop_cost)))
        ax.set_yticklabels(labels)

        fig.tight_layout()
        path = os.path.join(output_dir, "chart6_unit_cost_of_production.png")
        fig.savefig(path, dpi=300)
        plt.close(fig)
        generated_files["chart6"] = path

    # Chart 7: Monthly harvest output trend
    chart7_df = completed_df.dropna(
        subset=["actual_harvest_date", "actual_yield_kg"]
    ).copy()

    if not chart7_df.empty:
        chart7_df["harvest_month"] = (
            chart7_df["actual_harvest_date"].dt.to_period("M")
        )

        monthly_harvest = chart7_df.groupby(
            "harvest_month"
        )["actual_yield_kg"].sum().sort_index()

        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(monthly_harvest))

        ax.plot(
            x,
            monthly_harvest.values,
            color=GREEN,
            marker="o",
            linewidth=2.5,
            markersize=7,
        )

        ax.fill_between(
            x,
            monthly_harvest.values,
            alpha=0.10,
            color=GREEN,
        )

        ax.set_title("Monthly Actual Harvest Output Trend", pad=20)
        ax.set_xlabel("Harvest Month")
        ax.set_ylabel("Total Harvest Output (kg)")
        ax.yaxis.set_major_formatter(
            ticker.StrMethodFormatter("{x:,.0f}")
        )
        ax.set_xticks(x)
        ax.set_xticklabels(
            monthly_harvest.index.astype(str),
            rotation=45,
            ha="right",
        )
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)

        fig.tight_layout()
        path = os.path.join(output_dir, "chart7_monthly_harvest_trend.png")
        fig.savefig(path, dpi=300)
        plt.close(fig)
        generated_files["chart7"] = path

    print(
        f"[+] Successfully generated {len(generated_files)} "
        f"analytical charts in '{output_dir}/'."
    )

    return generated_files
