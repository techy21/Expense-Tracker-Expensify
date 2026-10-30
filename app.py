import os

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

with app.app_context():
    init_db()
    seed_db()


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
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded sample data mirroring seed_db() — replaced by DB queries in Step 5
    user = {
        "name": "Demo User",
        "email": "demo@expensify.com",
        "initials": "DU",
        "member_since": "October 2026",
    }
    stats = {
        "total_spent": 265.54,
        "transaction_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "25 Oct 2026", "description": "Groceries", "category": "Food", "amount": 42.30},
        {"date": "20 Oct 2026", "description": "Gift wrap", "category": "Other", "amount": 10.00},
        {"date": "15 Oct 2026", "description": "New shoes", "category": "Shopping", "amount": 49.99},
        {"date": "12 Oct 2026", "description": "Movie night", "category": "Entertainment", "amount": 30.00},
        {"date": "08 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 15.75},
        {"date": "05 Oct 2026", "description": "Electricity", "category": "Bills", "amount": 80.00},
        {"date": "03 Oct 2026", "description": "Bus pass", "category": "Transport", "amount": 25.00},
        {"date": "01 Oct 2026", "description": "Lunch", "category": "Food", "amount": 12.50},
    ]
    categories = [
        {"name": "Bills", "total": 80.00, "percent": 30},
        {"name": "Food", "total": 54.80, "percent": 21},
        {"name": "Shopping", "total": 49.99, "percent": 19},
        {"name": "Entertainment", "total": 30.00, "percent": 11},
        {"name": "Transport", "total": 25.00, "percent": 9},
        {"name": "Health", "total": 15.75, "percent": 6},
        {"name": "Other", "total": 10.00, "percent": 4},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
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
