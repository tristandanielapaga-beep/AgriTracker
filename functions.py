"""Business workflows and agronomic calculations for Agricultural Tracker."""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

from generate_synthetic_data import calculate_season_overlap_ratio
import database as db
import ml_model


# PAGASA Climate Sub-Season Definition (Philippines)
SUB_SEASON_MONTHS = {
    "Cool Dry": {11, 12, 1, 2},
    "Hot Dry": {3, 4, 5},
    "Wet": {6, 7, 8, 9, 10},
    "Year-Round": set(range(1, 13)),
}


# ---------------------------------------------------------------------------
# 1. Validation helpers
# ---------------------------------------------------------------------------

def validate_date_format(date_str: str) -> bool:
    """Validate strict ISO date format (YYYY-MM-DD)."""
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except (ValueError, AttributeError):
        return False


def validate_harvest_after_planting(planting_date_str: str, harvest_date_str: str) -> bool:
    """Harvest date must be on or after planting date."""
    if not validate_date_format(planting_date_str) or not validate_date_format(harvest_date_str):
        return False
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    harvest_dt = datetime.strptime(harvest_date_str.strip(), "%Y-%m-%d")
    return harvest_dt >= plant_dt


def validate_positive_number(val: Any) -> bool:
    try:
        return float(val) > 0
    except (ValueError, TypeError):
        return False


def validate_non_negative_number(val: Any) -> bool:
    try:
        return float(val) >= 0
    except (ValueError, TypeError):
        return False


def validate_expense_date(
    expense_date_str: str,
    planting_date_str: str,
    actual_harvest_date_str: Optional[str] = None,
    max_pre_days: int = 90,
    max_post_days: int = 30,
) -> Tuple[bool, str]:
    """
    Expense dates may be up to 90 days before planting and up to
    30 days after harvest for completed records.
    """
    if not validate_date_format(expense_date_str):
        return False, "Invalid date format. Use strict zero-padded format YYYY-MM-DD (e.g., 2024-04-12)."

    try:
        exp_dt = datetime.strptime(expense_date_str.strip(), "%Y-%m-%d")
        plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    except ValueError:
        return False, "Invalid calendar date."

    min_allowed_dt = plant_dt - timedelta(days=max_pre_days)
    if exp_dt < min_allowed_dt:
        return False, (
            f"Expense date ({expense_date_str}) is too far in the past. "
            f"Pre-planting expenses are allowed up to {max_pre_days} days "
            f"before planting ({min_allowed_dt.strftime('%Y-%m-%d')})."
        )

    if actual_harvest_date_str:
        harvest_dt = datetime.strptime(actual_harvest_date_str.strip(), "%Y-%m-%d")
        max_allowed_dt = harvest_dt + timedelta(days=max_post_days)
        if exp_dt > max_allowed_dt:
            return False, (
                f"Expense date ({expense_date_str}) cannot exceed {max_post_days} "
                f"days past actual harvest date ({actual_harvest_date_str})."
            )

    return True, "Valid"


# ---------------------------------------------------------------------------
# 2. Agronomic and seasonality calculation engines
# ---------------------------------------------------------------------------

def calculate_target_harvest_window(
    planting_date_str: str, min_days: int, max_days: int
) -> Tuple[str, str]:
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    min_harvest_dt = plant_dt + timedelta(days=int(min_days))
    max_harvest_dt = plant_dt + timedelta(days=int(max_days))
    return min_harvest_dt.strftime("%Y-%m-%d"), max_harvest_dt.strftime("%Y-%m-%d")


def evaluate_harvest_timing(
    actual_harvest_date_str: str, min_harvest_date_str: str, max_harvest_date_str: str
) -> str:
    actual_dt = datetime.strptime(actual_harvest_date_str.strip(), "%Y-%m-%d")
    min_dt = datetime.strptime(min_harvest_date_str.strip(), "%Y-%m-%d")
    max_dt = datetime.strptime(max_harvest_date_str.strip(), "%Y-%m-%d")

    if actual_dt < min_dt:
        return "Premature"
    if min_dt <= actual_dt <= max_dt:
        return "On-Time"
    return "Overdue"


def compute_pagasa_overlap(
    planting_date_str: str, growth_days: int, preferred_sub_season: str
) -> Tuple[float, str]:
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    overlap_ratio = calculate_season_overlap_ratio(
        plant_dt.month, growth_days, preferred_sub_season
    )

    if overlap_ratio >= 0.75:
        seasonality_tag = "In-Season"
    elif overlap_ratio >= 0.40:
        seasonality_tag = "Transition / Partial"
    else:
        seasonality_tag = "Off-Season"
    return overlap_ratio, seasonality_tag


