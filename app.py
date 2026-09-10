from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

@app.route("/")
def home():
    conn = sqlite3.connect("income_tracker.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT source, amount, date, id FROM income ORDER BY date DESC;")
    income_rows = cursor.fetchall()
    
    cursor.execute("SELECT item, cost, date, id FROM expenses ORDER BY date DESC;")
    expense_rows = cursor.fetchall()
    
    conn.close()
    
    total_income = sum(row[1] for row in income_rows)
    total_expenses = sum(row[1] for row in expense_rows)
    net_profit = total_income - total_expenses
    
    return render_template(
        "dashboard.html", 
        income_rows=income_rows, 
        expense_rows=expense_rows, 
        net_profit=net_profit
    )

@app.route("/add_income", methods=["POST"])
def add_income():
    source = request.form.get("source")
    amount = float(request.form.get("amount", 0.0))
    date = request.form.get("date")
    
    conn = sqlite3.connect("income_tracker.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO income (source, amount, date) VALUES (?, ?, ?);", (source, amount, date))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/add_expense", methods=["POST"])
def add_expense():
    item = request.form.get("item")
    cost = float(request.form.get("cost", 0.0))
    date = request.form.get("date")
    
    conn = sqlite3.connect("income_tracker.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expenses (item, cost, date) VALUES (?, ?, ?);", (item, cost, date))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/delete/<table_name>/<int:entry_id>", methods=["POST"])
def delete_entry(table_name, entry_id):
    if table_name in ["income", "expenses"]:
        conn = sqlite3.connect("income_tracker.db")
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?;", (entry_id,))
        conn.commit()
        conn.close()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
