import sqlite3
from datetime import date, timedelta


conn = sqlite3.connect('library.db')
conn.execute("PRAGMA foreign_keys = ON")

def find_item(cur, search_term):
    #Search by title name year or issn/isbn
    cur.execute("""
        SELECT i.item_id, i.title, i.creator, i.year,
               pb.isbn AS pb_isbn, pb.page_num,
               eb.isbn AS eb_isbn, eb.format,
               mg.issue AS mg_issue, mg.ISSN AS mg_issn,
               jr.issue AS jr_issue, jr.ISSN AS jr_issn,
               rc.type AS rc_type
        FROM Item i
        LEFT JOIN PrintBook pb ON i.item_id = pb.item_id
        LEFT JOIN EBook     eb ON i.item_id = eb.item_id
        LEFT JOIN Magazine  mg ON i.item_id = mg.item_id
        LEFT JOIN Journal   jr ON i.item_id = jr.item_id
        LEFT JOIN Record    rc ON i.item_id = rc.item_id
        WHERE i.title LIKE :term
           OR i.creator LIKE :term
           OR pb.isbn LIKE :term
           OR eb.isbn LIKE :term
           OR mg.ISSN LIKE :term
           OR jr.ISSN LIKE :term
           OR CAST(i.year AS TEXT) LIKE :term 
    """, {"term": f"%{search_term}%"})

    rows = cur.fetchall()
    results = []

    for row in rows:
        (item_id, title, creator, year,
         pb_isbn, page_num,
         eb_isbn, fmt,
         mg_issue, mg_issn,
         jr_issue, jr_issn,
         rc_type) = row

        # get type
        if pb_isbn is not None:
            item_type = "Print Book"
        elif eb_isbn is not None:
            item_type = "E-Book"
        elif mg_issue is not None:
            item_type = "Magazine"
        elif jr_issue is not None:
            item_type = "Journal"
        elif rc_type is not None:
            item_type = "Record"
        else:
            item_type = "Unknown"

        #set issn/isbn
        isbn = pb_isbn if pb_isbn is not None else eb_isbn
        issn = mg_issn if mg_issn is not None else jr_issn

        #set count available
        available_copies = None
        if item_type == "Print Book":
            cur.execute(
                "SELECT COUNT(*) FROM Copy WHERE item_id = ? AND status = 'available'",
                (item_id,)
            )
            available_copies = cur.fetchone()[0]

        results.append({
            "item_id": item_id,
            "title": title,
            "creator": creator,
            "year": year,
            "type": item_type,
            "isbn": isbn,
            "issn": issn,
            "available_copies": available_copies,
        })

    return results

def borrow_item(cur, member_id, item_id):
    return;

def return_item(cur, member_id, item_id, copy_number):
    return;

def donate_item(cur, item_data):
    return;

def find_event(cur, event_type=None):
    return;
    
def register_for_event(cur, member_id, event_id):
    return;

def volunteer_for_event(cur, member_id, event_id):
    return;

def ask_librarian(cur):
    return;

def register_member(cur, name, address, phone, email):
    # try to create and add a tuple with reg info
    try:
        with conn:
            cur.execute(
                "INSERT INTO Member (name, address, phone, email, reg_date, status) "
                "VALUES (?, ?, ?, ?, ?, 'active')", (name, address, phone, email, date.today().isoformat())
            )
        new_id = cur.lastrowid
        print("Your ID is: ", new_id)
        return {"member_id": new_id, "name": name}
    except sqlite3.IntegrityError as e:
        print("Registration failed:", e)
        return None

def login(cur, member_id):
    #Attempt to find member for provided id
    cur.execute(
        "SELECT member_id, name, status FROM Member WHERE member_id = ?",
        (member_id,)
    )
    row = cur.fetchone()

    if row is None:
        print("No member found with that ID.")
        return None

    member_id, name, status = row

    #check status
    if status != "active":
        print(f"Member account is {status}, not active.")
        return None

    return {"member_id": member_id, "name": name}

def  login_or_register(cur):
    #Promt login or reg
    while True:
        choice = input("1) Log in  2) Register as new member: ")

        if choice == "1":
            member_id = int(input("Enter your member ID: "))
            member = login(cur, member_id)
            if member is not None:
                return member
            # repromt on failure

        elif choice == "2":
            name = input("Name: ")
            address = input("Address: ")
            phone = input("Phone: ")
            email = input("Email: ")
            member = register_member(cur, name, address, phone, email)
            if member is not None:
                return member

def main():
    cur = conn.cursor()
    #set member or promt login
    current_member = login_or_register(cur)

    #basic input loop
    while True:
        print(f"\nLogged in as: {current_member['name']} ID: {current_member['member_id']}")
        print("1. Find item\n2. Borrow item\n3. Return item\n4. Donate item\n5. Upcoming Events\n6. Volunteer Oportunities\n7. Help\n0. Quit")
        choice = input("Choose: ")
        #search input
        if choice == "1":
            term = input("Search for: ")
            matches = find_item(cur, term)

            #return results
            if not matches:
                print("No items found.\n")
            else:
                for item in matches:
                    print(f"{item['title']} by {item['creator']} ({item['year']}) — {item['type']}")

                    if item['isbn'] is not None:
                        print(f"    ISBN: {item['isbn']}")
                    elif item['issn'] is not None:
                        print(f"    ISSN: {item['issn']}")

                    if item['available_copies'] is not None:
                        print(f"    Available copies: {item['available_copies']}")
                print()
        elif choice == "0":
            break
        # ... etc

    conn.close()

if __name__ == "__main__":
    main()