import os
import sys
from typing import List, Dict, Any

import database as db
import functions as fn
import analytics as an


def clear_screen():
    """Clears the terminal console for a clean view."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Renders a standardized terminal section header."""
    print("=" * 85)
    print(f"   {title.upper()}")
    print("=" * 85)


def render_ledger_table(items: List[Dict[str, Any]], current_page: int, total_pages: int, total_records: int):
    """Renders a paginated summary ledger table directly in the terminal."""
    print("\n" + "=" * 115)
    print(f"                                AGRICULTURAL PRODUCTION LEDGER (Page {current_page} of {total_pages} | Total: {total_records})")
    print("=" * 115)
    print(f"{'ID':<4} | {'Crop Name':<16} | {'Location':<25} | {'Area (ha)':<9} | {'Planted':<10} | {'Pred (kg)':<10} | {'Actual (kg)':<11} | {'Var %':<7} | {'Expenses (₱)':<12} | {'Status'}")
    print("-" * 115)

    if not items:
        print("                                   [ No production records found ]")
    else:
        for r in items:
            var_str = f"{r['yield_variance_pct']:+.1f}%" if r['status'] == 'Completed' else "N/A"
            actual_str = f"{r['actual_yield_kg']:,.2f}" if r['status'] == 'Completed' else "Pending"
            loc_name = (r['location_name'][:22] + "..") if len(r['location_name']) > 24 else r['location_name']
            crop_name = (r['crop_name'][:14] + "..") if len(r['crop_name']) > 16 else r['crop_name']

            print(
                f"{r['record_id']:<4} | "
                f"{crop_name:<16} | "
                f"{loc_name:<25} | "
                f"{r['area_hectares']:<9.2f} | "
                f"{r['planting_date']:<10} | "
                f"{r['predicted_yield_kg']:<10,.2f} | "
                f"{actual_str:<11} | "
                f"{var_str:<7} | "
                f"₱{r['total_expenses_php']:<11,.2f} | "
                f"{r['status']}"
            )
    print("=" * 115)


def view_ledger_workflow():
    """Interactive paginated ledger viewer workflow."""
    current_page = 1
    page_size = 10

    while True:
        clear_screen()
        all_records = db.fetch_joined_records()
        pagination = fn.paginate_records(all_records, page=current_page, page_size=page_size)

        render_ledger_table(
            items=pagination["items"],
            current_page=pagination["current_page"],
            total_pages=pagination["total_pages"],
            total_records=pagination["total_records"]
        )

        print("\nNavigation: [N]ext Page | [P]revious Page | [I]nspect Record Details | [B]ack to Main Menu")
        choice = input("Select an option: ").strip().lower()

        if choice == 'n':
            if current_page < pagination["total_pages"]:
                current_page += 1
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
        elif choice == 'i':
            rec_id_str = input("\nEnter Record ID to inspect: ").strip()
            if rec_id_str.isdigit():
                inspect_record_details(int(rec_id_str))
                input("\nPress Enter to return to ledger...")
        elif choice == 'b':
            break


