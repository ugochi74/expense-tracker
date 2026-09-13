# Expense Tracker

This Flask app uses Supabase Auth for signup/login/email verification and PostgreSQL (the database included with Supabase) for user-scoped income and expense records.

## Setup

1. Create a Supabase project. In Authentication settings, enable email confirmations and set the site URL/redirect URLs for your Render app.
2. Run [`schema.sql`](schema.sql) in the Supabase SQL Editor.
3. Copy [`.env.example`](.env.example) to `.env` and set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`, and a random `SECRET_KEY`.
4. Install dependencies with `pip install -r requirements.txt` and run `gunicorn app:app`.

On Render, add the same variables in the service Environment settings. Never use a Supabase service-role key in this app; the anon key is sufficient for authentication, while the server enforces `user_id` ownership on every query.
