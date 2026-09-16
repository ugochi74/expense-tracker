import os
import time
from email.utils import parseaddr
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
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
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY) if SUPABASE_URL and SUPABASE_ANON_KEY else None

# How many seconds before actual expiry we proactively refresh the token.
# This avoids a request failing right at the boundary.
TOKEN_REFRESH_BUFFER_SECONDS = 60


def store_session(auth_session):
    """Save everything needed to authenticate and later refresh, from a Supabase auth session."""
    session["access_token"] = auth_session.access_token
    session["refresh_token"] = auth_session.refresh_token
    # expires_at is not guaranteed by Supabase and can come back as None —
    # fall back to computing it from expires_in (which is always present)
    # so downstream expiry math never operates on None.
    session["expires_at"] = auth_session.expires_at or (time.time() + auth_session.expires_in)


def data_client():
    """
    Return a Supabase client authenticated as the current user for RLS.
    Automatically refreshes the access token if it has expired or is about
    to, using the stored refresh token — this is what was missing before,
    and is why queries started failing with "JWT expired" after ~1 hour.
    """
    if not supabase:
        raise RuntimeError("Supabase is not configured")

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    expires_at = session.get("expires_at") or 0  # treat missing/None as "already expired"

    if not access_token or not refresh_token:
        raise RuntimeError("Supabase session is missing")

    if time.time() >= expires_at - TOKEN_REFRESH_BUFFER_SECONDS:
        try:
            refreshed = supabase.auth.refresh_session(refresh_token)
            store_session(refreshed.session)
            access_token = refreshed.session.access_token
        except Exception as exc:
            # The refresh token itself is invalid/expired — the user genuinely
            # needs to log in again, not just retry.
            session.clear()
            raise RuntimeError("Your session has expired. Please log in again.") from exc

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


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
                    session["user"] = {"id": result.user.id, "email": result.user.email, "username": name}
                    store_session(result.session)
                    return redirect(url_for("home"))
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
            metadata = u.user_metadata or {}
            session["user"] = {"id": u.id, "email": u.email, "username": metadata.get("username", u.email.split("@")[0])}
            store_session(result.session)
            return redirect(url_for("home"))
        except Exception as exc:
            app.logger.info("Login failed for %s: %s", email, exc)
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
    try:
        client = data_client()
        income = client.table("income").select("id,source,amount,date").eq("user_id", user()["id"]).order("date", desc=True).order("id", desc=True).execute().data
        expenses = client.table("expenses").select("id,item,cost,date").eq("user_id", user()["id"]).order("date", desc=True).order("id", desc=True).execute().data
        plans = client.table("plans").select("id,goal,target_amount,target_date").eq("user_id", user()["id"]).order("target_date").execute().data
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login"))
    except Exception:
        app.logger.exception("Unable to load dashboard data")
        flash("Your data is temporarily unavailable. Please try again shortly.", "error")
        income, expenses, plans = [], [], []
    # PostgREST may decode numeric columns as strings or floats; normalize before arithmetic.
    total_income = sum((Decimal(str(r["amount"])) for r in income), Decimal("0"))
    total_expenses = sum((Decimal(str(r["cost"])) for r in expenses), Decimal("0"))
    return render_template("dashboard.html", username=user()["username"], income_rows=income, expense_rows=expenses, plan_rows=plans, net_profit=total_income-total_expenses)


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
        data_client().table("income").insert({"user_id": user()["id"], "source": request.form.get("source", "").strip(), "amount": str(amount(request.form.get("amount"))), "date": request.form.get("date")}).execute()
        flash("Income added successfully!", "success")
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login"))
    except Exception:
        flash("Income could not be saved. Check the amount and date.", "error")
    return redirect(url_for("home"))


@app.post("/add_expense")
@required
def add_expense():
    try:
        data_client().table("expenses").insert({"user_id": user()["id"], "item": request.form.get("item", "").strip(), "cost": str(amount(request.form.get("cost"))), "date": request.form.get("date")}).execute()
        flash("Expense added successfully!", "success")
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login"))
    except Exception:
        flash("Expense could not be saved. Check the amount and date.", "error")
    return redirect(url_for("home"))


@app.post("/add_plan")
@required
def add_plan():
    try:
        data_client().table("plans").insert({"user_id": user()["id"], "goal": request.form.get("goal", "").strip(), "target_amount": str(amount(request.form.get("target_amount"))), "target_date": request.form.get("target_date")}).execute()
        flash("Plan added successfully!", "success")
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login"))
    except Exception:
        flash("Plan could not be saved. Check the amount and date.", "error")
    return redirect(url_for("home"))


@app.post("/edit/<table_name>/<int:entry_id>")
@required
def edit_entry(table_name, entry_id):
    if table_name not in {"income", "expenses", "plans"}:
        return redirect(url_for("home"))
    try:
        if table_name == "income":
            payload = {
                "source": request.form.get("source", "").strip(),
                "amount": str(amount(request.form.get("amount"))),
                "date": request.form.get("date"),
            }
        elif table_name == "expenses":
            payload = {
                "item": request.form.get("item", "").strip(),
                "cost": str(amount(request.form.get("cost"))),
                "date": request.form.get("date"),
            }
        else:
            payload = {
                "goal": request.form.get("goal", "").strip(),
                "target_amount": str(amount(request.form.get("target_amount"))),
                "target_date": request.form.get("target_date"),
            }
        data_client().table(table_name).update(payload).eq("id", entry_id).eq("user_id", user()["id"]).execute()
    except RuntimeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("login"))
    except Exception:
        flash("The entry could not be updated. Check the amount and date.", "error")
    return redirect(url_for("home"))


@app.post("/delete/<table_name>/<int:entry_id>")
@required
def delete_entry(table_name, entry_id):
    if table_name in {"income", "expenses", "plans"}:
        try:
            data_client().table(table_name).delete().eq("id", entry_id).eq("user_id", user()["id"]).execute()
        except RuntimeError as exc:
            flash(str(exc), "error")
            return redirect(url_for("login"))
        except Exception:
            app.logger.exception("Unable to delete %s entry %s", table_name, entry_id)
            flash("The entry could not be deleted right now. Please try again.", "error")
    return redirect(url_for("home"))


if __name__ == "__main__": app.run(debug=os.environ.get("FLASK_DEBUG") == "1")