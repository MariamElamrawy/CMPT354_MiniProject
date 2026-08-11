import sqlite3
from datetime import date, timedelta


conn = sqlite3.connect('library.db')
conn.execute("PRAGMA foreign_keys = ON")

LOAN_DAYS = 14

def pause():
    input("\nPress Enter to continue...")

def search_items(cur, search_term):
    #Search by title name year or issn/isbn
    cur.execute("""
        SELECT i.item_id, i.title, i.creator, i.year,
               pb.isbn AS pb_isbn, pb.page_num,
               eb.isbn AS eb_isbn, eb.format,
               mg.issue AS mg_issue, mg.ISSN AS mg_issn,
               jr.issue AS jr_issue, jr.ISSN AS jr_issn,
               rc.type AS rc_type,
               (SELECT COUNT(*) FROM Copy c
                 WHERE c.item_id = i.item_id AND c.status = 'available') AS available_copies
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
         rc_type, available_copies) = row

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
    #ensure one copy per member 
    cur.execute(
        "SELECT 1 FROM Loan WHERE member_id = ? AND item_id = ? AND returned_date IS NULL",
        (member_id, item_id)
    )
    if cur.fetchone() is not None:
        print("You already have a copy of this item on loan.")
        return None

    #get a free copy
    cur.execute(
        "SELECT copy_number FROM Copy WHERE item_id = ? AND status = 'available' "
        "ORDER BY copy_number LIMIT 1",
        (item_id,)
    )
    row = cur.fetchone()

    if row is None:
        print("No copies available to borrow.")
        return None

    copy_number = row[0]
    due = date.today() + timedelta(days=LOAN_DAYS)

    #copy_on_loan will flip the copy status, block_loan_if_fines_exceed can reject 
    try:
        with conn:
            cur.execute(
                "INSERT INTO Loan (checkout_date, due_date, returned_date, item_id, copy_number, member_id) "
                "VALUES (?, ?, NULL, ?, ?, ?)",
                (date.today().isoformat(), due.isoformat(), item_id, copy_number, member_id)
            )
        loan_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        print("Borrow failed:", e)
        return None

    print(f"Borrowed copy {copy_number}. Due back {due.isoformat()}.")
    return {"loan_id": loan_id, "item_id": item_id,
            "copy_number": copy_number, "due_date": due.isoformat()}

def place_hold(cur, member_id, item_id):
    #ensure one per membee
    cur.execute("SELECT 1 FROM Hold WHERE member_id = ? AND item_id = ?", (member_id, item_id))
    if cur.fetchone() is not None:
        print("You already have a hold on this item.")
        return None

    try:
        with conn:
            cur.execute(
                "INSERT INTO Hold (member_id, item_id, date_placed) VALUES (?, ?, ?)",
                (member_id, item_id, date.today().isoformat())
            )
    except sqlite3.IntegrityError as e:
        print("Hold failed:", e)
        return None

    print("Hold placed.")
    return {"member_id": member_id, "item_id": item_id}

def show_results(matches):
    #List matches with selection number
    for number, item in enumerate(matches, start=1):
        print(f"{number}. {item['title']} by {item['creator']} ({item['year']}) — {item['type']}")

        if item['isbn'] is not None:
            print(f"    ISBN: {item['isbn']}")
        elif item['issn'] is not None:
            print(f"    ISSN: {item['issn']}")

        print(f"    Available copies: {item['available_copies']}")

def item_action(cur, member_id, item):
    #Borrow if a copy is free or promt hold
    while True:
        if item['available_copies'] > 0:
            choice = input("\n(1) Borrow this item  (0) Back: ").strip()
        else:
            choice = input("\nNo copies available. (1) Place a hold  (0) Back: ").strip()

        if choice == "0":
            return

        if choice == "1":
            if item['available_copies'] > 0:
                borrow_item(cur, member_id, item['item_id'])
            else:
                place_hold(cur, member_id, item['item_id'])
            pause()
            return

        print("Invalid choice.")

def browse_results(cur, member_id, matches):
    #selection list
    while True:
        print()
        show_results(matches)
        entry = input("\nSelect item number (#), or (0) to return to the menu: ").strip()

        if entry == "0":
            return

        if not entry.isdigit() or not 1 <= int(entry) <= len(matches):
            print("Invalid selection.")
            pause()
            continue

        item = matches[int(entry) - 1]
        print(f"\n{item['title']} by {item['creator']} ({item['year']}) — {item['type']}")
        item_action(cur, member_id, item)
        return


def member_loans(cur, member_id):
    #get everything the member currently has out
    cur.execute("""
        SELECT l.loan_id, l.item_id, l.copy_number, l.checkout_date, l.due_date,
               i.title, i.creator, i.year
        FROM Loan l
        JOIN Item i ON i.item_id = l.item_id
        WHERE l.member_id = ? AND l.returned_date IS NULL
        ORDER BY l.due_date
    """, (member_id,))

    loans = []

    for (loan_id, item_id, copy_number, checkout_date, due_date,
         title, creator, year) in cur.fetchall():
        loans.append({
            "loan_id": loan_id,
            "item_id": item_id,
            "copy_number": copy_number,
            "checkout_date": checkout_date,
            "due_date": due_date,
            "title": title,
            "creator": creator,
            "year": year,
            "overdue": due_date < date.today().isoformat(),
        })

    return loans

def return_item(cur, member_id, item_id, copy_number):
    #find the open loan for this copy
    cur.execute(
        "SELECT loan_id FROM Loan WHERE member_id = ? AND item_id = ? AND copy_number = ? "
        "AND returned_date IS NULL",
        (member_id, item_id, copy_number)
    )
    row = cur.fetchone()

    if row is None:
        print("No open loan found for that copy.")
        return None

    loan_id = row[0]

    #copy_returned trigger will update copy
    with conn:
        cur.execute(
            "UPDATE Loan SET returned_date = ? WHERE loan_id = ?",
            (date.today().isoformat(), loan_id)
        )

    print(f"Returned copy {copy_number}.")
    return {"loan_id": loan_id, "item_id": item_id, "copy_number": copy_number}

def show_loans(loans):
    #disp selection list
    for number, loan in enumerate(loans, start=1):
        print(f"{number}. {loan['title']} by {loan['creator']} ({loan['year']})")
        print(f"    Copy {loan['copy_number']}, borrowed {loan['checkout_date']}")

        if loan['overdue']:
            print(f"    Due {loan['due_date']} — OVERDUE")
        else:
            print(f"    Due {loan['due_date']}")

def loan_action(cur, member_id, loan):
    #return option
    while True:
        choice = input("\n(1) Return this item  (0) Back: ").strip()

        if choice == "0":
            return

        if choice == "1":
            return_item(cur, member_id, loan['item_id'], loan['copy_number'])
            pause()
            return

        print("Invalid choice.")

def browse_loans(cur, member_id, loans):
    #loan selection
    while True:
        print()
        show_loans(loans)
        entry = input("\nSelect item number (#), or (0) to return to the menu: ").strip()

        if entry == "0":
            return

        if not entry.isdigit() or not 1 <= int(entry) <= len(loans):
            print("Invalid selection.")
            pause()
            continue

        loan = loans[int(entry) - 1]
        print(f"\n{loan['title']} by {loan['creator']} ({loan['year']}) — copy {loan['copy_number']}")
        loan_action(cur, member_id, loan)
        return

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
        print("Write this down, you will need it to log in.")
        pause()
        return {"member_id": new_id, "name": name}
    except sqlite3.IntegrityError as e:
        print("Registration failed:", e)
        pause()
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
        pause()
        return None

    member_id, name, status = row

    #check status
    if status != "active":
        print(f"Member account is {status}, not active.")
        pause()
        return None

    return {"member_id": member_id, "name": name}

def  login_or_register(cur):
    #Promt login or reg
    while True:
        choice = input("1) Log in  2) Register as new member: ")

        if choice == "1":
            entry = input("Enter your member ID: ").strip()
            #validate
            if not entry.isdigit():
                print("Member ID must be a number.")
                pause()
                continue

            member = login(cur, int(entry))
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
        print("(1) Search items\n(2) Return item\n(3) Donate item\n(4) Upcoming Events\n(5) Volunteer Oportunities\n(6) Help\n(0) Quit")
        choice = input("Choose: ")
        #search input
        if choice == "1":
            term = input("Search for: ")
            matches = search_items(cur, term)

            #borrow and hold are reached by picking a result
            if not matches:
                print("No items found.")
                pause()
            else:
                browse_results(cur, current_member['member_id'], matches)
        #items currently on loan
        elif choice == "2":
            loans = member_loans(cur, current_member['member_id'])

            if not loans:
                print("You have nothing on loan.")
                pause()
            else:
                browse_loans(cur, current_member['member_id'], loans)
        elif choice == "0":
            break
        

    conn.close()

if __name__ == "__main__":
    main()