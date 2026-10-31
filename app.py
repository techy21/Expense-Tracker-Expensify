import calendar
import os
from datetime import date, datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_db,
    get_user_by_email,
    get_user_categories,
    get_user_profile,
    get_user_stats,
    get_user_transactions,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

with app.app_context():
    init_db()
    seed_db()


def normalise_date(value):
    """Return value as YYYY-MM-DD, or None if blank; raise ValueError if invalid."""
    value = value.strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def parse_date_filter(args):
    """Return (start_date, end_date, error); bad input gives (None, None, message)."""
    try:
        start_date = normalise_date(args.get("start_date", ""))
        end_date = normalise_date(args.get("end_date", ""))
    except ValueError:
        return None, None, "Please enter valid dates."

    # ISO date strings sort in date order, so they can be compared directly.
    if start_date and end_date and start_date > end_date:
        return None, None, "Start date must be on or before the end date."

    return start_date, end_date, None


def get_date_presets(today):
    """Return the quick filters; both cover whole calendar months up to this month's end."""
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day).isoformat()

    months_back = 2  # the current month plus the two before it
    total_months = today.year * 12 + (today.month - 1) - months_back
    year, zero_based_month = divmod(total_months, 12)
    three_months_start = date(year, zero_based_month + 1, 1).isoformat()

    return [
        {
            "label": "This month",
            "start_date": today.replace(day=1).isoformat(),
            "end_date": month_end,
        },
        {
            "label": "Last 3 months",
            "start_date": three_months_start,
            "end_date": month_end,
        },
    ]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    duplicate_error = "An account with this email is already registered."
    error = None
    if not name or not email or not password:
        error = "All fields are required."
    elif "@" not in email:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif get_user_by_email(email):
        error = duplicate_error
    elif create_user(name, email, password) is None:
        error = duplicate_error

    if error:
        return render_template("register.html", error=error, name=name, email=email)

    flash("Account created. Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = None
    error = None
    if not email or not password:
        error = "Email and password are required."
    else:
        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid email or password."

    if error:
        return render_template("login.html", error=error, email=email)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_profile(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    start_date, end_date, filter_error = parse_date_filter(request.args)

    return render_template(
        "profile.html",
        user=user,
        stats=get_user_stats(user_id, start_date, end_date),
        transactions=get_user_transactions(user_id, start_date, end_date),
        categories=get_user_categories(user_id, start_date, end_date),
        start_date=start_date,
        end_date=end_date,
        filter_error=filter_error,
        date_presets=get_date_presets(date.today()),
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