def inspect_record_details(record_id: int):
    """Displays full agronomic, seasonality, and expense details for a specific record."""
    records = {r["record_id"]: r for r in db.fetch_joined_records()}
    if record_id not in records:
        print(f"\n[!] Record ID #{record_id} does not exist.")
        return

    r = records[record_id]
    overlap_ratio, season_tag = fn.compute_pagasa_overlap(
        r["planting_date"], r["min_growth_days"], r["preferred_sub_season"]
    )
    expenses = db.fetch_expenses_by_record(record_id)

    print("\n" + "=" * 75)
    print(f"               DETAILED OPERATIONAL RECORD INSPECTOR (ID #{record_id})")
    print("=" * 75)
    print(f" Crop Variety:          {r['crop_name']} (Category: {r['category']})")
    print(f" Target Sub-Season:     {r['preferred_sub_season']} (Calculated Overlap: {season_tag} - {overlap_ratio*100:.1f}%)")
    print(f" Farm Location:         {r['location_name']} ({r['field_type']})")
    print(f" Plot Area:             {r['area_hectares']:.2f} hectares")
    print(f" Planting Date:         {r['planting_date']}")
    print(f" Expected Growth Span:  {r['min_growth_days']} - {r['max_growth_days']} days")
    print(f" Target Harvest Window: {r['target_min_harvest_date']} to {r['target_max_harvest_date']}")
    print(f" Actual Harvest Date:   {r['actual_harvest_date'] if r['actual_harvest_date'] else 'In Progress / Pending'}")
    print(f" ML Predicted Yield:    {r['predicted_yield_kg']:,.2f} kg")
    print(f" Actual Harvest Yield:  {r['actual_yield_kg']:,.2f} kg")
    print(f" Yield Prediction Var:  {r['yield_variance_pct']:+.2f}%")
    print(f" Status:                {r['status']}")
    print("-" * 75)
    print(" ITEMIZED EXPENSE LOGS:")
    if not expenses:
        print("   (No itemized expenses logged for this record)")
    else:
        for e in expenses:
            print(f"   [{e['date_logged']}] {e['expense_category']:<25} | ₱{e['amount_php']:<10,.2f} | {e['description']}")
    print(f" TOTAL CUMULATIVE EXPENSES: ₱{r['total_expenses_php']:,.2f}")
    print("=" * 75)


def search_records_workflow():
    """Filters records by Year, Category, or Keyword."""
    clear_screen()
    print_header("Search & Filter Production Records")

    print("[1] Filter by Year")
    print("[2] Filter by Crop Category")
    print("[3] Search by Crop Name or Location Name")
    print("[4] Back to Main Menu")

    choice = input("\nSelect filter type (1-4): ").strip()
    all_records = db.fetch_joined_records()
    filtered = []

    if choice == '1':
        year_str = input("Enter Year (e.g., 2024, 2025, 2026): ").strip()
        filtered = [r for r in all_records if r['planting_date'].startswith(year_str)]
    elif choice == '2':
        cat_str = input("Enter Category (Grains, Vegetables, Fruits, Root Crops / Tubers, Legumes / Pulses): ").strip().lower()
        filtered = [r for r in all_records if cat_str in r['category'].lower()]
    elif choice == '3':
        kw = input("Enter search keyword (Crop or Location): ").strip().lower()
        filtered = [r for r in all_records if kw in r['crop_name'].lower() or kw in r['location_name'].lower()]
    elif choice == '4':
        return
    else:
        print("\n[!] Invalid selection.")
        input("Press Enter to continue...")
        return

    pagination = fn.paginate_records(filtered, page=1, page_size=20)
    render_ledger_table(pagination["items"], 1, 1, pagination["total_records"])
    input("\nPress Enter to return to main menu...")


def log_planting_workflow():
    """Interactive workflow for creating a new planting record."""
    clear_screen()
    print_header("Log New Planting Operation")

    crops = db.fetch_all_crops()
    locations = db.fetch_all_locations()

    if not crops or not locations:
        print("[!] Catalog error: Crops or Locations empty.")
        input("Press Enter to return...")
        return

    print("AVAILABLE CROP VARIETIES:")
    for c in crops:
        print(f"  [{c['crop_id']}] {c['crop_name']:<22} | Category: {c['category']:<20} | Target: {c['preferred_sub_season']}")

    try:
        crop_id = int(input("\nSelect Crop ID: ").strip())
    except ValueError:
        print("[!] Invalid Crop ID.")
        input("Press Enter to return...")
        return

    print("\nSAVED FARM LOCATIONS / PLOTS:")
    for l in locations:
        print(f"  [{l['location_id']}] {l['location_name']:<32} | Field: {l['field_type']:<22} | Area: {l['area_hectares']:.2f} ha")

    try:
        location_id = int(input("\nSelect Location ID: ").strip())
    except ValueError:
        print("[!] Invalid Location ID.")
        input("Press Enter to return...")
        return

    planting_date = input("Enter Planting Date (YYYY-MM-DD): ").strip()
    if not fn.validate_date_format(planting_date):
        print("[!] Invalid date format. Must be YYYY-MM-DD.")
        input("Press Enter to return...")
        return

    budget_str = input("Enter Initial Budget / Capital Allocation in PHP (₱) [Default 0.00]: ").strip()
    budget = float(budget_str) if budget_str and fn.validate_non_negative_number(budget_str) else 0.0

    result = fn.create_planting_operation(
        crop_id=crop_id,
        location_id=location_id,
        planting_date_str=planting_date,
        initial_budget_php=budget
    )

    if result["success"]:
        print(f"\n[+] SUCCESS: {result['message']}")
    else:
        print(f"\n[!] ERROR: {result['message']}")
    input("\nPress Enter to return to main menu...")


