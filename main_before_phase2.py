import os
import sys
from typing import List, Dict, Any
from getpass import getpass

import database_backup as db
import functions_backup as fn
import analytics as an
import auth


def clear_screen():
    """Clears the terminal console for a clean view."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Renders a standardized terminal section header."""
    print("=" * 85)
    print(f"   {title.upper()}")
    print("=" * 85)


def render_ledger_table(items: List[Dict[str, Any]], current_page: int, total_pages: int, total_records: int):
    """Renders tabular ledger view with dynamic OVERDUE tags."""
    print("=" * 115)
    print(f"                                AGRICULTURAL PRODUCTION LEDGER (Page {current_page} of {total_pages} | Total: {total_records})")
    print("=" * 115)
    print(f"{'ID':<4} | {'Crop Name':<16} | {'Location':<25} | {'Area (ha)':<9} | {'Planted':<10} | {'Pred (kg)':<10} | {'Actual (kg)':<11} | {'Expenses (₱)':<12} | {'Status'}")
    print("-" * 115)

    if not items:
        print("  (No production records found matching criteria)")
    else:
        for r in items:
            crop_disp = (r['crop_name'][:13] + '..') if len(r['crop_name']) > 15 else r['crop_name']
            loc_disp = (r['location_name'][:22] + '..') if len(r['location_name']) > 24 else r['location_name']
            act_yield_str = f"{r['actual_yield_kg']:,.2f}" if r['status'] == 'Completed' else "Pending"
            
            # Dynamic Overdue Tagging
            dyn_status = fn.get_dynamic_record_status(r['status'], r['target_max_harvest_date'])

            print(f"{r['record_id']:<4} | {crop_disp:<16} | {loc_disp:<25} | {r['area_hectares']:<9.2f} | {r['planting_date']} | {r['predicted_yield_kg']:<10,.2f} | {act_yield_str:<11} | ₱{r['total_expenses_php']:<11,.2f} | {dyn_status}")

    print("=" * 115)


def edit_record_workflow():
    """Interactive workflow for editing planting metadata of existing operations."""
    clear_screen()
    print_header("Edit Production Record Metadata")

    all_records = db.fetch_joined_records()
    records_dict = {r['record_id']: r for r in all_records}

    if not all_records:
        print("[!] No records available to edit.")
        input("Press Enter to return...")
        return

    try:
        rec_id = int(input("Enter Production Record ID to Edit: ").strip())
    except ValueError:
        print("[!] Invalid Record ID.")
        input("Press Enter to return...")
        return

    if rec_id not in records_dict:
        print(f"[!] Record ID #{rec_id} not found.")
        input("Press Enter to return...")
        return

    target = records_dict[rec_id]
    print(f"\nEditing Record #{rec_id} (Current Crop: {target['crop_name']} | Location: {target['location_name']} | Planted: {target['planting_date']}):")

    crops = db.fetch_all_crops()
    locations = db.fetch_all_locations()

    print("\nAVAILABLE CROPS:")
    for c in crops:
        print(f"  [{c['crop_id']}] {c['crop_name']} ({c['category']})")
    try:
        crop_id_input = input(f"Select Crop ID [Current: {target['crop_id']}]: ").strip()
        new_crop_id = int(crop_id_input) if crop_id_input else target['crop_id']
    except ValueError:
        print("[!] Invalid Crop Selection.")
        input("Press Enter to return...")
        return

    print("\nAVAILABLE LOCATIONS:")
    for l in locations:
        print(f"  [{l['location_id']}] {l['location_name']} ({l['area_hectares']} ha)")
    try:
        loc_id_input = input(f"Select Location ID [Current: {target['location_id']}]: ").strip()
        new_loc_id = int(loc_id_input) if loc_id_input else target['location_id']
    except ValueError:
        print("[!] Invalid Location Selection.")
        input("Press Enter to return...")
        return

    new_date = input(f"Enter Planting Date YYYY-MM-DD [Current: {target['planting_date']}]: ").strip() or target['planting_date']

    res = fn.edit_planting_operation(rec_id, new_crop_id, new_loc_id, new_date)

    if res["success"]:
        print(f"\n[+] SUCCESS: {res['message']}")
    else:
        print(f"\n[!] UPDATE FAILED: {res['message']}")

    input("\nPress Enter to return to main menu...")


