import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

import database as db
import ml_model

# PAGASA Climate Sub-Season Definition (Philippines)
SUB_SEASON_MONTHS = {
    "Cool Dry": {11, 12, 1, 2},
    "Hot Dry": {3, 4, 5},
    "Wet": {6, 7, 8, 9, 10},
    "Year-Round": set(range(1, 13))
}

# --- 1. Validation Helpers ---

def validate_date_format(date_str: str) -> bool:
    """Validates if a string adheres strictly to ISO format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except (ValueError, AttributeError):
        return False

def validate_harvest_after_planting(planting_date_str: str, harvest_date_str: str) -> bool:
    """Enforces rule: Harvest Date >= Planting Date."""
    if not validate_date_format(planting_date_str) or not validate_date_format(harvest_date_str):
        return False
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    harvest_dt = datetime.strptime(harvest_date_str.strip(), "%Y-%m-%d")
    return harvest_dt >= plant_dt

def validate_positive_number(val: Any) -> bool:
    """Ensures numeric inputs are strictly positive (> 0)."""
    try:
        num = float(val)
        return num > 0
    except (ValueError, TypeError):
        return False

def validate_non_negative_number(val: Any) -> bool:
    """Ensures numeric inputs are non-negative (>= 0)."""
    try:
        num = float(val)
        return num >= 0
    except (ValueError, TypeError):
        return False
def validate_expense_date(
    expense_date_str: str, 
    planting_date_str: str, 
    actual_harvest_date_str: Optional[str] = None, 
    max_pre_days: int = 90, 
    max_post_days: int = 30
) -> Tuple[bool, str]:
    """
    Validates that an expense date falls within a realistic agronomic window:
    - No earlier than 90 days before planting (pre-planting inputs/seeds)
    - No later than 30 days after harvest (post-harvest processing/labor)
    """
    if not validate_date_format(expense_date_str):
        return False, "Invalid date format. Use strict zero-padded format YYYY-MM-DD (e.g., 2024-04-12)."

    try:
        exp_dt = datetime.strptime(expense_date_str.strip(), "%Y-%m-%d")
        plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    except ValueError:
        return False, "Invalid calendar date."

    # 1. Lower Bound Guard: Max 90 days before planting
    min_allowed_dt = plant_dt - timedelta(days=max_pre_days)
    if exp_dt < min_allowed_dt:
        return False, f"Expense date ({expense_date_str}) is too far in the past. Pre-planting expenses are allowed up to {max_pre_days} days before planting ({min_allowed_dt.strftime('%Y-%m-%d')})."

    # 2. Upper Bound Guard: Max 30 days after harvest (if completed)
    if actual_harvest_date_str:
        harvest_dt = datetime.strptime(actual_harvest_date_str.strip(), "%Y-%m-%d")
        max_allowed_dt = harvest_dt + timedelta(days=max_post_days)
        if exp_dt > max_allowed_dt:
            return False, f"Expense date ({expense_date_str}) cannot exceed {max_post_days} days past actual harvest date ({actual_harvest_date_str})."

    return True, "Valid"

# --- 2. Agronomic & Seasonality Calculation Engines ---

def calculate_target_harvest_window(planting_date_str: str, min_days: int, max_days: int) -> Tuple[str, str]:
    """
    Computes the operational min and max target harvest dates based on crop maturity specs.
    """
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    min_harvest_dt = plant_dt + timedelta(days=int(min_days))
    max_harvest_dt = plant_dt + timedelta(days=int(max_days))
    
    return min_harvest_dt.strftime("%Y-%m-%d"), max_harvest_dt.strftime("%Y-%m-%d")

def evaluate_harvest_timing(actual_harvest_date_str: str, min_harvest_date_str: str, max_harvest_date_str: str) -> str:
    """
    Evaluates harvest timing status against expected growth duration windows:
    - Premature: Harvested before min growth days.
    - On-Time: Harvested within [min_days, max_days] window.
    - Overdue: Harvested after max growth days.
    """
    actual_dt = datetime.strptime(actual_harvest_date_str.strip(), "%Y-%m-%d")
    min_dt = datetime.strptime(min_harvest_date_str.strip(), "%Y-%m-%d")
    max_dt = datetime.strptime(max_harvest_date_str.strip(), "%Y-%m-%d")

    if actual_dt < min_dt:
        return "Premature"
    elif min_dt <= actual_dt <= max_dt:
        return "On-Time"
    else:
        return "Overdue"

def compute_pagasa_overlap(planting_date_str: str, growth_days: int, preferred_sub_season: str) -> Tuple[float, str]:
    """
    Calculates exact daily growth overlap against PAGASA climate sub-seasons:
    - In-Season (>= 75% overlap)
    - Transition / Partial (40% - 74% overlap)
    - Off-Season (< 40% overlap)
    """
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    planting_month = plant_dt.month
    
    overlap_ratio = ml_model.calculate_season_overlap_ratio(planting_month, growth_days, preferred_sub_season)
    
    if overlap_ratio >= 0.75:
        seasonality_tag = "In-Season"
    elif overlap_ratio >= 0.40:
        seasonality_tag = "Transition / Partial"
    else:
        seasonality_tag = "Off-Season"

    return overlap_ratio, seasonality_tag

def calculate_yield_variance_pct(predicted_kg: float, actual_kg: float) -> float:
    """
    Computes over/under prediction percentage:
    ((Actual - Predicted) / Predicted) * 100
    Returns +% for over-performance, -% for under-performance.
    """
    if predicted_kg <= 0:
        return 0.0
    variance = ((actual_kg - predicted_kg) / predicted_kg) * 100.0
    return round(float(variance), 2)

# --- 3. Operational Ledger Pagination Engine ---

def paginate_records(records: List[Dict[str, Any]], page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Paginates an arbitrary list of dictionary records.
    Returns structured pagination metadata package.
    """
    total_records = len(records)
    if total_records == 0:
        return {
            "items": [],
            "current_page": 1,
            "total_pages": 1,
            "page_size": page_size,
            "total_records": 0
        }

    total_pages = (total_records + page_size - 1) // page_size
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = records[start_idx:end_idx]

    return {
        "items": paginated_items,
        "current_page": current_page,
        "total_pages": total_pages,
        "page_size": page_size,
        "total_records": total_records
    }