def log_harvest_workflow():
    """Interactive workflow for updating a record upon harvest completion."""
    clear_screen()
    print_header("Log Harvest Output (Complete Record)")

    active_records = [r for r in db.fetch_joined_records() if r['status'] == 'In Progress']
    if not active_records:
        print("[!] No 'In Progress' production records available for harvest logging.")
        input("\nPress Enter to return...")
        return

    print("ACTIVE OPERATIONS (IN PROGRESS):")
    for r in active_records:
        print(f"  [{r['record_id']}] {r['crop_name']} at {r['location_name']} (Planted: {r['planting_date']})")

    try:
        rec_id = int(input("\nSelect Record ID to update: ").strip())
    except ValueError:
        print("[!] Invalid Record ID.")
        input("Press Enter to return...")
        return

    harvest_date = input("Enter Actual Harvest Date (YYYY-MM-DD): ").strip()
    actual_kg_str = input("Enter Actual Harvest Weight in Kilograms (kg): ").strip()

    if not fn.validate_non_negative_number(actual_kg_str):
        print("[!] Invalid harvest weight.")
        input("Press Enter to return...")
        return

    result = fn.record_harvest_completion(
        record_id=rec_id,
        actual_harvest_date_str=harvest_date,
        actual_yield_kg=float(actual_kg_str)
    )

    if result["success"]:
        print(f"\n[+] SUCCESS: {result['message']}")
    else:
        print(f"\n[!] ERROR: {result['message']}")
    input("\nPress Enter to return to main menu...")


