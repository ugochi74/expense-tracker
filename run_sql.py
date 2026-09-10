import sqlite3

conn = sqlite3.connect("income_tracker.db")
cursor = conn.cursor()

print("Connected to income_tracker.db. Type your SQL query or 'exit' to quit.")
while True:
    try:
        query = input("SQL> ")
        if query.strip().lower() in ['exit', 'quit']:
            break
        if not query.strip():
            continue
        
        cursor.execute(query)
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            for row in rows:
                print(row)
        else:
            conn.commit()
            print("Command executed successfully.")
    except Exception as e:
       print(f"Error: {e}")

conn.close()
