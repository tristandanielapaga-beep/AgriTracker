
import os
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.dummy import DummyRegressor

from sklearn.model_selection import cross_validate, KFold
from sklearn.inspection import permutation_importance


DATA_PATH = os.path.join("data", "historical_farm_data.csv")


def evaluate_model():
    # 1. Load dataset
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}"
        )

    df = pd.read_csv(DATA_PATH)

    X = df.drop(columns=["actual_yield_kg"])
    y = df["actual_yield_kg"]

    categorical_features = ["category", "field_type"]

    numeric_features = [
        "min_growth_days",
        "max_growth_days",
        "area_hectares",
        "budget_per_hectare",
        "planting_month",
        "season_overlap_ratio"
    ]

    # 2. Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42
    )

    # 3. Build preprocessing pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features
            ),
            ("num", "passthrough", numeric_features)
        ]
    )

    # 4. Create Random Forest model
    model = Pipeline(steps=[
        ("preprocessor", preprocessor),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=100,
                random_state=42
            )
        )
    ])

    # 5. Train using training data only
    model.fit(X_train, y_train)

    # 6. Predict using unseen testing data
    predictions = model.predict(X_test)

    # 7. Calculate evaluation metrics
    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)

    # 8. Create a simple baseline for comparison
    baseline = DummyRegressor(strategy="mean")
    baseline.fit(X_train, y_train)

    baseline_predictions = baseline.predict(X_test)

    baseline_mae = mean_absolute_error(
        y_test, baseline_predictions
    )

    baseline_rmse = np.sqrt(
        mean_squared_error(y_test, baseline_predictions)
    )

    baseline_r2 = r2_score(
        y_test, baseline_predictions
    )

    # 9. Display results
    print("\n========== MODEL EVALUATION ==========")

    print(f"Total records: {len(df)}")
    print(f"Training records: {len(X_train)}")
    print(f"Testing records: {len(X_test)}")

    print("\n--- Random Forest ---")
    print(f"MAE:  {mae:,.2f} kg")
    print(f"RMSE: {rmse:,.2f} kg")
    print(f"R²:   {r2:.4f}")

    print("\n--- Mean Baseline ---")
    print(f"MAE:  {baseline_mae:,.2f} kg")
    print(f"RMSE: {baseline_rmse:,.2f} kg")
    print(f"R²:   {baseline_r2:.4f}")

    print("\n======================================")
        # 10. Five-fold cross-validation on training data
    cv = KFold(
        n_splits=5,
        shuffle=True,
        random_state=42
    )

    cv_results = cross_validate(
        model,
        X_train,
        y_train,
        cv=cv,
        scoring={
            "mae": "neg_mean_absolute_error",
            "rmse": "neg_root_mean_squared_error",
            "r2": "r2"
        }
    )

    print("\n--- 5-Fold Cross-Validation ---")

    print(
        f"MAE:  {-cv_results['test_mae'].mean():,.2f} "
        f"+/- {cv_results['test_mae'].std():,.2f} kg"
    )

    print(
        f"RMSE: {-cv_results['test_rmse'].mean():,.2f} "
        f"+/- {cv_results['test_rmse'].std():,.2f} kg"
    )

    print(
        f"R²:   {cv_results['test_r2'].mean():.4f} "
        f"+/- {cv_results['test_r2'].std():.4f}"
    )
    # Performance by crop category
    print("\n--- Performance by Crop Category ---")

    results = X_test[["category"]].copy()
    results["actual"] = y_test.to_numpy()
    results["predicted"] = predictions

    results["absolute_error"] = abs(
        results["actual"] - results["predicted"]
    )

    for category, group in results.groupby("category"):

        category_mae = mean_absolute_error(
            group["actual"],
            group["predicted"]
        )

        category_rmse = np.sqrt(
            mean_squared_error(
                group["actual"],
                group["predicted"]
            )
        )

        relative_mae = (
            category_mae / group["actual"].mean()
        ) * 100

        print(f"\n{category}")
        print(f"  Test records: {len(group)}")
        print(f"  MAE: {category_mae:,.2f} kg")
        print(f"  RMSE: {category_rmse:,.2f} kg")
        print(f"  MAE relative to category mean: {relative_mae:.2f}%")
    
        # Feature importance using permutation importance
    print("\n--- Feature Importance ---")

    importance = permutation_importance(
        model,
        X_test,
        y_test,
        scoring="neg_mean_absolute_error",
        n_repeats=10,
        random_state=42,
        n_jobs=-1
    )

    importance_df = pd.DataFrame({
        "Feature": X_test.columns,
        "Importance": importance.importances_mean,
        "Std": importance.importances_std
    })

    importance_df = importance_df.sort_values(
        by="Importance",
        ascending=False
    )

    print(
        importance_df.to_string(
            index=False,
            formatters={
                "Importance": "{:.4f}".format,
                "Std": "{:.4f}".format
            }
        )
    )

    return model


if __name__ == "__main__":
    evaluate_model()
