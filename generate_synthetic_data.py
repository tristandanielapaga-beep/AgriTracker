import os
import numpy as np
import pandas as pd

# PAGASA Sub-Season Month Mappings (Philippines)
SUB_SEASON_MONTHS = {
    "Cool Dry": {11, 12, 1, 2},
    "Hot Dry": {3, 4, 5},
    "Wet": {6, 7, 8, 9, 10},
    "Year-Round": set(range(1, 13))
}

def calculate_season_overlap_ratio(planting_month: int, growth_days: int, preferred_sub_season: str) -> float:
    """
    Calculates the proportion of growth days (0.0 to 1.0) that fall inside 
    the crop's preferred PAGASA climate sub-season.
    """
    preferred_months = SUB_SEASON_MONTHS.get(preferred_sub_season, set(range(1, 13)))
    
    # 30-day month approximation starting mid-month (day 15)
    matched_days = 0
    for day in range(growth_days):
        current_month = ((planting_month - 1) + (day // 30)) % 12 + 1
        if current_month in preferred_months:
            matched_days += 1
            
    return round(matched_days / growth_days, 4)

def generate_historical_dataset(num_samples: int = 1500, filename: str = "data/historical_farm_data.csv"):
    """
    Generates domain-informed synthetic historical farm records across 5 agricultural categories
    to pre-train the yield prediction regression model (expanded to 1,500 samples).
    """
    os.makedirs("data", exist_ok=True)
    np.random.seed(42)  # Fixed seed for reproducible benchmarks

    categories = [
        "Grains", 
        "Vegetables", 
        "Fruits", 
        "Root Crops / Tubers", 
        "Legumes / Pulses"
    ]
    
    field_types = [
        "Irrigated Lowland", 
        "Rainfed Upland", 
        "Greenhouse/Controlled"
    ]

    # Baseline yield range (kg per hectare) by biological category
    category_yield_base = {
        "Grains": (3500, 5500),
        "Vegetables": (8000, 16000),
        "Fruits": (12000, 25000),
        "Root Crops / Tubers": (10000, 20000),
        "Legumes / Pulses": (1200, 2800)
    }

    # Preferred sub-season options mapped by category for dataset simulation
    category_sub_seasons = {
        "Grains": ["Wet", "Hot Dry"],
        "Vegetables": ["Cool Dry", "Hot Dry", "Wet"],
        "Fruits": ["Year-Round", "Hot Dry"],
        "Root Crops / Tubers": ["Wet", "Year-Round"],
        "Legumes / Pulses": ["Cool Dry", "Hot Dry"]
    }

    field_multipliers = {
        "Irrigated Lowland": 1.25,
        "Rainfed Upland": 0.85,
        "Greenhouse/Controlled": 1.45
    }

    data = []
    for _ in range(num_samples):
        cat = str(np.random.choice(categories))
        field = str(np.random.choice(field_types))
        sub_season = str(np.random.choice(category_sub_seasons[cat]))
        
        # Maturity duration ranges per category
        if cat == "Grains":
            min_days, max_days = int(np.random.choice([80, 100])), int(np.random.choice([100, 120]))
        elif cat == "Vegetables":
            min_days, max_days = int(np.random.choice([50, 60])), int(np.random.choice([70, 90]))
        elif cat == "Fruits":
            min_days, max_days = int(np.random.choice([200, 270])), int(np.random.choice([300, 365]))
        elif cat == "Root Crops / Tubers":
            min_days, max_days = int(np.random.choice([120, 150])), int(np.random.choice([180, 240]))
        else:  # Legumes / Pulses
            min_days, max_days = int(np.random.choice([50, 60])), int(np.random.choice([75, 90]))

        area_ha = round(float(np.random.uniform(0.5, 5.0)), 2)
        budget_per_ha = round(float(np.random.uniform(15000, 65000)), 2)
        planting_month = int(np.random.randint(1, 13))

        # Calculate exact growth day overlap ratio with target sub-season
        overlap_ratio = calculate_season_overlap_ratio(planting_month, min_days, sub_season)

        # 1. Base Yield Baseline
        base_low, base_high = category_yield_base[cat]
        base_yield_ha = np.random.uniform(base_low, base_high)
        
        # 2. Environmental Field Multiplier
        field_mult = field_multipliers[field]
        
        # 3. Logarithmic Diminishing Returns on Budget Spending
        budget_factor = 0.7 + 0.5 * (np.log10(budget_per_ha) - np.log10(15000))
        
        # 4. 3-Tier Seasonality Overlap Multiplier
        if overlap_ratio >= 0.75:
            season_mult = 1.15   # In-Season boost (+15%)
        elif overlap_ratio >= 0.40:
            season_mult = 0.95   # Partial / Transition penalty (-5%)
        else:
            season_mult = 0.75   # Off-Season penalty (-25%)
        
        # 5. Stochastic Environmental Noise (+/- 10%)
        noise = np.random.uniform(0.90, 1.10)

        # Compute simulated total yield mass in kilograms
        final_yield_kg = round(
            base_yield_ha * area_ha * field_mult * budget_factor * season_mult * noise, 
            2
        )

        data.append({
            "category": cat,
            "min_growth_days": min_days,
            "max_growth_days": max_days,
            "area_hectares": area_ha,
            "budget_per_hectare": budget_per_ha,
            "field_type": field,
            "planting_month": planting_month,
            "season_overlap_ratio": overlap_ratio,
            "actual_yield_kg": final_yield_kg
        })

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"[+] Successfully generated {num_samples} historical farm records in '{filename}'.")

if __name__ == "__main__":
    generate_historical_dataset()