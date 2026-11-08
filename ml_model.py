import os
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from generate_synthetic_data import generate_historical_dataset

DATA_PATH = os.path.join("data", "historical_farm_data.csv")
_MODEL_PIPELINE = None

def get_or_train_model():
    """
    Loads historical training data, constructs the ColumnTransformer pipeline,
    fits the RandomForestRegressor, and caches the pipeline in memory.
    """
    global _MODEL_PIPELINE
    if _MODEL_PIPELINE is not None:
        return _MODEL_PIPELINE

    # Ensure historical training CSV exists
    if not os.path.exists(DATA_PATH):
        generate_historical_dataset(500, DATA_PATH)

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

    # Preprocessing Pipeline: One-Hot Encode categorical attributes, pass numeric variables directly
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ("num", "passthrough", numeric_features)
        ]
    )

    # Scikit-learn Pipeline wrapper
    _MODEL_PIPELINE = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(n_estimators=100, random_state=42))
    ])

    _MODEL_PIPELINE.fit(X, y)
    return _MODEL_PIPELINE

def predict_crop_yield(
    category: str, 
    min_days: int, 
    max_days: int, 
    area_ha: float, 
    budget_per_ha: float, 
    field_type: str, 
    planting_month: int,
    season_overlap_ratio: float
) -> float:
    """
    Predicts estimated harvest yield in kilograms (kg) for a planting operation
    using metadata inputs and PAGASA sub-season overlap ratio.
    """
    model = get_or_train_model()
    
    input_df = pd.DataFrame([{
        "category": str(category),
        "min_growth_days": int(min_days),
        "max_growth_days": int(max_days),
        "area_hectares": float(area_ha),
        "budget_per_hectare": float(budget_per_ha),
        "field_type": str(field_type),
        "planting_month": int(planting_month),
        "season_overlap_ratio": float(season_overlap_ratio)
    }])

    predicted_yield = model.predict(input_df)[0]
    return round(float(predicted_yield), 2)