def calculate_yield_variance_pct(predicted_kg: float, actual_kg: float) -> float:
    if predicted_kg <= 0:
        return 0.0
    variance = ((actual_kg - predicted_kg) / predicted_kg) * 100.0
    return round(float(variance), 2)


# ---------------------------------------------------------------------------
# 3. Operational ledger pagination
# ---------------------------------------------------------------------------

def paginate_records(
    records: List[Dict[str, Any]], page: int = 1, page_size: int = 10
) -> Dict[str, Any]:
    total_records = len(records)
    if total_records == 0:
        return {
            "items": [], "current_page": 1, "total_pages": 1,
            "page_size": page_size, "total_records": 0,
        }

    # Avoid division by zero and nonsensical page sizes.
    page_size = max(1, int(page_size))
    total_pages = (total_records + page_size - 1) // page_size
    current_page = max(1, min(int(page), total_pages))
    start_idx = (current_page - 1) * page_size
    return {
        "items": records[start_idx:start_idx + page_size],
        "current_page": current_page,
        "total_pages": total_pages,
        "page_size": page_size,
        "total_records": total_records,
    }


# ---------------------------------------------------------------------------
# 4. Catalog workflows
# ---------------------------------------------------------------------------

def add_crop_type(
    crop_name: str, category: str, min_growth_days: int,
    max_growth_days: int, preferred_sub_season: str, user_id: int,
) -> Dict[str, Any]:
    """Admin-only direct catalog registration."""
    if not crop_name.strip():
        return {"success": False, "message": "Crop name cannot be empty."}
    if min_growth_days <= 0 or max_growth_days < min_growth_days:
        return {"success": False, "message": "Invalid growth duration ranges."}
    if preferred_sub_season not in SUB_SEASON_MONTHS:
        return {"success": False, "message": "Invalid PAGASA sub-season target."}

    try:
        new_id = db.add_crop_catalog_item(
            crop_name.strip(), category.strip(), int(min_growth_days),
            int(max_growth_days), preferred_sub_season.strip(), user_id,
        )
        return {
            "success": True,
            "message": f"Crop '{crop_name}' registered successfully.",
            "crop_id": new_id,
        }
    except db.psycopg.errors.UniqueViolation:
        return {"success": False, "message": f"Crop name '{crop_name}' already exists in catalog."}


def add_farm_location(
    location_name: str, field_type: str, area_hectares: float, user_id: int,
) -> Dict[str, Any]:
    """Admin-only direct location registration."""
    if not location_name.strip():
        return {"success": False, "message": "Location name cannot be empty."}
    if not validate_positive_number(area_hectares):
        return {"success": False, "message": "Area in hectares must be strictly positive (> 0)."}

    try:
        new_id = db.add_location_catalog_item(
            location_name.strip(), field_type.strip(), float(area_hectares), user_id
        )
        return {
            "success": True,
            "message": f"Location '{location_name}' registered successfully.",
            "location_id": new_id,
        }
    except db.psycopg.errors.UniqueViolation:
        return {"success": False, "message": f"Location '{location_name}' already exists."}


def request_crop_type(
    crop_name: str, category: str, min_growth_days: int,
    max_growth_days: int, preferred_sub_season: str, user_id: int,
) -> Dict[str, Any]:
    """Allow an active user to submit a crop for administrator review."""
    if not crop_name.strip():
        return {"success": False, "message": "Crop name cannot be empty."}
    if min_growth_days <= 0 or max_growth_days < min_growth_days:
        return {"success": False, "message": "Invalid growth duration ranges."}
    if preferred_sub_season not in SUB_SEASON_MONTHS:
        return {"success": False, "message": "Invalid PAGASA sub-season target."}
    request_id = db.submit_crop_request(
        user_id, crop_name.strip(), category.strip(), int(min_growth_days),
        int(max_growth_days), preferred_sub_season.strip(),
    )
    return {
        "success": True, "request_id": request_id,
        "message": f"Crop request #{request_id} submitted for administrator review.",
    }


def request_farm_location(
    location_name: str, field_type: str, area_hectares: float, user_id: int,
) -> Dict[str, Any]:
    """Allow an active user to submit a location for administrator review."""
    if not location_name.strip():
        return {"success": False, "message": "Location name cannot be empty."}
    if not validate_positive_number(area_hectares):
        return {"success": False, "message": "Area in hectares must be strictly positive (> 0)."}
    request_id = db.submit_location_request(
        user_id, location_name.strip(), field_type.strip(), float(area_hectares)
    )
    return {
        "success": True, "request_id": request_id,
        "message": f"Location request #{request_id} submitted for administrator review.",
    }


# ---------------------------------------------------------------------------
# 5. Production workflows
# ---------------------------------------------------------------------------