def manage_expenses_workflow():
    """Interactive console for viewing, adding, editing, and deleting itemized expenses."""
    clear_screen()
    print_header("Manage Itemized Production Expenses")

    all_records = db.fetch_joined_records()
    records_dict = {r['record_id']: r for r in all_records}

    if not all_records:
        print("[!] No production records available.")
        input("Press Enter to return...")
        return

    print("PRODUCTION RECORDS:")
    for r in all_records:
        print(f"  [{r['record_id']}] {r['crop_name']} at {r['location_name']} (Total Expenses: ₱{r['total_expenses_php']:,.2f})")

    try:
        rec_id = int(input("\nSelect Record ID to manage expenses: ").strip())
    except ValueError:
        print("[!] Invalid Record ID.")
        input("Press Enter to return...")
        return

    if rec_id not in records_dict:
        print(f"[!] Record ID #{rec_id} not found.")
        input("Press Enter to return...")
        return

    while True:
        clear_screen()
        target_rec = {r['record_id']: r for r in db.fetch_joined_records()}[rec_id]
        expenses = db.fetch_expenses_by_record(rec_id)

        print_header(f"Expense Log Manager for Record #{rec_id} ({target_rec['crop_name']})")
        print(f" Farm Location: {target_rec['location_name']} | Planting Date: {target_rec['planting_date']}")
        print(f" Current Total Expenses: ₱{target_rec['total_expenses_php']:,.2f}\n")
        print("ITEMIZED EXPENSES:")
        print(f" {'ID':<4} | {'Date':<10} | {'Category':<25} | {'Amount (₱)':<12} | {'Description'}")
        print("-" * 75)

        if not expenses:
            print("  (No itemized expenses logged for this record)")
        else:
            for e in expenses:
                print(f" [{e['expense_id']:<2}] | {e['date_logged']} | {e['expense_category']:<25} | ₱{e['amount_php']:<11,.2f} | {e['description']}")
        print("-" * 75)

        print("\nOptions: [A]dd Expense | [E]dit Expense | [D]elete Expense | [B]ack to Main Menu")
        choice = input("Select an option: ").strip().lower()

        categories = [
            'Seeds/Seedlings', 'Fertilizer/Soil Inputs', 'Pesticides/Crop Protection',
            'Labor/Workforce', 'Fuel/Irrigation/Utilities', 'Equipment/Maintenance', 'Other'
        ]

        if choice == 'a':
            print("\n--- ADD NEW EXPENSE ITEM ---")
            print("EXPENSE CATEGORIES:")
            for idx, cat in enumerate(categories, 1):
                print(f"  [{idx}] {cat}")
            try:
                cat_idx = int(input("Select Category ID: ").strip()) - 1
                selected_cat = categories[cat_idx]
            except (ValueError, IndexError):
                print("[!] Invalid Category selection.")
                input("Press Enter to continue...")
                continue

            desc = input("Enter Description: ").strip()
            amount_str = input("Enter Amount in PHP (₱): ").strip()
            date_str = input("Enter Expense Date (YYYY-MM-DD): ").strip()

            if not fn.validate_positive_number(amount_str):
                print("[!] Invalid amount. Must be positive.")
                input("Press Enter to continue...")
                continue

            is_valid_date, date_err = fn.validate_expense_date(
                expense_date_str=date_str,
                planting_date_str=target_rec['planting_date'],
                actual_harvest_date_str=target_rec['actual_harvest_date']
            )
            if not is_valid_date:
                print(f"\n[!] DATE ERROR: {date_err}")
                input("Press Enter to continue...")
                continue

            db.add_itemized_expense(rec_id, selected_cat, desc, float(amount_str), date_str)
            print("[+] Expense line item added successfully!")
            input("Press Enter to continue...")

        elif choice == 'e':
            if not expenses:
                print("[!] No expenses to edit.")
                input("Press Enter to continue...")
                continue
            try:
                exp_id = int(input("\nEnter Expense Line Item ID to Edit: ").strip())
            except ValueError:
                print("[!] Invalid Expense ID.")
                input("Press Enter to continue...")
                continue

            exp_dict = {e['expense_id']: e for e in expenses}
            if exp_id not in exp_dict:
                print(f"[!] Expense ID #{exp_id} not found.")
                input("Press Enter to continue...")
                continue

            target_exp = exp_dict[exp_id]
            print(f"\nEditing Expense #{exp_id} ({target_exp['description']}):")
            print("EXPENSE CATEGORIES:")
            for idx, cat in enumerate(categories, 1):
                print(f"  [{idx}] {cat}")
            try:
                cat_idx = int(input(f"Select Category ID [Current: {target_exp['expense_category']}]: ").strip()) - 1
                selected_cat = categories[cat_idx]
            except (ValueError, IndexError):
                print("[!] Invalid Category selection.")
                input("Press Enter to continue...")
                continue

            desc = input(f"Enter Description [Current: '{target_exp['description']}']: ").strip() or target_exp['description']
            amount_str = input(f"Enter Amount in PHP [Current: ₱{target_exp['amount_php']:,.2f}]: ").strip()
            amount = float(amount_str) if amount_str and fn.validate_positive_number(amount_str) else target_exp['amount_php']
            
            date_str = input(f"Enter Date [Current: {target_exp['date_logged']}]: ").strip() or target_exp['date_logged']

            is_valid_date, date_err = fn.validate_expense_date(
                expense_date_str=date_str,
                planting_date_str=target_rec['planting_date'],
                actual_harvest_date_str=target_rec['actual_harvest_date']
            )
            if not is_valid_date:
                print(f"\n[!] DATE ERROR: {date_err}")
                input("Press Enter to continue...")
                continue

            db.update_itemized_expense(exp_id, selected_cat, desc, amount, date_str)
            print(f"[+] Expense #{exp_id} updated successfully!")
            input("Press Enter to continue...")

        elif choice == 'd':
            if not expenses:
                print("[!] No expenses to delete.")
                input("Press Enter to continue...")
                continue
            try:
                exp_id = int(input("\nEnter Expense Line Item ID to Delete: ").strip())
            except ValueError:
                print("[!] Invalid Expense ID.")
                input("Press Enter to continue...")
                continue

            exp_dict = {e['expense_id']: e for e in expenses}
            if exp_id not in exp_dict:
                print(f"[!] Expense ID #{exp_id} not found.")
                input("Press Enter to continue...")
                continue

            target_exp = exp_dict[exp_id]
            confirm = input(f"Are you sure you want to delete expense '{target_exp['description']}' (₱{target_exp['amount_php']:,.2f})? (y/n): ").strip().lower()
            if confirm == 'y':
                db.delete_itemized_expense(exp_id)
                print(f"[+] Expense #{exp_id} deleted successfully.")
            else:
                print("[*] Deletion cancelled.")
            input("Press Enter to continue...")

        elif choice == 'b':
            break

