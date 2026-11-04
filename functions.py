from datetime import datetime
import database
import os

def clear_screen():
    """Utility function to clear text in terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_non_empty_string(prompt):
    """Prompt user for input and validate that it is not blank."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Error: Input cannot be empty. Please try again.")


def get_positive_float(prompt, allow_zero=False):
    """Prompt user and validate a positive floating-point number."""
    while True:
        try:
            val_str = input(prompt).strip()
            val = float(val_str)
            if allow_zero and val >= 0:
                return val
            elif not allow_zero and val > 0:
                return val
            else:
                msg = "zero or greater" if allow_zero else "greater than zero"
                print(f"Error: Value must be {msg}.")
        except ValueError:
            print("Error: Invalid number format. Please enter a valid decimal number.")


def get_valid_date(prompt, allow_optional=False):
    """Prompt user and validate date string format (YYYY-MM-DD)."""
    while True:
        date_str = input(prompt).strip()
        if allow_optional and not date_str:
            return None  # Represents ongoing/unharvested crop
            
        try:
            valid_date = datetime.strptime(date_str, "%Y-%m-%d")
            return valid_date.strftime("%Y-%m-%d")
        except ValueError:
            print("Error: Date must be in YYYY-MM-DD format (e.g., 2026-05-15).")


def select_crop_from_menu():
    """Display available crops from the database and prompt user to select one."""
    crops = database.fetch_all_crops()
    if not crops:
        print("No crops found in the database.")
        return None

    print("\n--- Available Crops ---")
    for crop in crops:
        print(f"[{crop['crop_id']}] {crop['crop_name']} ({crop['category']}) - Growth: {crop['typical_growth_days']} days")
    
    valid_ids = [crop['crop_id'] for crop in crops]
    while True:
        try:
            selected_id = int(input("\nSelect Crop ID: ").strip())
            if selected_id in valid_ids:
                return selected_id
            print("Error: Selected Crop ID does not exist.")
        except ValueError:
            print("Error: Please enter a valid numerical ID.")


def add_new_production_record():
    """Gather and validate inputs before saving a new record to the database."""
    print("\n--- Add New Production Record ---")
    crop_id = select_crop_from_menu()
    if not crop_id:
        return

    location = get_non_empty_string("Enter Farm Location (e.g., Field Alpha): ")
    area = get_positive_float("Enter Area Size in Hectares: ")
    planting_date = get_valid_date("Enter Planting Date (YYYY-MM-DD): ")
    
    is_harvested = input("Has this crop been harvested yet? (y/n): ").strip().lower()
    if is_harvested == 'y':
        harvest_date = get_valid_date("Enter Harvest Date (YYYY-MM-DD): ")
        harvest_qty = get_positive_float("Enter Harvest Quantity (kg): ", allow_zero=True)
    else:
        harvest_date = None
        harvest_qty = 0.0

    cost = get_positive_float("Enter Total Production Cost ($/PHP): ", allow_zero=True)

    record_id = database.insert_production_record(
        crop_id, location, area, planting_date, harvest_date, harvest_qty, cost
    )
    print(f"\nSuccess: Production Record #{record_id} saved successfully!")


def view_all_records():
    """Fetch and display stored production records in a clean tabular view."""
    records = database.fetch_joined_records()
    if not records:
        print("\nNo records found in the database.")
        return

    print("\n" + "-" * 95)
    print(f"{'ID':<4} | {'Crop Name':<18} | {'Category':<10} | {'Location':<18} | {'Harvest Date':<12} | {'Qty (kg)':<9} | {'Cost':<10}")
    print("-" * 95)

    for row in records:
        print(f"{row['record_id']:<4} | {row['crop_name']:<18} | {row['category']:<10} | {row['farm_location']:<18} | {row['harvest_status']:<12} | {row['harvest_qty_kg']:<9.1f} | {row['production_cost']:<10.2f}")
    print("-" * 95)


def delete_record_interactive():
    """Prompt for a record ID, request confirmation, and delete it."""
    view_all_records()
    try:
        rec_id = int(input("\nEnter Record ID to delete (or 0 to cancel): ").strip())
        if rec_id == 0:
            print("Deletion cancelled.")
            return

        confirm = input(f"Are you sure you want to delete Record #{rec_id}? (y/n): ").strip().lower()
        if confirm == 'y':
            success = database.delete_record_by_id(rec_id)
            if success:
                print(f"Record #{rec_id} deleted successfully.")
            else:
                print(f"Error: Record #{rec_id} was not found.")
        else:
            print("Deletion cancelled.")
    except ValueError:
        print("Error: Invalid Record ID input.")
        
def search_records_interactive():
    """Prompt user for a search query and display matching records."""
    query = input("Enter search term (Crop Name, Category, or Location): ").strip()
    if not query:
        print("Search cancelled or blank query entered.")
        return

    results = database.search_records(query)
    if not results:
        print(f"\nNo records matched '{query}'.")
        return

    print(f"\n--- Search Results for '{query}' ---")
    print("-" * 95)
    print(f"{'ID':<4} | {'Crop Name':<18} | {'Category':<10} | {'Location':<18} | {'Harvest Date':<12} | {'Qty (kg)':<9} | {'Cost':<10}")
    print("-" * 95)
    for row in results:
        print(f"{row['record_id']:<4} | {row['crop_name']:<18} | {row['category']:<10} | {row['farm_location']:<18} | {row['harvest_status']:<12} | {row['harvest_qty_kg']:<9.1f} | {row['production_cost']:<10.2f}")
    print("-" * 95)


def update_record_interactive():
    """Prompt user to update harvest details for a given record ID."""
    view_all_records()
    try:
        rec_id = int(input("\nEnter Record ID to update harvest details (0 to cancel): ").strip())
        if rec_id == 0:
            return

        harvest_date = get_valid_date("Enter Harvest Date (YYYY-MM-DD): ")
        harvest_qty = get_positive_float("Enter Harvest Quantity (kg): ", allow_zero=True)

        success = database.update_harvest_record(rec_id, harvest_date, harvest_qty)
        if success:
            print(f"Success: Record #{rec_id} harvest details updated!")
        else:
            print(f"Error: Record #{rec_id} was not found.")
    except ValueError:
        print("Error: Invalid Record ID.")