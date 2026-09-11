from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from passlib.context import CryptContext

app = Flask(__name__)
app.secret_key = "super_secret_session_key_change_this_later"

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "income_tracker.db")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enables named lookups: row['amount']
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            source TEXT,
            amount REAL,
            date TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item TEXT,
            cost REAL,
            date TEXT
        );
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        
        hashed = pwd_context.hash(password)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?);", (username, email, hashed))
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "Error: That email is already registered!"
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE email = ?;", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and pwd_context.verify(password, user["password_hash"]):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))
        return "Invalid credentials!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT username FROM users WHERE id = ?;", (user_id,))
    user_profile = cursor.fetchone()
    current_username = user_profile["username"] if user_profile else "User"
    
    cursor.execute("SELECT source, amount, date, id FROM income WHERE user_id = ? ORDER BY date DESC;", (user_id,))
    income_rows = cursor.fetchall()
    
    cursor.execute("SELECT item, cost, date, id FROM expenses WHERE user_id = ? ORDER BY date DESC;", (user_id,))
    expense_rows = cursor.fetchall()
    conn.close()
    
    # FIXED: Uses correct key mappings to compute totals cleanly without crashing
    total_income = sum(row["amount"] for row in income_rows)
    total_expenses = sum(row["cost"] for row in expense_rows)
    net_profit = total_income - total_expenses
    
    return render_template(
        "dashboard.html", 
        username=current_username, 
        income_rows=income_rows, 
        expense_rows=expense_rows, 
        net_profit=net_profit
    )

@app.route("/add_income", methods=["POST"])
def add_income():
    if "user_id" not in session:
        return redirect(url_for("login"))
    source = request.form.get("source")
    amount = float(request.form.get("amount", 0.0))
    date = request.form.get("date")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO income (user_id, source, amount, date) VALUES (?, ?, ?, ?);", (session["user_id"], source, amount, date))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/add_expense", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))
    item = request.form.get("item")
    cost = float(request.form.get("cost", 0.0))
    date = request.form.get("date")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO expenses (user_id, item, cost, date) VALUES (?, ?, ?, ?);", (session["user_id"], item, cost, date))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/delete/<table_name>/<int:entry_id>", methods=["POST"])
def delete_entry(table_name, entry_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    if table_name in ["income", "expenses"]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ? AND user_id = ?;", (entry_id, session["user_id"]))
        conn.commit()
        conn.close()
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
