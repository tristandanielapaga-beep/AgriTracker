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
            records_dict = {r['record_id']: r for r in db.fetch_joined_records()}
            if rec_id in records_dict:
                target = records_dict[rec_id]
                print(f"\nSelected Record #{rec_id}: {target['crop_name']} at {target['location_name']}")
                print(f"Current Status: {target['status']} | Predicted Yield: {target['predicted_yield_kg']:,.2f} kg")
                
                actual_yield_str = input("Enter Actual Harvest Yield (kg): ").strip()
                actual_date_str = input("Enter Actual Harvest Date (YYYY-MM-DD): ").strip()
                
                if fn.validate_positive_number(actual_yield_str):
                    actual_yield = float(actual_yield_str)
                    db.update_harvest_output(rec_id, actual_yield, actual_date_str, status="Completed")
                    print(f"[+] Harvest successfully logged and Record #{rec_id} marked as Completed!")
                else:
                    print("[!] Invalid yield amount entered.")
                input("Press Enter to continue...")
            else:
                print(f"[!] Record ID #{rec_id} not found.")
                input("Press Enter...")
        elif choice == 'b':
            break