def view_ledger_workflow():
    """Interactive paginated ledger with Jump-to-Page, Dynamic Sorting, and Direct Search."""
    current_page = 1
    page_size = 10
    current_sort_field = "record_id"
    current_sort_dir = "ASC"
    search_keyword = ""

    while True:
        clear_screen()
        # Fetch records sorted by active sort field
        all_records = db.fetch_joined_records(order_by=current_sort_field, order_dir=current_sort_dir)
        
        # Apply active inline search filter
        if search_keyword:
            kw = search_keyword.lower()
            all_records = [
                r for r in all_records
                if kw in str(r['record_id'])
                or kw in r['crop_name'].lower()
                or kw in r['location_name'].lower()
                or kw in r['status'].lower()
                or kw in r['planting_date']
            ]

        pagination = fn.paginate_records(all_records, page=current_page, page_size=page_size)

        render_ledger_table(
            items=pagination["items"],
            current_page=pagination["current_page"],
            total_pages=pagination["total_pages"],
            total_records=pagination["total_records"]
        )

        filter_status_str = f" [Filter: '{search_keyword}']" if search_keyword else ""
        sort_status_str = f" [Sorted by: {current_sort_field} {current_sort_dir}]"
        print(f"Active Controls:{sort_status_str}{filter_status_str}")
        print("\nNavigation: [N]ext | [P]rev | [J]ump Page | [S]ort Field | [F]ilter / Search | [I]nspect | [B]ack")
        choice = input("Select option: ").strip().lower()

        if choice == 'n':
            if current_page < pagination["total_pages"]:
                current_page += 1
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
        elif choice == 'j':
            try:
                target_p = int(input(f"Enter Page Number (1-{pagination['total_pages']}): ").strip())
                if 1 <= target_p <= pagination["total_pages"]:
                    current_page = target_p
                else:
                    print("[!] Out of bounds page number.")
                    input("Press Enter...")
            except ValueError:
                print("[!] Invalid input.")
                input("Press Enter...")
        elif choice == 's':
            print("\nSORT FIELDS: [1] Record ID | [2] Planting Date | [3] Crop Name | [4] Location | [5] Expenses")
            s_choice = input("Select sort field (1-5): ").strip()
            field_map = {'1': 'record_id', '2': 'planting_date', '3': 'crop_name', '4': 'location_name', '5': 'total_expenses_php'}
            if s_choice in field_map:
                current_sort_field = field_map[s_choice]
                d_choice = input("Direction: [1] Ascending (ASC) | [2] Descending (DESC): ").strip()
                current_sort_dir = "DESC" if d_choice == '2' else "ASC"
                current_page = 1
        elif choice == 'f':
            kw_input = input("\nEnter search keyword (or press Enter to clear filter): ").strip()
            search_keyword = kw_input
            current_page = 1
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
    """Interactive paginated search and filter workflow for production records."""
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
        input("Press Enter...")
        return

    # Clean paginated loop for the pre-filtered results subset
    current_page = 1
    page_size = 10

    while True:
        clear_screen()
        pagination = fn.paginate_records(filtered, page=current_page, page_size=page_size)

        render_ledger_table(
            items=pagination["items"],
            current_page=pagination["current_page"],
            total_pages=pagination["total_pages"],
            total_records=pagination["total_records"]
        )

        print("\nNavigation: [N]ext | [P]rev | [J]ump Page | [I]nspect Record | [B]ack to Search Menu")
        sub_choice = input("Select option: ").strip().lower()

        if sub_choice == 'n':
            if current_page < pagination["total_pages"]:
                current_page += 1
        elif sub_choice == 'p':
            if current_page > 1:
                current_page -= 1
        elif sub_choice == 'j':
            try:
                target_p = int(input(f"Enter Page Number (1-{pagination['total_pages']}): ").strip())
                if 1 <= target_p <= pagination["total_pages"]:
                    current_page = target_p
            except ValueError:
                pass
        elif sub_choice == 'i':
            rec_id_str = input("\nEnter Record ID to inspect: ").strip()
            if rec_id_str.isdigit():
                inspect_record_details(int(rec_id_str))
                input("\nPress Enter to return...")
        elif sub_choice == 'b':
            break


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
    """Interactive paginated console with sorting and filtering for logging harvest output on active records."""
    current_page = 1
    page_size = 10
    current_sort_field = "record_id"
    current_sort_dir = "ASC"
    search_keyword = ""

    while True:
        clear_screen()
        # Fetch records, optionally filtering specifically for 'In Progress' active records or all
        all_records = db.fetch_joined_records(order_by=current_sort_field, order_dir=current_sort_dir)

        # Apply active inline keyword filter
        if search_keyword:
            kw = search_keyword.lower()
            all_records = [
                r for r in all_records
                if kw in str(r['record_id'])
                or kw in r['crop_name'].lower()
                or kw in r['location_name'].lower()
                or kw in r['status'].lower()
                or kw in r['planting_date']
            ]

        pagination = fn.paginate_records(all_records, page=current_page, page_size=page_size)

        print_header("Log Harvest Output & Complete Active Records")
        print(f"Select Active Record to Log Harvest (Page {pagination['current_page']} of {pagination['total_pages']} | Total: {pagination['total_records']}):\n")
        print(f" {'ID':<4} | {'Crop Name':<16} | {'Location':<25} | {'Planted':<10} | {'Status':<10}")
        print("-" * 80)

        if not pagination["items"]:
            print("  (No production records found matching criteria)")
        else:
            for r in pagination["items"]:
                crop_disp = (r['crop_name'][:13] + '..') if len(r['crop_name']) > 15 else r['crop_name']
                loc_disp = (r['location_name'][:22] + '..') if len(r['location_name']) > 24 else r['location_name']
                print(f" [{r['record_id']:<3}] | {crop_disp:<16} | {loc_disp:<25} | {r['planting_date']} | {r['status']:<10}")
        
        print("-" * 80)
        sort_status = f"[Sorted by: {current_sort_field} {current_sort_dir}]"
        filter_status = f"[Filter: '{search_keyword}']" if search_keyword else ""
        print(f"Active Controls: {sort_status} {filter_status}")
        print("\nNavigation: [N]ext | [P]rev | [J]ump Page | [S]ort Field | [F]ilter Keyword | [ID] Select Record | [B]ack")
        choice = input("Select option: ").strip().lower()

        if choice == 'n':
            if current_page < pagination["total_pages"]:
                current_page += 1
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
        elif choice == 'j':
            try:
                target_p = int(input(f"Enter Page Number (1-{pagination['total_pages']}): ").strip())
                if 1 <= target_p <= pagination["total_pages"]:
                    current_page = target_p
            except ValueError:
                pass
        elif choice == 's':
            print("\nSORT FIELDS: [1] Record ID | [2] Crop Name | [3] Location | [4] Planting Date | [5] Status")
            s_choice = input("Select sort field (1-5): ").strip()
            field_map = {'1': 'record_id', '2': 'crop_name', '3': 'location_name', '4': 'planting_date', '5': 'status'}
            if s_choice in field_map:
                current_sort_field = field_map[s_choice]
                d_choice = input("Direction: [1] Ascending (ASC) | [2] Descending (DESC): ").strip()
                current_sort_dir = "DESC" if d_choice == '2' else "ASC"
                current_page = 1
        elif choice == 'f':
            kw_input = input("\nEnter search keyword (or press Enter to clear): ").strip()
            search_keyword = kw_input
            current_page = 1
        elif choice.isdigit():
            rec_id = int(choice)
            target = db.fetch_joined_record_by_id(rec_id)
            if target is not None:
                print(f"\nSelected Record #{rec_id}: {target['crop_name']} at {target['location_name']}")
                print(f"Current Status: {target['status']} | Predicted Yield: {target['predicted_yield_kg']:,.2f} kg")
                
                actual_yield_str = input("Enter Actual Harvest Yield (kg): ").strip()
                actual_date_str = input("Enter Actual Harvest Date (YYYY-MM-DD): ").strip()
                
                if fn.validate_non_negative_number(actual_yield_str):
                    actual_yield = float(actual_yield_str)
                    result = fn.record_harvest_completion(rec_id, actual_date_str, actual_yield)
                    print(f"[+] {result['message']}" if result["success"] else f"[!] {result['message']}")
                else:
                    print("[!] Invalid yield amount entered.")
                input("Press Enter to continue...")
            else:
                print(f"[!] Record ID #{rec_id} not found.")
                input("Press Enter...")
        elif choice == 'b':
            break