def create_planting_operation(
    crop_id: int,
    location_id: int,
    planting_date_str: str,
    user_id: int,
    initial_budget_php: float = 0.0,
    initial_expense_description: str = "Initial Land Prep & Planting",
) -> Dict[str, Any]:
    """
    Create a planting and its optional initial expense atomically.
    The authenticated user's ID is stored as created_by on both records.
    """
    if not validate_date_format(planting_date_str):
        return {"success": False, "message": "Invalid planting date format. Use YYYY-MM-DD."}
    if not validate_non_negative_number(initial_budget_php):
        return {"success": False, "message": "Initial budget must be non-negative."}

    # Validate the account before doing prediction work.
    with db.get_connection() as conn:
        db._get_active_user_role(conn, user_id)

    crops = {c["crop_id"]: c for c in db.fetch_all_crops()}
    locations = {l["location_id"]: l for l in db.fetch_all_locations()}
    if crop_id not in crops:
        return {"success": False, "message": f"Crop ID {crop_id} not found."}
    if location_id not in locations:
        return {"success": False, "message": f"Location ID {location_id} not found."}

    crop = crops[crop_id]
    loc = locations[location_id]
    target_min, target_max = calculate_target_harvest_window(
        planting_date_str, crop["min_growth_days"], crop["max_growth_days"]
    )
    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    overlap_ratio, season_tag = compute_pagasa_overlap(
        planting_date_str, crop["min_growth_days"], crop["preferred_sub_season"]
    )

    area_ha = float(loc["area_hectares"])
    budget = float(initial_budget_php)
    budget_per_ha = budget / area_ha if budget > 0 else 25000.0

    predicted_yield_kg = ml_model.predict_crop_yield(
        category=crop["category"],
        min_days=crop["min_growth_days"],
        max_days=crop["max_growth_days"],
        area_ha=area_ha,
        budget_per_ha=budget_per_ha,
        field_type=loc["field_type"],
        planting_month=plant_dt.month,
        season_overlap_ratio=overlap_ratio,
    )

    # One transaction: production record, optional expense, and both audit entries.
    with db.get_connection() as conn:
        db._get_active_user_role(conn, user_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO production_records (
                    crop_id, location_id, planting_date,
                    target_min_harvest_date, target_max_harvest_date,
                    predicted_yield_kg, actual_yield_kg, yield_variance_pct,
                    total_expenses_php, status, is_historical, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, 0.0, 0.0, %s, 'In Progress', 0, %s)
                RETURNING record_id
                """,
                (crop_id, location_id, planting_date_str.strip(), target_min,
                 target_max, predicted_yield_kg, budget, user_id),
            )
            record_id = cur.fetchone()["record_id"]

            db.log_action(
                conn, user_id, "CREATE_PRODUCTION_RECORD", "production_records",
                record_id, {
                    "crop_id": crop_id, "location_id": location_id,
                    "planting_date": planting_date_str.strip(),
                    "predicted_yield_kg": float(predicted_yield_kg),
                },
            )

            if budget > 0:
                cur.execute(
                    """
                    INSERT INTO production_expenses (
                        record_id, expense_category, description,
                        amount_php, date_logged, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING expense_id
                    """,
                    (record_id, "Seeds/Seedlings", initial_expense_description,
                     budget, planting_date_str.strip(), user_id),
                )
                expense_id = cur.fetchone()["expense_id"]
                db.log_action(
                    conn, user_id, "ADD_EXPENSE", "production_expenses", expense_id,
                    {
                        "record_id": record_id, "category": "Seeds/Seedlings",
                        "description": initial_expense_description,
                        "amount_php": budget,
                    },
                )

    return {
        "success": True,
        "record_id": record_id,
        "predicted_yield_kg": predicted_yield_kg,
        "target_min_harvest_date": target_min,
        "target_max_harvest_date": target_max,
        "seasonality_tag": season_tag,
        "season_overlap_ratio": overlap_ratio,
        "message": (
            f"Planting logged successfully (Record #{record_id}). "
            f"ML Predicted Yield: {predicted_yield_kg:,.2f} kg ({season_tag})."
        ),
    }


def record_harvest_completion(
    record_id: int, actual_harvest_date_str: str,
    actual_yield_kg: float, user_id: int,
) -> Dict[str, Any]:
    """Validate, calculate, complete, and audit a harvest record."""
    if not validate_date_format(actual_harvest_date_str):
        return {"success": False, "message": "Invalid harvest date format. Use YYYY-MM-DD."}
    if not validate_non_negative_number(actual_yield_kg):
        return {"success": False, "message": "Actual harvest weight must be non-negative (>= 0)."}

    record = db.fetch_joined_record_by_id(record_id, user_id)
    if record is None:
        return {"success": False, "message": f"Production Record ID #{record_id} not found."}

    if not validate_harvest_after_planting(record["planting_date"], actual_harvest_date_str):
        return {
            "success": False,
            "message": (
                f"Harvest date ({actual_harvest_date_str}) cannot precede "
                f"planting date ({record['planting_date']})."
            ),
        }

    variance_pct = calculate_yield_variance_pct(
        float(record["predicted_yield_kg"]), float(actual_yield_kg)
    )
    timing_status = evaluate_harvest_timing(
        actual_harvest_date_str,
        record["target_min_harvest_date"],
        record["target_max_harvest_date"],
    )

    with db.get_connection() as conn:
        locked_record = db._authorize_record_access(conn, record_id, user_id)
        if locked_record["status"] != "In Progress":
            return {"success": False, "message": "This production record is not In Progress."}

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE production_records
                SET actual_harvest_date = %s, actual_yield_kg = %s,
                    yield_variance_pct = %s, status = 'Completed'
                WHERE record_id = %s
                """,
                (actual_harvest_date_str.strip(), float(actual_yield_kg),
                 variance_pct, record_id),
            )

        db.log_action(
            conn, user_id, "COMPLETE_HARVEST", "production_records", record_id,
            {
                "actual_harvest_date": actual_harvest_date_str.strip(),
                "actual_yield_kg": float(actual_yield_kg),
                "yield_variance_pct": variance_pct,
                "timing_status": timing_status,
            },
        )

    variance_sign = "+" if variance_pct > 0 else ""
    return {
        "success": True,
        "record_id": record_id,
        "actual_yield_kg": actual_yield_kg,
        "predicted_yield_kg": record["predicted_yield_kg"],
        "variance_pct": variance_pct,
        "timing_status": timing_status,
        "message": (
            f"Harvest logged for Record #{record_id}. Yield: {actual_yield_kg:,.2f} kg "
            f"(Variance: {variance_sign}{variance_pct:.2f}%, Timing: {timing_status})."
        ),
    }


def validate_planting_date_horizon(
    planting_date_str: str, min_year: int = 2020, max_future_days: int = 365
) -> Tuple[bool, str]:
    """Planting date must be >= 2020-01-01 and no more than one year ahead."""
    if not validate_date_format(planting_date_str):
        return False, "Invalid date format. Use YYYY-MM-DD."

    plant_dt = datetime.strptime(planting_date_str.strip(), "%Y-%m-%d")
    min_allowed = datetime(min_year, 1, 1)
    max_allowed = datetime.now() + timedelta(days=max_future_days)
    if plant_dt < min_allowed:
        return False, f"Planting date cannot be earlier than {min_year}-01-01."
    if plant_dt > max_allowed:
        return False, (
            f"Planting date cannot be more than 1 year in the future "
            f"({max_allowed.strftime('%Y-%m-%d')})."
        )
    return True, "Valid"


def get_dynamic_record_status(status: str, target_max_harvest_date: str) -> str:
    """Tag active records as overdue when the target maximum date has passed."""
    if status.strip().lower() == "in progress" and target_max_harvest_date:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str > target_max_harvest_date:
            return "In Progress [OVERDUE]"
    return status


def edit_planting_operation(
    record_id: int, new_crop_id: int, new_location_id: int,
    new_planting_date_str: str, user_id: int,
) -> Dict[str, Any]:
    """Modify planting details and recalculate the ML yield prediction."""
    is_valid_horizon, err_msg = validate_planting_date_horizon(new_planting_date_str)
    if not is_valid_horizon:
        return {"success": False, "message": err_msg}

    existing_rec = db.fetch_joined_record_by_id(record_id, user_id)
    if existing_rec is None:
        return {"success": False, "message": f"Production Record ID #{record_id} not found."}

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

    total_exp = float(existing_rec["total_expenses_php"] or 0)
    budget_per_ha = total_exp / float(loc["area_hectares"]) if total_exp > 0 else 25000.0
    new_predicted_yield_kg = ml_model.predict_crop_yield(
        category=crop["category"],
        min_days=crop["min_growth_days"],
        max_days=crop["max_growth_days"],
        area_ha=loc["area_hectares"],
        budget_per_ha=budget_per_ha,
        field_type=loc["field_type"],
        planting_month=plant_dt.month,
        season_overlap_ratio=overlap_ratio,
    )

    success = db.update_production_record(
        record_id=record_id,
        crop_id=new_crop_id,
        location_id=new_location_id,
        planting_date_str=new_planting_date_str.strip(),
        target_min=target_min,
        target_max=target_max,
        predicted_yield_kg=new_predicted_yield_kg,
        user_id=user_id,
    )
    if success:
        return {
            "success": True,
            "message": (
                f"Record #{record_id} updated. Recalculated ML Yield: "
                f"{new_predicted_yield_kg:,.2f} kg ({season_tag})."
            ),
        }
    return {"success": False, "message": "Failed to update record in database."}
