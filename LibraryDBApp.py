import sqlite3
from datetime import date, timedelta


conn = sqlite3.connect('library.db')
conn.execute("PRAGMA foreign_keys = ON")

LOAN_DAYS = 14

def pause():
    input("\nPress Enter to continue...")

#every attr
ITEM_COLUMNS = """
        i.item_id, i.title, i.creator, i.publisher, i.year, i.subject_genre, i.language,
        pb.ISBN AS pb_isbn, pb.page_num,
        eb.ISBN AS eb_isbn, eb.format,
        mg.ISSN AS mg_issn, mg.issue AS mg_issue, mg.issue_date,
        jr.ISSN AS jr_issn, jr.issue AS jr_issue, jr.volume,
        rc.type AS rc_type, rc.quantity,
        (SELECT COUNT(*) FROM Copy c
          WHERE c.item_id = i.item_id AND c.status = 'available') AS available_copies
"""

ITEM_JOINS = """
        LEFT JOIN PrintBook pb ON i.item_id = pb.item_id
        LEFT JOIN EBook     eb ON i.item_id = eb.item_id
        LEFT JOIN Magazine  mg ON i.item_id = mg.item_id
        LEFT JOIN Journal   jr ON i.item_id = jr.item_id
        LEFT JOIN Record    rc ON i.item_id = rc.item_id
"""

def build_item(row):
    #Turn row of cols into one dict
    (item_id, title, creator, publisher, year, subject_genre, language,
     pb_isbn, page_num,
     eb_isbn, fmt,
     mg_issn, mg_issue, issue_date,
     jr_issn, jr_issue, volume,
     rc_type, quantity, available_copies) = row

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

    return {
        "item_id": item_id,
        "title": title,
        "creator": creator,
        "publisher": publisher,
        "year": year,
        "subject_genre": subject_genre,
        "language": language,
        "type": item_type,
        #set issn/isbn
        "isbn": pb_isbn if pb_isbn is not None else eb_isbn,
        "issn": mg_issn if mg_issn is not None else jr_issn,
        "page_num": page_num,
        "format": fmt,
        "issue": mg_issue if mg_issue is not None else jr_issue,
        "issue_date": issue_date,
        "volume": volume,
        "record_type": rc_type,
        "quantity": quantity,
        "available_copies": available_copies,
    }

def search_items(cur, search_term):
    #Search by title name year or issn/isbn
    cur.execute(f"""
        SELECT {ITEM_COLUMNS}
        FROM Item i
        {ITEM_JOINS}
        WHERE i.title LIKE :term
           OR i.creator LIKE :term
           OR pb.isbn LIKE :term
           OR eb.isbn LIKE :term
           OR mg.ISSN LIKE :term
           OR jr.ISSN LIKE :term
           OR CAST(i.year AS TEXT) LIKE :term
    """, {"term": f"%{search_term}%"})

    return [build_item(row) for row in cur.fetchall()]

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

def shown(value):
    # added to disp - for missing info
    return value if value is not None else "-"

def show_item(item, number=None):
    #Everything about an item
    label = f"{number}. " if number is not None else ""
    print(f"{label}{item['title']} by {shown(item['creator'])} "
          f"({shown(item['year'])}) — {item['type']}")
    print(f"    Publisher: {shown(item['publisher'])}")
    print(f"    Subject/Genre: {shown(item['subject_genre'])}")
    print(f"    Language: {shown(item['language'])}")

    #dependant info
    if item['type'] == "Print Book":
        print(f"    ISBN: {shown(item['isbn'])}")
        print(f"    Pages: {shown(item['page_num'])}")
    elif item['type'] == "E-Book":
        print(f"    ISBN: {shown(item['isbn'])}")
        print(f"    Format: {shown(item['format'])}")
    elif item['type'] == "Magazine":
        print(f"    ISSN: {shown(item['issn'])}")
        print(f"    Issue: {shown(item['issue'])}")
        print(f"    Issue date: {shown(item['issue_date'])}")
    elif item['type'] == "Journal":
        print(f"    ISSN: {shown(item['issn'])}")
        print(f"    Issue: {shown(item['issue'])}")
        print(f"    Volume: {shown(item['volume'])}")
    elif item['type'] == "Record":
        print(f"    Type: {shown(item['record_type'])}")
        print(f"    Quantity: {shown(item['quantity'])}")

    print(f"    Available copies: {item['available_copies']}")

def show_results(matches):
    #List matches with selection number
    for number, item in enumerate(matches, start=1):
        show_item(item, number)

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
        print()
        show_item(item)
        item_action(cur, member_id, item)
        return