def manage_expenses_workflow():
    """Interactive paginated console with sorting and filtering for managing itemized production expenses."""
    current_page = 1
    page_size = 10
    current_sort_field = "record_id"
    current_sort_dir = "ASC"
    search_keyword = ""

    while True:
        clear_screen()
        all_records = db.fetch_joined_records(order_by=current_sort_field, order_dir=current_sort_dir)

        # Apply active inline keyword filter
        if search_keyword:
            kw = search_keyword.lower()
            all_records = [
                r for r in all_records
                if kw in str(r['record_id'])
                or kw in r['crop_name'].lower()
                or kw in r['location_name'].lower()
                or kw in str(r['total_expenses_php'])
            ]

        pagination = fn.paginate_records(all_records, page=current_page, page_size=page_size)

        print_header("Manage Itemized Production Expenses")
        print(f"Select a Production Record (Page {pagination['current_page']} of {pagination['total_pages']} | Total: {pagination['total_records']}):\n")
        print(f" {'ID':<4} | {'Crop Name':<16} | {'Location':<25} | {'Total Expenses (₱)'}")
        print("-" * 75)

        if not pagination["items"]:
            print("  (No production records found matching criteria)")
        else:
            for r in pagination["items"]:
                crop_disp = (r['crop_name'][:13] + '..') if len(r['crop_name']) > 15 else r['crop_name']
                loc_disp = (r['location_name'][:22] + '..') if len(r['location_name']) > 24 else r['location_name']
                print(f" [{r['record_id']:<3}] | {crop_disp:<16} | {loc_disp:<25} | ₱{r['total_expenses_php']:<12,.2f}")
        
        print("-" * 75)
        sort_status = f"[Sorted by: {current_sort_field} {current_sort_dir}]"
        filter_status = f"[Filter: '{search_keyword}']" if search_keyword else ""
        print(f"Active Controls: {sort_status} {filter_status}")
        print("\nNavigation: [N]ext | [P]rev | [J]ump Page | [S]ort Field | [F]ilter Keyword | [ID] Select Record | [B]ack")
        choice = input("Select option: ").strip().lower()

        if choice == 'n':
            if current_page < pagination["total_pages"]:
                current_page += 1
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
        elif choice == 'j':
            try:
                target_p = int(input(f"Enter Page Number (1-{pagination['total_pages']}): ").strip())
                if 1 <= target_p <= pagination["total_pages"]:
                    current_page = target_p
            except ValueError:
                pass
        elif choice == 's':
            print("\nSORT FIELDS: [1] Record ID | [2] Crop Name | [3] Location | [4] Total Expenses")
            s_choice = input("Select sort field (1-4): ").strip()
            field_map = {'1': 'record_id', '2': 'crop_name', '3': 'location_name', '4': 'total_expenses_php'}
            if s_choice in field_map:
                current_sort_field = field_map[s_choice]
                d_choice = input("Direction: [1] Ascending (ASC) | [2] Descending (DESC): ").strip()
                current_sort_dir = "DESC" if d_choice == '2' else "ASC"
                current_page = 1
        elif choice == 'f':
            kw_input = input("\nEnter search keyword (or press Enter to clear): ").strip()
            search_keyword = kw_input
            current_page = 1
        elif choice.isdigit():
            rec_id = int(choice)
            records_dict = {r['record_id']: r for r in db.fetch_joined_records()}
            if rec_id in records_dict:
                _run_expense_item_manager(rec_id)
            else:
                print(f"[!] Record ID #{rec_id} not found.")
                input("Press Enter...")
        elif choice == 'b':
            break
        