# --- 4. Transaction Workflows (Decoupled Business API) ---

def add_crop_type(crop_name: str, category: str, min_growth_days: int, max_growth_days: int, preferred_sub_season: str) -> Dict[str, Any]:
    """Registers a new crop variant in the SQLite catalog."""
    if not crop_name.strip():
        return {"success": False, "message": "Crop name cannot be empty."}
    if min_growth_days <= 0 or max_growth_days < min_growth_days:
        return {"success": False, "message": "Invalid growth duration ranges."}
    if preferred_sub_season not in SUB_SEASON_MONTHS:
        return {"success": False, "message": "Invalid PAGASA sub-season target."}

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO crops (crop_name, category, min_growth_days, max_growth_days, preferred_sub_season)
                VALUES (?, ?, ?, ?, ?);
            """, (crop_name.strip(), category.strip(), int(min_growth_days), int(max_growth_days), preferred_sub_season.strip()))
            conn.commit()
            new_id = cursor.lastrowid
        return {"success": True, "message": f"Crop '{crop_name}' registered successfully.", "crop_id": new_id}
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"Crop name '{crop_name}' already exists in catalog."}

def add_farm_location(location_name: str, field_type: str, area_hectares: float) -> Dict[str, Any]:
    """Registers a reusable farm plot in the locations catalog."""
    if not location_name.strip():
        return {"success": False, "message": "Location name cannot be empty."}
    if not validate_positive_number(area_hectares):
        return {"success": False, "message": "Area in hectares must be strictly positive (> 0)."}

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO locations (location_name, field_type, area_hectares)
                VALUES (?, ?, ?);
            """, (location_name.strip(), field_type.strip(), float(area_hectares)))
            conn.commit()
            new_id = cursor.lastrowid
        return {"success": True, "message": f"Location '{location_name}' registered successfully.", "location_id": new_id}
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"Location '{location_name}' already exists."}

