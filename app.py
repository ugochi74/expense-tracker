import os
from email.utils import parseaddr
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from flask import Flask, flash, redirect, render_template, request, session, url_for
from supabase import create_client

def load_local_env(path=Path(__file__).with_name(".env")):
    """Load simple KEY=VALUE settings for local runs without overriding exports."""
    try:
        with open(path, encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value.strip('"').strip("'")
    except OSError:
        pass

load_local_env()

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

def valid_email(value):
    """Return a normalized email only when it has a real local/domain part."""
    address = (value or "").strip().lower()
    _, parsed = parseaddr(address)
    if parsed != address or "@" not in address:
        return None
    local, domain = address.rsplit("@", 1)
    return address if local and domain and "." in domain else None

def auth_ready():
    if supabase is None:
        flash("Authentication is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.", "error")
        return False
    return True

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        email = valid_email(request.form.get("email"))
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter a username, valid email, and password of at least 8 characters.", "error")
        elif not auth_ready():
            pass
        else:
            try:
                result = supabase.auth.sign_up({"email": email, "password": password, "options": {"data": {"username": name}}})
                if result.user and result.session:
                    session["user"] = {"id": result.user.id, "email": result.user.email, "username": name}; return redirect(url_for("home"))
                flash("Account created. Check your email to verify your address before signing in.", "success"); return redirect(url_for("login"))
            except Exception as exc:
                app.logger.warning("Signup failed: %s", exc)
                flash("Unable to create that account. The email may already be registered or the service is unavailable.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = valid_email(request.form.get("email"))
        password = request.form.get("password", "")
        if not email or not password:
            flash("Enter a valid email and password.", "error")
            return render_template("login.html")
        if not auth_ready():
            return render_template("login.html")
        try:
            result = supabase.auth.sign_in_with_password({"email": email, "password": password})
            u = result.user
            confirmed_at = getattr(u, "email_confirmed_at", None) or getattr(u, "confirmed_at", None)
            if not u or not confirmed_at:
                flash("Verify your email address before signing in.", "error"); return render_template("login.html")
            metadata = u.user_metadata or {}; session["user"] = {"id": u.id, "email": u.email, "username": metadata.get("username", u.email.split("@")[0])}; return redirect(url_for("home"))
        except Exception as exc:
            app.logger.info("Login failed for %s: %s", email, exc)
            # Supabase raises for unverified accounts before returning a user.
            # Keep credential failures generic, but give verification failures
            # the action the user can actually take.
            error_code = str(getattr(exc, "code", "")).lower()
            error_text = str(exc).lower()
            if "email_not_confirmed" in error_code or "email not confirmed" in error_text:
                flash("Verify your email address before signing in.", "error")
            elif "invalid login credentials" in error_text or "invalid email or password" in error_text:
                flash("Invalid email or password.", "error")
            else:
                flash("Unable to sign in right now. Please try again.", "error")
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
