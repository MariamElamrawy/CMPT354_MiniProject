import sqlite3

conn = sqlite3.connect('library.db')

cursor = conn.cursor()
print("Opened database successfully \n")

with conn:

    cur = conn.cursor()

    # Sanity-check query: confirm the connection works and list what tables exist.
    # (Replace/expand this with real queries as you build out the app.)
    myQuery = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"

    cur.execute(myQuery)

    rows = cur.fetchall()
    if rows:
        print("Connected. Tables found in library.db:")
        for row in rows:
            print(" -", row[0])
    else:
        print("Connected, but no tables were found in library.db!")
    print("\n")


if conn:
    conn.close()
    print("Closed database successfully")
