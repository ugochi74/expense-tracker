import argparse
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

DATABASE = "income_tracker.db"


def connect_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database():
    with connect_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_cents INTEGER NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                income_date TEXT NOT NULL,
                note TEXT
            )
        """)


def money_to_cents(amount):
    try:
        value = Decimal(str(amount))
        if value <= 0:
            raise ValueError
        return int(value * 100)
    except (InvalidOperation, ValueError):
        raise ValueError("Amount must be a positive number, such as 1250.50")


def format_money(cents):
    return f"${cents / 100:,.2f}"


def add_income(args):
    amount_cents = money_to_cents(args.amount)

    with connect_db() as connection:
        connection.execute("""
            INSERT INTO income
            (amount_cents, source, category, income_date, note)
            VALUES (?, ?, ?, ?, ?)
        """, (
            amount_cents,
            args.source,
            args.category,
            args.date,
            args.note
        ))

    print(f"Added {format_money(amount_cents)} from {args.source}")


def list_income(args):
    query = """
        SELECT id, amount_cents, source, category, income_date, note
        FROM income
        WHERE 1 = 1
    """
    parameters = []

    if args.month:
        query += " AND income_date LIKE ?"
        parameters.append(f"{args.month}%")

    if args.category:
        query += " AND category = ?"
        parameters.append(args.category)

    query += " ORDER BY income_date DESC, id DESC"

    with connect_db() as connection:
        rows = connection.execute(query, parameters).fetchall()

    if not rows:
        print("No income records found.")
        return

    print(f"{'ID':<4} {'Date':<12} {'Amount':>12}  {'Source':<20} {'Category':<15} Note")
    print("-" * 90)

    for row in rows:
        print(
            f"{row['id']:<4} "
            f"{row['income_date']:<12} "
            f"{format_money(row['amount_cents']):>12}  "
            f"{row['source']:<20} "
            f"{row['category']:<15} "
            f"{row['note'] or ''}"
        )


def show_summary(args):
    query = """
        SELECT category, SUM(amount_cents) AS total
        FROM income
        WHERE 1 = 1
    """
    parameters = []

    if args.month:
        query += " AND income_date LIKE ?"
        parameters.append(f"{args.month}%")

    query += " GROUP BY category ORDER BY total DESC"

    with connect_db() as connection:
        rows = connection.execute(query, parameters).fetchall()

    if not rows:
        print("No income records found.")
        return

    total = sum(row["total"] for row in rows)

    print("Income Summary")
    print("-" * 30)

    for row in rows:
        print(f"{row['category']:<20} {format_money(row['total']):>10}")

    print("-" * 30)
    print(f"{'Total':<20} {format_money(total):>10}")


def delete_income(args):
    with connect_db() as connection:
        row = connection.execute(
            "SELECT * FROM income WHERE id = ?",
            (args.id,)
        ).fetchone()

        if not row:
            print("Income record not found.")
            return

        connection.execute(
            "DELETE FROM income WHERE id = ?",
            (args.id,)
        )

    print(f"Deleted income record #{args.id}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Track your income using SQLite."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser(
        "add",
        help="Add an income record"
    )
    add_parser.add_argument("amount", help="Income amount, e.g. 1250.50")
    add_parser.add_argument("--source", required=True, help="Income source")
    add_parser.add_argument(
        "--category",
        default="Other",
        help="Category, e.g. Salary, Freelance, Business"
    )
    add_parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date in YYYY-MM-DD format"
    )
    add_parser.add_argument("--note", default="", help="Optional note")
    add_parser.set_defaults(function=add_income)

    list_parser = subparsers.add_parser(
        "list",
        help="List income records"
    )
    list_parser.add_argument(
        "--month",
        help="Filter by month, e.g. 2025-03"
    )
    list_parser.add_argument(
        "--category",
        help="Filter by category"
    )
    list_parser.set_defaults(function=list_income)

    summary_parser = subparsers.add_parser(
        "summary",
        help="Show income totals"
    )
    summary_parser.add_argument(
        "--month",
        help="Show summary for a month, e.g. 2025-03"
    )
    summary_parser.set_defaults(function=show_summary)

    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete an income record"
    )
    delete_parser.add_argument(
        "id",
        type=int,
        help="ID of the record to delete"
    )
    delete_parser.set_defaults(function=delete_income)

    return parser


def main():
    setup_database()

    parser = build_parser()
    args = parser.parse_args()

    try:
        args.function(args)
    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()