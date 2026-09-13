import os
from decimal import Decimal, InvalidOperation
from functools import wraps
import psycopg
from psycopg.rows import dict_row
from flask import Flask, flash, redirect, render_template, request, session, url_for
from supabase import create_client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY) if SUPABASE_URL and SUPABASE_ANON_KEY else None

def db():
    if not DATABASE_URL: raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
def required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs) if session.get("user") else redirect(url_for("login"))
    return wrapped
def user(): return session.get("user")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form.get("username", "").strip(), request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter a username, valid email, and password of at least 8 characters.", "error")
        else:
            try:
                result = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": {"username": name}}})
                if result.user and result.session:
                    session["user"] = {"id": result.user.id, "email": result.user.email, "username": name}; return redirect(url_for("home"))
                flash("Account created. Check your email to verify your address before signing in.", "success"); return redirect(url_for("login"))
            except Exception: flash("Unable to create that account. The email may already be registered.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            result = supabase.auth.sign_in_with_password({"email": request.form.get("email", "").strip().lower(), "password": request.form.get("password", "")})
            u = result.user
            if not u or not getattr(u, "email_confirmed_at", None):
                flash("Verify your email address before signing in.", "error"); return render_template("login.html")
            metadata = u.user_metadata or {}; session["user"] = {"id": u.id, "email": u.email, "username": metadata.get("username", u.email.split("@")[0])}; return redirect(url_for("home"))
        except Exception: flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/")
@required
def home():
    with db() as conn:
        income = conn.execute("select id, source, amount, date from income where user_id=%s order by date desc,id desc", (user()["id"],)).fetchall()
        expenses = conn.execute("select id, item, cost, date from expenses where user_id=%s order by date desc,id desc", (user()["id"],)).fetchall()
    total_income = sum((r["amount"] for r in income), Decimal("0")); total_expenses = sum((r["cost"] for r in expenses), Decimal("0"))
    return render_template("dashboard.html", username=user()["username"], income_rows=income, expense_rows=expenses, net_profit=total_income-total_expenses)

def amount(value):
    try:
        n = Decimal(value)
        if n <= 0: raise InvalidOperation
        return n
    except (InvalidOperation, TypeError): raise ValueError

@app.post("/add_income")
@required
def add_income():
    try:
        with db() as conn: conn.execute("insert into income(user_id,source,amount,date) values(%s,%s,%s,%s)", (user()["id"], request.form.get("source", "").strip(), amount(request.form.get("amount")), request.form.get("date")))
    except (ValueError, psycopg.Error): flash("Income could not be saved. Check the amount and date.", "error")
    return redirect(url_for("home"))

@app.post("/add_expense")
@required
def add_expense():
    try:
        with db() as conn: conn.execute("insert into expenses(user_id,item,cost,date) values(%s,%s,%s,%s)", (user()["id"], request.form.get("item", "").strip(), amount(request.form.get("cost")), request.form.get("date")))
    except (ValueError, psycopg.Error): flash("Expense could not be saved. Check the amount and date.", "error")
    return redirect(url_for("home"))

@app.post("/delete/<table_name>/<int:entry_id>")
@required
def delete_entry(table_name, entry_id):
    if table_name in {"income", "expenses"}:
        with db() as conn: conn.execute(f"delete from {table_name} where id=%s and user_id=%s", (entry_id, user()["id"]))
    return redirect(url_for("home"))

if __name__ == "__main__": app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