def delete_record_workflow():
    """Deletes a record with strict confirmation guard."""
    clear_screen()
    print_header("Delete Production Record")

    all_records = db.fetch_joined_records()
    if not all_records:
        print("[!] No records available for deletion.")
        input("Press Enter to return...")
        return

    for r in all_records:
        print(f"  [{r['record_id']}] {r['crop_name']} at {r['location_name']} (Planted: {r['planting_date']})")

    try:
        rec_id = int(input("\nEnter Record ID to delete: ").strip())
    except ValueError:
        print("[!] Invalid Record ID.")
        input("Press Enter to return...")
        return

    records_dict = {r['record_id']: r for r in all_records}
    if rec_id not in records_dict:
        print(f"[!] Record ID #{rec_id} not found.")
        input("Press Enter to return...")
        return

    target = records_dict[rec_id]
    print(f"\n[WARNING] Are you sure you want to delete Record #{rec_id} ({target['crop_name']} at {target['location_name']})?")
    confirm = input("Type 'DELETE' to confirm deletion: ").strip()

    if confirm == "DELETE":
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM production_records WHERE record_id = ?;", (rec_id,))
            conn.commit()
        print(f"\n[+] SUCCESS: Record #{rec_id} deleted successfully.")
    else:
        print("\n[*] Deletion cancelled.")
    input("\nPress Enter to return to main menu...")


def register_crop_workflow():
    """Adds a new crop variety to the database catalog."""
    clear_screen()
    print_header("Register New Crop Variety")

    crop_name = input("Enter Crop Name (e.g., Sweet Potato): ").strip()
    
    categories = ['Grains', 'Vegetables', 'Fruits', 'Root Crops / Tubers', 'Legumes / Pulses']
    print("\nCATEGORIES:")
    for idx, c in enumerate(categories, 1):
        print(f"  [{idx}] {c}")
    try:
        cat_idx = int(input("Select Category ID: ").strip()) - 1
        selected_cat = categories[cat_idx]
    except (ValueError, IndexError):
        print("[!] Invalid category selection.")
        input("Press Enter to return...")
        return

    sub_seasons = ['Cool Dry', 'Hot Dry', 'Wet', 'Year-Round']
    print("\nPAGASA PREFERRED SUB-SEASONS:")
    for idx, s in enumerate(sub_seasons, 1):
        print(f"  [{idx}] {s}")
    try:
        s_idx = int(input("Select Sub-Season ID: ").strip()) - 1
        selected_sub_season = sub_seasons[s_idx]
    except (ValueError, IndexError):
        print("[!] Invalid sub-season selection.")
        input("Press Enter to return...")
        return

    try:
        min_days = int(input("Enter Minimum Growth Days: ").strip())
        max_days = int(input("Enter Maximum Growth Days: ").strip())
    except ValueError:
        print("[!] Invalid growth duration inputs.")
        input("Press Enter to return...")
        return

    res = fn.add_crop_type(crop_name, selected_cat, min_days, max_days, selected_sub_season)
    if res["success"]:
        print(f"\n[+] SUCCESS: {res['message']}")
    else:
        print(f"\n[!] ERROR: {res['message']}")
    input("\nPress Enter to return to main menu...")