def _run_expense_item_manager(rec_id: int):
    """Sub-loop for managing expense line items for a specific record."""
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

        print("\nOptions: [A]dd Expense | [E]dit Expense | [D]elete Expense | [B]ack")
        choice = input("Select an option: ").strip().lower()

        categories = [
            'Seeds/Seedlings', 'Fertilizer/Soil Inputs', 'Pesticides/Crop Protection',
            'Labor/Workforce', 'Fuel/Irrigation/Utilities', 'Equipment/Maintenance', 'Other'
        ]

        if choice == 'a':
            print("\n--- ADD NEW EXPENSE ITEM ---")
            for idx, cat in enumerate(categories, 1):
                print(f"  [{idx}] {cat}")
            try:
                cat_idx = int(input("Select Category ID: ").strip()) - 1
                selected_cat = categories[cat_idx]
            except (ValueError, IndexError):
                print("[!] Invalid Category selection.")
                input("Press Enter...")
                continue

            desc = input("Enter Description: ").strip()
            amount_str = input("Enter Amount in PHP (₱): ").strip()
            date_str = input("Enter Expense Date (YYYY-MM-DD): ").strip()

            if not fn.validate_positive_number(amount_str):
                print("[!] Invalid amount.")
                input("Press Enter...")
                continue

            is_valid_date, date_err = fn.validate_expense_date(
                expense_date_str=date_str,
                planting_date_str=target_rec['planting_date'],
                actual_harvest_date_str=target_rec['actual_harvest_date']
            )
            if not is_valid_date:
                print(f"\n[!] DATE ERROR: {date_err}")
                input("Press Enter...")
                continue

            db.add_itemized_expense(rec_id, selected_cat, desc, float(amount_str), date_str)
            print("[+] Expense line item added successfully!")
            input("Press Enter...")

        elif choice == 'e':
            if not expenses:
                print("[!] No expenses to edit.")
                input("Press Enter...")
                continue
            try:
                exp_id = int(input("\nEnter Expense Line Item ID to Edit: ").strip())
            except ValueError:
                print("[!] Invalid Expense ID.")
                input("Press Enter...")
                continue

            exp_dict = {e['expense_id']: e for e in expenses}
            if exp_id not in exp_dict:
                print(f"[!] Expense ID #{exp_id} not found.")
                input("Press Enter...")
                continue

            target_exp = exp_dict[exp_id]
            print(f"\nEditing Expense #{exp_id}:")
            for idx, cat in enumerate(categories, 1):
                print(f"  [{idx}] {cat}")
            try:
                cat_idx = int(input(f"Select Category ID [Current: {target_exp['expense_category']}]: ").strip()) - 1
                selected_cat = categories[cat_idx]
            except (ValueError, IndexError):
                selected_cat = target_exp['expense_category']

            desc = input(f"Enter Description [Current: '{target_exp['description']}']: ").strip() or target_exp['description']
            amount_str = input(f"Enter Amount in PHP [Current: ₱{target_exp['amount_php']:,.2f}]: ").strip()
            amount = float(amount_str) if amount_str and fn.validate_positive_number(amount_str) else target_exp['amount_php']
            date_str = input(f"Enter Date [Current: {target_exp['date_logged']}]: ").strip() or target_exp['date_logged']

            db.update_itemized_expense(exp_id, selected_cat, desc, amount, date_str)
            print(f"[+] Expense #{exp_id} updated successfully!")
            input("Press Enter...")

        elif choice == 'd':
            if not expenses:
                print("[!] No expenses to delete.")
                input("Press Enter...")
                continue
            try:
                exp_id = int(input("\nEnter Expense Line Item ID to Delete: ").strip())
            except ValueError:
                print("[!] Invalid Expense ID.")
                input("Press Enter...")
                continue

            if input(f"Confirm deletion of Expense #{exp_id}? (y/n): ").strip().lower() == 'y':
                db.delete_itemized_expense(exp_id)
                print(f"[+] Expense #{exp_id} deleted.")
                input("Press Enter...")

        elif choice == 'b':
            break
        
