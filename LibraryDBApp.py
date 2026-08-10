import sqlite3
from datetime import date, timedelta


conn = sqlite3.connect('library.db')
conn.execute("PRAGMA foreign_keys = ON")

def find_item(cur, search_term):
    

def borrow_item(cur, member_id, item_id):
    

def return_item(cur, member_id, item_id, copy_number):
    

def donate_item(cur, item_data):
    

def find_event(cur, event_type=None):
    
    
def register_for_event(cur, member_id, event_id):
    

def volunteer_for_event(cur, member_id, event_id):
    

def ask_librarian(cur):
    


def main():
    cur = conn.cursor()
    while True:
        print("1. Find item\n2. Borrow item\n... \n0. Quit")
        choice = input("Choose: ")
        if choice == "1":
            term = input("Search for: ")
            find_item(cur, term)
        elif choice == "0":
            break
        # ... etc

    conn.close()

if __name__ == "__main__":
    main()