def create_planting_operation(
    crop_id: int, 
    location_id: int, 
    planting_date_str: str, 
    initial_budget_php: float = 0.0,
    initial_expense_description: str = "Initial Land Prep & Planting"
) -> Dict[str, Any]:
    """
    Executes complete planting workflow:
    1. Fetches metadata from crops & locations tables.
    2. Calculates target harvest windows and PAGASA overlap ratio.
    3. Triggers ML prediction engine for predicted yield output.
    4. Inserts production record and logs initial itemized expense (if budget > 0).
    """
    if not validate_date_format(planting_date_str):
        return {"success": False, "message": "Invalid planting date format. Use YYYY-MM-DD."}

    crops = {c["crop_id"]: c for c in db.fetch_all_crops()}
    locations = {l["location_id"]: l for l in db.fetch_all_locations()}

    if crop_id not in crops:
        return {"success": False, "message": f"Crop ID {crop_id} not found."}
    if location_id not in locations:
        return {"success": False, "message": f"Location ID {location_id} not found."}

    crop = crops[crop_id]
    loc = locations[location_id]

    # Calculate operational target dates
    target_min, target_max = calculate_target_harvest_window(
        planting_date_str, crop["min_growth_days"], crop["max_growth_days"]
    )

    # Compute PAGASA Sub-Season Overlap Ratio
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    overlap_ratio, season_tag = compute_pagasa_overlap(
        planting_date_str, crop["min_growth_days"], crop["preferred_sub_season"]
    )

    # Compute budget per hectare for ML prediction engine
    area_ha = loc["area_hectares"]
    budget_per_ha = (initial_budget_php / area_ha) if initial_budget_php > 0 else 25000.0

    # Call Scikit-Learn ML Model Prediction Engine
    predicted_yield_kg = ml_model.predict_crop_yield(
        category=crop["category"],
        min_days=crop["min_growth_days"],
        max_days=crop["max_growth_days"],
        area_ha=loc["area_hectares"],
        budget_per_ha=budget_per_ha,
        field_type=loc["field_type"],
        planting_month=plant_dt.month,
        season_overlap_ratio=overlap_ratio
    )

    # Database Transaction
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO production_records (
                crop_id, location_id, planting_date, target_min_harvest_date, target_max_harvest_date,
                predicted_yield_kg, actual_yield_kg, yield_variance_pct, total_expenses_php, status, is_historical
            ) VALUES (?, ?, ?, ?, ?, ?, 0.0, 0.0, 0.0, 'In Progress', 0);
        """, (crop_id, location_id, planting_date_str.strip(), target_min, target_max, predicted_yield_kg))
        
        record_id = cursor.lastrowid
        conn.commit()

    # Log initial seed/planting budget expense if specified
    if initial_budget_php > 0:
        db.add_itemized_expense(
            record_id=record_id,
            category="Seeds/Seedlings",
            description=initial_expense_description,
            amount_php=float(initial_budget_php),
            date_logged=planting_date_str.strip()
        )

    return {
        "success": True,
        "record_id": record_id,
        "predicted_yield_kg": predicted_yield_kg,
        "target_min_harvest_date": target_min,
        "target_max_harvest_date": target_max,
        "seasonality_tag": season_tag,
        "season_overlap_ratio": overlap_ratio,
        "message": f"Planting logged successfully (Record #{record_id}). ML Predicted Yield: {predicted_yield_kg:,.2f} kg ({season_tag})."
    }

def record_harvest_completion(record_id: int, actual_harvest_date_str: str, actual_yield_kg: float) -> Dict[str, Any]:
    """
    Executes harvest completion workflow:
    1. Validates harvest date vs planting date.
    2. Calculates yield variance percentage vs ML prediction.
    3. Evaluates timing status (Premature, On-Time, Overdue).
    4. Updates database record status to 'Completed'.
    """
    if not validate_date_format(actual_harvest_date_str):
        return {"success": False, "message": "Invalid harvest date format. Use YYYY-MM-DD."}
    if not validate_non_negative_number(actual_yield_kg):
        return {"success": False, "message": "Actual harvest weight must be non-negative (>= 0)."}

    records = {r["record_id"]: r for r in db.fetch_joined_records()}
    if record_id not in records:
        return {"success": False, "message": f"Production Record ID #{record_id} not found."}

    record = records[record_id]
    
    if not validate_harvest_after_planting(record["planting_date"], actual_harvest_date_str):
        return {"success": False, "message": f"Harvest date ({actual_harvest_date_str}) cannot precede planting date ({record['planting_date']})."}

    # Calculate yield variance percentage
    variance_pct = calculate_yield_variance_pct(record["predicted_yield_kg"], actual_yield_kg)
    
    # Evaluate harvest timing status
    timing_status = evaluate_harvest_timing(
        actual_harvest_date_str, record["target_min_harvest_date"], record["target_max_harvest_date"]
    )

    # Commit update to SQLite
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE production_records
            SET actual_harvest_date = ?,
                actual_yield_kg = ?,
                yield_variance_pct = ?,
                status = 'Completed'
            WHERE record_id = ?;
        """, (actual_harvest_date_str.strip(), float(actual_yield_kg), variance_pct, record_id))
        conn.commit()

    variance_sign = "+" if variance_pct > 0 else ""
    return {
        "success": True,
        "record_id": record_id,
        "actual_yield_kg": actual_yield_kg,
        "predicted_yield_kg": record["predicted_yield_kg"],
        "variance_pct": variance_pct,
        "timing_status": timing_status,
        "message": f"Harvest logged for Record #{record_id}. Yield: {actual_yield_kg:,.2f} kg (Variance: {variance_sign}{variance_pct:.2f}%, Timing: {timing_status})."
    }