def register_location_workflow():
    """Adds a new farm location plot to the database catalog."""
    clear_screen()
    print_header("Register New Farm Location Plot")

    loc_name = input("Enter Plot / Location Name: ").strip()
    
    field_types = ['Irrigated Lowland', 'Rainfed Upland', 'Greenhouse/Controlled']
    print("\nFIELD TYPES:")
    for idx, f in enumerate(field_types, 1):
        print(f"  [{idx}] {f}")
    try:
        f_idx = int(input("Select Field Type ID: ").strip()) - 1
        selected_field = field_types[f_idx]
    except (ValueError, IndexError):
        print("[!] Invalid field type selection.")
        input("Press Enter to return...")
        return

    area_str = input("Enter Area in Hectares: ").strip()
    if not fn.validate_positive_number(area_str):
        print("[!] Invalid area value.")
        input("Press Enter to return...")
        return

    res = fn.add_farm_location(loc_name, selected_field, float(area_str))
    if res["success"]:
        print(f"\n[+] SUCCESS: {res['message']}")
    else:
        print(f"\n[!] ERROR: {res['message']}")
    input("\nPress Enter to return to main menu...")


def analytics_and_charts_workflow():
    """Executes analytics summaries and generates Matplotlib charts."""
    clear_screen()
    print_header("Executive Analytics & Visual Charts")

    an.print_cli_analytics_report()

    print("\n[1] Generate All 7 Visual Analytical Charts (Saved to charts/)")
    print("[2] Filter Analytics Report by Year")
    print("[3] Back to Main Menu")

    choice = input("\nSelect an option (1-3): ").strip()
    if choice == '1':
        print("\nGenerating charts...")
        files = an.generate_all_charts()
        print(f"\n[+] Charts successfully generated and saved to 'charts/':")
        for k, filepath in files.items():
            print(f"  - {filepath}")
        input("\nPress Enter to continue...")
    elif choice == '2':
        year_str = input("\nEnter Year to filter (e.g., 2024, 2025, 2026): ").strip()
        clear_screen()
        an.print_cli_analytics_report(year=year_str)
        input("\nPress Enter to continue...")


def main():
    """Program Entry Point: Initializes DB and runs main menu loop."""
    db.init_db()

    while True:
        clear_screen()
        print("=" * 85)
        print("           AGRICULTURAL PRODUCTION TRACKER & YIELD PREDICTION SYSTEM")
        print("                 DSA 214 - Programming for Data Science Project")
        print("=" * 85)
        print("  [1] View Production Ledger (Paginated Ledger)")
        print("  [2] Search / Filter Production Records")
        print("  [3] Log New Planting Operation (With ML Yield Prediction)")
        print("  [4] Log Harvest Output (Complete Active Record)")
        print("  [5] Manage Production Expenses")
        print("  [6] Register New Crop Variety")
        print("  [7] Register New Farm Location Plot")
        print("  [8] Delete Production Record")
        print("  [9] View Executive Analytics & Generate Charts")
        print(" [10] Exit System")
        print("=" * 85)

        choice = input("Select an option (1-10): ").strip()

        if choice == '1':
            view_ledger_workflow()
        elif choice == '2':
            search_records_workflow()
        elif choice == '3':
            log_planting_workflow()
        elif choice == '4':
            log_harvest_workflow()
        elif choice == '5':
            manage_expenses_workflow()
        elif choice == '6':
            register_crop_workflow()
        elif choice == '7':
            register_location_workflow()
        elif choice == '8':
            delete_record_workflow()
        elif choice == '9':
            analytics_and_charts_workflow()
        elif choice == '10':
            print("\n[+] Exiting Agricultural Tracker System safely. Goodbye!")
            sys.exit(0)
        else:
            print("\n[!] Invalid choice. Please enter a number from 1 to 10.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()