def delete_record_workflow():
    """Interactive paginated console with sorting and filtering for deleting production records."""
    current_page = 1
    page_size = 10
    current_sort_field = "record_id"
    current_sort_dir = "ASC"
    search_keyword = ""

    while True:
        clear_screen()
        all_records = db.fetch_joined_records(order_by=current_sort_field, order_dir=current_sort_dir)

        # Apply active inline keyword filter
        if search_keyword:
            kw = search_keyword.lower()
            all_records = [
                r for r in all_records
                if kw in str(r['record_id'])
                or kw in r['crop_name'].lower()
                or kw in r['location_name'].lower()
                or kw in r['status'].lower()
                or kw in r['planting_date']
            ]

        pagination = fn.paginate_records(all_records, page=current_page, page_size=page_size)

        print_header("Delete Production Records")
        print(f"Select Record to Delete (Page {pagination['current_page']} of {pagination['total_pages']} | Total: {pagination['total_records']}):\n")
        print(f" {'ID':<4} | {'Crop Name':<16} | {'Location':<25} | {'Status':<10}")
        print("-" * 65)

        if not pagination["items"]:
            print("  (No production records found matching criteria)")
        else:
            for r in pagination["items"]:
                crop_disp = (r['crop_name'][:13] + '..') if len(r['crop_name']) > 15 else r['crop_name']
                loc_disp = (r['location_name'][:22] + '..') if len(r['location_name']) > 24 else r['location_name']
                print(f" [{r['record_id']:<3}] | {crop_disp:<16} | {loc_disp:<25} | {r['status']:<10}")
        
        print("-" * 65)
        sort_status = f"[Sorted by: {current_sort_field} {current_sort_dir}]"
        filter_status = f"[Filter: '{search_keyword}']" if search_keyword else ""
        print(f"Active Controls: {sort_status} {filter_status}")
        print("\nNavigation: [N]ext | [P]rev | [J]ump Page | [S]ort Field | [F]ilter Keyword | [ID] Delete Record | [B]ack")
        choice = input("Select option: ").strip().lower()

        if choice == 'n':
            if current_page < pagination["total_pages"]:
                current_page += 1
        elif choice == 'p':
            if current_page > 1:
                current_page -= 1
        elif choice == 'j':
            try:
                target_p = int(input(f"Enter Page Number (1-{pagination['total_pages']}): ").strip())
                if 1 <= target_p <= pagination["total_pages"]:
                    current_page = target_p
            except ValueError:
                pass
        elif choice == 's':
            print("\nSORT FIELDS: [1] Record ID | [2] Crop Name | [3] Location | [4] Status")
            s_choice = input("Select sort field (1-4): ").strip()
            field_map = {'1': 'record_id', '2': 'crop_name', '3': 'location_name', '4': 'status'}
            if s_choice in field_map:
                current_sort_field = field_map[s_choice]
                d_choice = input("Direction: [1] Ascending (ASC) | [2] Descending (DESC): ").strip()
                current_sort_dir = "DESC" if d_choice == '2' else "ASC"
                current_page = 1
        elif choice == 'f':
            kw_input = input("\nEnter search keyword (or press Enter to clear): ").strip()
            search_keyword = kw_input
            current_page = 1
        elif choice.isdigit():
            rec_id = int(choice)
            target = db.fetch_joined_record_by_id(rec_id)
            if target is not None:
                confirm = input(f"Are you sure you want to delete Record #{rec_id} ({target['crop_name']} at {target['location_name']})? This will also remove child expenses. (y/n): ").strip().lower()
                if confirm == 'y':
                    if db.delete_production_record(rec_id):
                        print(f"[+] Record #{rec_id} deleted successfully.")
                    else:
                        print(f"[!] Record #{rec_id} could not be deleted.")
                    input("Press Enter to continue...")
            else:
                print(f"[!] Record ID #{rec_id} not found.")
                input("Press Enter...")
        elif choice == 'b':
            break


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

