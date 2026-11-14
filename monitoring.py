
import numpy as np
import pandas as pd
import database as db


def fetch_monitoring_dataframe(admin_user_id):
    """
    Retrieves production records and prepares records
    that have both predicted and actual yields.
    """
    records = db.fetch_analytics_records(admin_user_id)

    df = pd.DataFrame(records)

    if df.empty:
        return df

    df["predicted_yield_kg"] = pd.to_numeric(
        df["predicted_yield_kg"],
        errors="coerce"
    )

    df["actual_yield_kg"] = pd.to_numeric(
        df["actual_yield_kg"],
        errors="coerce"
    )

    return df


def print_model_monitoring_report(admin_user_id):
    """
    Displays actual model performance using recorded
    production outcomes.
    """

    df = fetch_monitoring_dataframe(admin_user_id)

    print("\n========== MODEL MONITORING ==========")

    if df.empty:
        print("No production records available.")
        return

    total_records = len(df)

    has_prediction = df["predicted_yield_kg"].notna()
    has_actual = df["actual_yield_kg"].notna()

    evaluated = df[has_prediction & has_actual].copy()

    print(f"\nTotal production records: {total_records}")
    print(f"Records with predictions: {has_prediction.sum()}")
    print(f"Records with actual yields: {has_actual.sum()}")
    print(f"Records evaluated: {len(evaluated)}")

    pending = int((has_prediction & ~has_actual).sum())

    print(f"Awaiting actual harvest data: {pending}")

    if evaluated.empty:
        print("\nNo records are ready for model evaluation yet.")
        print("======================================")
        return

    # Calculate prediction errors
    evaluated["error"] = (
        evaluated["predicted_yield_kg"]
        - evaluated["actual_yield_kg"]
    )

    evaluated["absolute_error"] = evaluated["error"].abs()

    mae = evaluated["absolute_error"].mean()

    rmse = np.sqrt(
        (evaluated["error"] ** 2).mean()
    )

    bias = evaluated["error"].mean()

    total_actual = evaluated["actual_yield_kg"].sum()

    if total_actual != 0:
        wape = (
            evaluated["absolute_error"].sum()
            / abs(total_actual)
        ) * 100
    else:
        wape = None

    print("\n--- Overall Performance ---")
    print(f"MAE: {mae:,.2f} kg")
    print(f"RMSE: {rmse:,.2f} kg")
    print(f"Prediction Bias: {bias:,.2f} kg")

    if wape is not None:
        print(f"WAPE: {wape:.2f}%")
    else:
        print("WAPE: Not available (total actual yield is zero)")

    print("\n--- Performance by Crop Category ---")

    for category, group in evaluated.groupby("category"):

        category_mae = group["absolute_error"].mean()

        category_rmse = np.sqrt(
            (group["error"] ** 2).mean()
        )

        print(f"\n{category}")
        print(f"  Evaluated records: {len(group)}")
        print(f"  MAE: {category_mae:,.2f} kg")
        print(f"  RMSE: {category_rmse:,.2f} kg")

    print("\n======================================")
