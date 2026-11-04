import sys
import database
import functions
import analytics


def display_menu():
    """Print the main CLI navigation menu."""
    print("==================================================")
    print("    AGRICULTURAL PRODUCTION TRACKER - DSA 214     ")
    print("==================================================")
    print("  [1] View All Production Records")
    print("  [2] Add New Production Record")
    print("  [3] Search Records by Crop or Category")
    print("  [4] Update Record Harvest Data")
    print("  [5] Delete Production Record")
    print("  [6] View Analytical Summaries")
    print("  [7] Generate & View Charts")
    print("  [8] Exit Application")
    print("==================================================")


def main():
    """Main execution loop for the CLI application."""
    # Ensure database tables exist and baseline seed data is loaded
    database.initialize_database()
    database.seed_sample_data()

    while True:
        functions.clear_screen()
        display_menu()
        
        choice = input("\nEnter your choice (1-8): ").strip()

        if choice == '1':
            functions.clear_screen()
            print("--- VIEW ALL PRODUCTION RECORDS ---")
            functions.view_all_records()
            input("\nPress Enter to return to the main menu...")

        elif choice == '2':
            functions.clear_screen()
            functions.add_new_production_record()
            input("\nPress Enter to return to the main menu...")

        elif choice == '3':
            functions.clear_screen()
            print("--- SEARCH RECORDS ---")
            functions.search_records_interactive()
            input("\nPress Enter to return to the main menu...")

        elif choice == '4':
            functions.clear_screen()
            print("--- UPDATE HARVEST RECORD ---")
            functions.update_record_interactive()
            input("\nPress Enter to return to the main menu...")

        elif choice == '5':
            functions.clear_screen()
            print("--- DELETE PRODUCTION RECORD ---")
            functions.delete_record_interactive()
            input("\nPress Enter to return to the main menu...")

        elif choice == '6':
            functions.clear_screen()
            analytics.display_analytical_summaries()
            input("\nPress Enter to return to the main menu...")

        elif choice == '7':
            functions.clear_screen()
            print("--- GENERATE VISUAL CHARTS ---")
            analytics.generate_all_charts()
            input("\nPress Enter to return to the main menu...")

        elif choice == '8':
            functions.clear_screen()
            print("Thank you for using the Agricultural Production Tracker. Goodbye!")
            sys.exit(0)

        else:
            input("\nInvalid choice! Please enter a number from 1 to 8. Press Enter to retry...")


if __name__ == "__main__":
    main()