def login_workflow():
    """Authenticates a user before granting access to the application."""

    while True:
        clear_screen()
        print("=" * 85)
        print("           AGRICULTURAL PRODUCTION TRACKER & YIELD PREDICTION SYSTEM")
        print("                         USER AUTHENTICATION")
        print("=" * 85)

        username = input("\nUsername: ").strip()
        password = getpass("Password: ")

        try:
            user = auth.authenticate_user(username, password)

            if user is not None:
                print(f"\n[+] Welcome, {user['full_name']}!")
                print(f"[+] Account Role: {user['role'].upper()}")
                input("\nPress Enter to continue...")
                return user

            print("\n[!] Invalid username or password, or account is inactive.")

        except Exception as error:
            print(f"\n[!] Authentication error: {error}")

        print("\n[1] Try Again")
        print("[2] Exit Application")

        choice = input("\nSelect an option: ").strip()

        if choice == '2':
            return None

def main():
    """Program Entry Point: Initializes DB, authenticates users, and runs the main menu."""

    db.init_db()

    while True:

        # Require authentication before entering the application.
        current_user = login_workflow()

        if current_user is None:
            print("\n[+] Exiting Agricultural Tracker System. Goodbye!")
            return

        # Main application menu.
        while True:
            clear_screen()

            print("=" * 85)
            print("           AGRICULTURAL PRODUCTION TRACKER & YIELD PREDICTION SYSTEM")
            print("                 DSA 214 - Programming for Data Science Project")
            print("=" * 85)

            print(
                f"  Logged in as: {current_user['full_name']} "
                f"({current_user['role'].upper()})"
            )

            print("-" * 85)

            print("  [1] View Production Ledger (Paginated Ledger)")
            print("  [2] Search / Filter Production Records")
            print("  [3] Log New Planting Operation (With ML Yield Prediction)")
            print("  [4] Log Harvest Output (Complete Active Record)")
            print("  [5] Manage Production Expenses")
            print("  [6] Register New Crop Variety")
            print("  [7] Register New Farm Location Plot")
            print("  [8] Delete Production Record")
            print("  [9] View Executive Analytics & Generate Charts")
            print(" [10] Logout")
            print(" [11] Exit System")

            print("=" * 85)

            choice = input("Select an option (1-11): ").strip()

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
                print(
                    f"\n[+] Logging out {current_user['username']}..."
                )
                break

            elif choice == '11':
                print("\n[+] Exiting Agricultural Tracker System safely. Goodbye!")
                return

            else:
                print("\n[!] Invalid choice. Please enter a number from 1 to 11.")
                input("Press Enter to continue...")




if __name__ == "__main__":
    main()