def member_loans(cur, member_id):
    #get everything the member currently has out
    cur.execute(f"""
        SELECT l.loan_id, l.copy_number, l.checkout_date, l.due_date,
               {ITEM_COLUMNS}
        FROM Loan l
        JOIN Item i ON i.item_id = l.item_id
        {ITEM_JOINS}
        WHERE l.member_id = ? AND l.returned_date IS NULL
        ORDER BY l.due_date
    """, (member_id,))

    loans = []

    for row in cur.fetchall():
        loan_id, copy_number, checkout_date, due_date = row[:4]
        loans.append({
            "loan_id": loan_id,
            "copy_number": copy_number,
            "checkout_date": checkout_date,
            "due_date": due_date,
            "overdue": due_date < date.today().isoformat(),
            "item": build_item(row[4:]),
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
        show_item(loan['item'], number)
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
            return_item(cur, member_id, loan['item']['item_id'], loan['copy_number'])
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
        print()
        show_item(loan['item'])
        print(f"    Copy {loan['copy_number']}, due {loan['due_date']}")
        loan_action(cur, member_id, loan)
        return

def get_text(prompt, required=False):
    while True:
        entry = input(prompt).strip()

        if entry:
            return entry
        if not required:
            return None

        print("This one is required.")

def get_int(prompt, required=False):
    while True:
        entry = input(prompt).strip()

        if not entry:
            if not required:
                return None
            print("This one is required.")
            continue

        if entry.isdigit():
            return int(entry)

        print("Enter a number.")

def get_date(prompt):
    while True:
        entry = input(prompt).strip()

        if not entry:
            return None

        try:
            return date.fromisoformat(entry).isoformat()
        except ValueError:
            print("Enter a date as YYYY-MM-DD.")

def find_existing_item(cur, item_data):
    #find by isbn or issn and issue
    item_type = item_data['type']

    if item_type == "Print Book" and item_data['isbn']:
        cur.execute("SELECT item_id FROM PrintBook WHERE ISBN = ?", (item_data['isbn'],))
    elif item_type == "E-Book" and item_data['isbn']:
        cur.execute("SELECT item_id FROM EBook WHERE ISBN = ?", (item_data['isbn'],))
    elif item_type == "Magazine" and item_data['issn']:
        cur.execute("SELECT item_id FROM Magazine WHERE ISSN = ? AND issue IS ?",
                    (item_data['issn'], item_data['issue']))
    elif item_type == "Journal" and item_data['issn']:
        cur.execute("SELECT item_id FROM Journal WHERE ISSN = ? AND issue IS ?",
                    (item_data['issn'], item_data['issue']))
    else:
        return None

    row = cur.fetchone()
    return row[0] if row is not None else None

def add_copy(cur, item_id, member_id):
    #next free copy number for an item we already had
    cur.execute("SELECT COALESCE(MAX(copy_number), 0) + 1 FROM Copy WHERE item_id = ?", (item_id,))
    copy_number = cur.fetchone()[0]

    with conn:
        cur.execute("INSERT INTO Copy (item_id, copy_number, status) VALUES (?, ?, 'available')",
                    (item_id, copy_number))
        cur.execute("INSERT INTO Donates (item_id, copy_number, member_id, date_donated) "
                    "VALUES (?, ?, ?, ?)",
                    (item_id, copy_number, member_id, date.today().isoformat()))

    return copy_number

def donate_item(cur, member_id, item_data):
    #donating something already had adds a copy
    existing_id = find_existing_item(cur, item_data)

    if existing_id is not None:
        copy_number = add_copy(cur, existing_id, member_id)
        print(f"Already in the catalogue, added as copy {copy_number}.")
        return {"item_id": existing_id, "copy_number": copy_number, "new_item": False}

    item_type = item_data['type']

    #attmpt insertion
    try:
        with conn:
            cur.execute(
                "INSERT INTO Item (title, creator, publisher, year, subject_genre, language) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (item_data['title'], item_data['creator'], item_data['publisher'],
                 item_data['year'], item_data['subject_genre'], item_data['language'])
            )
            item_id = cur.lastrowid

            if item_type == "Print Book":
                cur.execute("INSERT INTO PrintBook (item_id, ISBN, page_num) VALUES (?, ?, ?)",
                            (item_id, item_data['isbn'], item_data['page_num']))
            elif item_type == "E-Book":
                cur.execute("INSERT INTO EBook (item_id, ISBN, format) VALUES (?, ?, ?)",
                            (item_id, item_data['isbn'], item_data['format']))
            elif item_type == "Magazine":
                cur.execute("INSERT INTO Magazine (item_id, ISSN, issue, issue_date) VALUES (?, ?, ?, ?)",
                            (item_id, item_data['issn'], item_data['issue'], item_data['issue_date']))
            elif item_type == "Journal":
                cur.execute("INSERT INTO Journal (item_id, ISSN, issue, volume) VALUES (?, ?, ?, ?)",
                            (item_id, item_data['issn'], item_data['issue'], item_data['volume']))

            cur.execute("INSERT INTO Copy (item_id, copy_number, status) VALUES (?, 1, 'available')",
                        (item_id,))
            cur.execute("INSERT INTO Donates (item_id, copy_number, member_id, date_donated) "
                        "VALUES (?, 1, ?, ?)",
                        (item_id, member_id, date.today().isoformat()))
    except sqlite3.IntegrityError as e:
        print("Donation failed:", e)
        return None

    print(f"Thanks, added as item {item_id}, copy 1.")
    return {"item_id": item_id, "copy_number": 1, "new_item": True}

def donate_prompt(cur, member_id):
    while True:
        print("\nWhat would you like to donate?")
        print("(1) Print Book\n(2) E-Book\n(3) Magazine\n(4) Journal\n(0) Back")
        choice = input("Choose: ").strip()

        if choice == "0":
            return
        if choice in ("1", "2", "3", "4"):
            break

        print("Invalid choice.")

    item_type = {"1": "Print Book", "2": "E-Book", "3": "Magazine", "4": "Journal"}[choice]

    #blank is fine for anything except the title
    item_data = {
        "type": item_type,
        "title": get_text("Title: ", required=True),
        "creator": get_text("Author/Creator: ", required=True),
        "publisher": get_text("Publisher: ", required=True),
        "year": get_int("Year: ", required=True),
        "subject_genre": get_text("Subject/Genre: ", required=True),
        "language": get_text("Language: ", required=True),
        "isbn": None,
        "issn": None,
        "issue": None,
        "issue_date": None,
        "volume": None,
        "page_num": None,
        "format": None,
    }

    if item_type == "Print Book":
        item_data['isbn'] = get_text("ISBN: ")
        item_data['page_num'] = get_int("Pages: ")
    elif item_type == "E-Book":
        item_data['isbn'] = get_text("ISBN: ")
        item_data['format'] = get_text("Format (PDF, EPUB, ...): ")
    elif item_type == "Magazine":
        item_data['issn'] = get_text("ISSN: ")
        item_data['issue'] = get_text("Issue: ")
        item_data['issue_date'] = get_date("Issue date (YYYY-MM-DD): ")
    elif item_type == "Journal":
        item_data['issn'] = get_text("ISSN: ")
        item_data['issue'] = get_text("Issue: ")
        item_data['volume'] = get_int("Volume: ")

    donate_item(cur, member_id, item_data)
    pause()

def show_event(event, number=None):
    label = f"{number}. " if number is not None else ""
    print(f"{label}{event['name']} ({event['type']}) — {event['date']} {shown(event['time'])}")
    print(f"    Room: {shown(event['room_name'])}")
    print(f"    Audience: {shown(event['audience'])}")
    if event['capacity'] is not None:
        spots_left = event['capacity'] - event['registered']
        print(f"    Spots left: {spots_left} / {event['capacity']}")

def show_all_events(events):
    for number, event in enumerate(events, start=1):
        show_event(event, number)

def upcoming_events(cur, event_type=None):
    #list al events or by tpe from today on
    cur.execute("""
        SELECT e.event_id, e.name, e.type, e.date, e.time, e.audience, e.capacity, r.name,
               (SELECT COUNT(*) FROM Registers reg WHERE reg.event_id = e.event_id) AS registered
        FROM Event e
        LEFT JOIN Room r ON r.room_id = e.room_id
        WHERE e.date >= :today
          AND (:etype IS NULL OR e.type = :etype)
        ORDER BY e.date, e.time
    """, {"today": date.today().isoformat(), "etype": event_type})

    events = []
    for row in cur.fetchall():
        event_id, name, etype, edate, etime, audience, capacity, room_name, registered = row
        events.append({
            "event_id": event_id, "name": name, "type": etype,
            "date": edate, "time": etime, "audience": audience,
            "capacity": capacity, "room_name": room_name, "registered": registered,
        })
    return events

def event_action(cur, member_id, event):
    while True:
        choice = input("\n(1) Register  (2) Volunteer  (0) Back: ").strip()

        if choice == "0":
            return
        if choice == "1":
            register_for_event(cur, member_id, event['event_id'])
            pause()
            return
        if choice == "2":
            volunteer_for_event(cur, member_id, event['event_id'])
            pause()
            return

        print("Invalid choice.")

def browse_events(cur, member_id, events):
    while True:
        print()
        show_all_events(events)
        entry = input("\nSelect event number (#), or (0) to return to the menu: ").strip()

        if entry == "0":
            return

        if not entry.isdigit() or not 1 <= int(entry) <= len(events):
            print("Invalid selection.")
            pause()
            continue

        event = events[int(entry) - 1]
        print()
        show_event(event)
        event_action(cur, member_id, event)
        return
    
def register_for_event(cur, member_id, event_id):
    #check alr registered and capacity
    cur.execute("SELECT 1 FROM Registers WHERE member_id = ? AND event_id = ?", (member_id, event_id))
    if cur.fetchone() is not None:
        print("You're already registered for this event.")
        return None

    cur.execute("SELECT capacity FROM Event WHERE event_id = ?", (event_id,))
    capacity = cur.fetchone()[0]
    if capacity is not None:
        cur.execute("SELECT COUNT(*) FROM Registers WHERE event_id = ?", (event_id,))
        if cur.fetchone()[0] >= capacity:
            print("Sorry, this event is full.")
            return None

    #attempt to reg
    try:
        with conn:
            cur.execute(
                "INSERT INTO Registers (member_id, event_id, reg_date) VALUES (?, ?, ?)",
                (member_id, event_id, date.today().isoformat())
            )
    except sqlite3.IntegrityError as e:
        print("Registration failed:", e)
        return None

    print("Registered!")
    return {"member_id": member_id, "event_id": event_id}


def volunteer_for_event(cur, member_id, event_id):
    #check alr reg
    cur.execute("SELECT 1 FROM Volunteers WHERE member_id = ? AND event_id = ?", (member_id, event_id))
    if cur.fetchone() is not None:
        print("You're already volunteering for this event.")
        return None

    #attempt reg
    try:
        with conn:
            cur.execute("INSERT INTO Volunteers (member_id, event_id) VALUES (?, ?)", (member_id, event_id))
    except sqlite3.IntegrityError as e:
        print("Volunteer signup failed:", e)
        return None

    print("Signed up to volunteer!")
    return {"member_id": member_id, "event_id": event_id}

def ask_librarian(cur):
    return;

def register_member(cur, name, address, phone, email):
    # try to create and add a tuple with reg info
    try:
        with conn:
            cur.execute("""
                INSERT INTO Member (name, address, phone, email, reg_date, status)
                VALUES (?, ?, ?, ?, ?, 'active')""", (name, address, phone, email, date.today().isoformat())
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
    
def check_overdue_fines(cur):
    #issue fines to any overdue without them, incr fines overitme
    with conn:
        cur.execute("""
            INSERT OR IGNORE INTO Fine (loan_id, date_issued, amount, status)
            SELECT l.loan_id,
                   date('now'),
                   ROUND((julianday('now') - julianday(l.due_date)) * 0.50, 2),
                   'unpaid'
            FROM Loan l
            WHERE l.returned_date IS NULL
              AND l.due_date < date('now')
        """)
        cur.execute("""
            UPDATE Fine
            SET amount = ROUND((julianday('now') - julianday(
                    (SELECT due_date FROM Loan WHERE Loan.loan_id = Fine.loan_id)
                )) * 0.50, 2)
            WHERE status = 'unpaid'
            AND loan_id IN (
                SELECT loan_id FROM Loan
                WHERE returned_date IS NULL AND due_date < date('now')
            )
        """)


def main():
    cur = conn.cursor()
    #set member or promt login
    current_member = login_or_register(cur)
    check_overdue_fines(cur)

    #basic input loop
    while True:
        print(f"\nLogged in as: {current_member['name']} ID: {current_member['member_id']}")
        print("(1) Search items\n(2) Return item\n(3) Donate item\n(4) Upcoming Events\n(5) Get Help\n(0) Quit")
        choice = input("Choose: ")
        #search input
        if choice == "1":
            term = input("Search for: ")
            matches = search_items(cur, term)
            #recrds of items to be added dont need to be seen by users
            matches = [item for item in matches if item['type'] != "Record"]

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
        #donations
        elif choice == "3":
            donate_prompt(cur, current_member['member_id'])
        elif choice == "0":
            break

        elif choice == "4":
            events = upcoming_events(cur)
            if not events:
                print("No upcoming events found.")
                pause()
            else:
                browse_events(cur, current_member['member_id'], events)
        

    conn.close()

if __name__ == "__main__":
    main()