def validate_planting_date_horizon(planting_date_str: str, min_year: int = 2020, max_future_days: int = 365) -> Tuple[bool, str]:
    """
    Task 6 Guard: Enforces planting dates within realistic boundaries:
    - No earlier than Jan 1, 2020
    - No later than 1 year into the future from system clock
    """
    if not validate_date_format(planting_date_str):
        return False, "Invalid date format. Use YYYY-MM-DD."

    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    min_allowed = datetime(min_year, 1, 1)
    max_allowed = datetime.now() + timedelta(days=max_future_days)

    if plant_dt < min_allowed:
        return False, f"Planting date cannot be earlier than {min_year}-01-01."
    if plant_dt > max_allowed:
        return False, f"Planting date cannot be more than 1 year in the future ({max_allowed.strftime('%Y-%m-%d')})."

    return True, "Valid"

def get_dynamic_record_status(status: str, target_max_harvest_date: str) -> str:
    """
    Task 5 Alert: Dynamically tags active records as OVERDUE if target harvest date is past present time.
    """
    if status.strip().lower() == "in progress" and target_max_harvest_date:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str > target_max_harvest_date:
            return "In Progress [OVERDUE]"
    return status

def edit_planting_operation(record_id: int, new_crop_id: int, new_location_id: int, new_planting_date_str: str) -> Dict[str, Any]:
    """
    Task 3 Engine: Modifies planting details and re-runs ML yield prediction.
    """
    is_valid_horizon, err_msg = validate_planting_date_horizon(new_planting_date_str)
    if not is_valid_horizon:
        return {"success": False, "message": err_msg}

    crops = {c["crop_id"]: c for c in db.fetch_all_crops()}
    locations = {l["location_id"]: l for l in db.fetch_all_locations()}

    if new_crop_id not in crops:
        return {"success": False, "message": f"Crop ID #{new_crop_id} not found."}
    if new_location_id not in locations:
        return {"success": False, "message": f"Location ID #{new_location_id} not found."}

    crop = crops[new_crop_id]
    loc = locations[new_location_id]

    target_min, target_max = calculate_target_harvest_window(
        new_planting_date_str, crop["min_growth_days"], crop["max_growth_days"]
    )

    plant_dt = datetime.strptime(new_planting_date_str.strip(), "%Y-%m-%d")
    overlap_ratio, season_tag = compute_pagasa_overlap(
        new_planting_date_str, crop["min_growth_days"], crop["preferred_sub_season"]
    )

    # Fetch active total expenses to estimate budget per hectare
    existing_records = {r['record_id']: r for r in db.fetch_joined_records()}
    existing_rec = existing_records.get(record_id)
    total_exp = existing_rec['total_expenses_php'] if existing_rec else 0.0
    
    budget_per_ha = (total_exp / loc["area_hectares"]) if total_exp > 0 else 25000.0

    new_predicted_yield_kg = ml_model.predict_crop_yield(
        category=crop["category"],
        min_days=crop["min_growth_days"],
        max_days=crop["max_growth_days"],
        area_ha=loc["area_hectares"],
        budget_per_ha=budget_per_ha,
        field_type=loc["field_type"],
        planting_month=plant_dt.month,
        season_overlap_ratio=overlap_ratio
    )

    success = db.update_production_record(
        record_id=record_id,
        crop_id=new_crop_id,
        location_id=new_location_id,
        planting_date_str=new_planting_date_str.strip(),
        target_min=target_min,
        target_max=target_max,
        predicted_yield_kg=new_predicted_yield_kg
    )

    if success:
        return {
            "success": True,
            "message": f"Record #{record_id} updated. Recalculated ML Yield: {new_predicted_yield_kg:,.2f} kg ({season_tag})."
        }
    return {"success": False, "message": "Failed to update record in database."}