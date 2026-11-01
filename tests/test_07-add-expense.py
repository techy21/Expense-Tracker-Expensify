"""Tests for Step 07: Add Expense.

Based on .claude/specs/07-add-expense.md.

Isolation: database.db.DB_PATH is pointed at a temporary file before ``app``
is imported (app.py runs init_db()/seed_db() at import) and again per test,
so the real expense_tracker.db is never touched.
"""
import atexit
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import date

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database.db as db_module  # noqa: E402

_IMPORT_TMP_DIR = tempfile.mkdtemp(prefix="expensify_import_")
atexit.register(shutil.rmtree, _IMPORT_TMP_DIR, ignore_errors=True)

_original_db_path = db_module.DB_PATH
db_module.DB_PATH = os.path.join(_IMPORT_TMP_DIR, "import.db")
try:
    import app as app_module  # noqa: E402
finally:
    db_module.DB_PATH = _original_db_path

flask_app = app_module.app

PASSWORD = "password123"
ALICE_EMAIL = "alice@example.com"
BOB_EMAIL = "bob@example.com"
EXPECTED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]


# ---------------------------------------------------------------------- #
# Helpers                                                                 #
# ---------------------------------------------------------------------- #

def query(sql, params=()):
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def execute(sql, params=()):
    conn = sqlite3.connect(db_module.DB_PATH)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def expense_rows(user_id=None):
    if user_id is None:
        return query("SELECT * FROM expenses")
    return query("SELECT * FROM expenses WHERE user_id = ?", (user_id,))


def login(client, email):
    return client.post("/login", data={"email": email, "password": PASSWORD})


def valid_form(**overrides):
    data = {
        "amount": "100.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Team lunch",
    }
    data.update(overrides)
    return data


def input_tag(body, name):
    match = re.search(r"<input\b[^>]*name=[\"']" + name + r"[\"'][^>]*>", body)
    assert match, f"Expected an <input> named {name}"
    return match.group(0)


def select_tag(body, name):
    match = re.search(
        r"<select\b[^>]*name=[\"']" + name + r"[\"'][^>]*>.*?</select>", body, re.S
    )
    assert match, f"Expected a <select> named {name}"
    return match.group(0)


# ---------------------------------------------------------------------- #
# Fixtures                                                                #
# ---------------------------------------------------------------------- #

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    flask_app.config.update({"TESTING": True, "CSRF_ENABLED": False})
    db_module.init_db()
    yield flask_app


@pytest.fixture
def users(app):
    alice = db_module.create_user("Alice Smith", ALICE_EMAIL, PASSWORD)
    bob = db_module.create_user("Bob Jones", BOB_EMAIL, PASSWORD)
    assert alice and bob, "Test users must be created"
    return {"alice": alice, "bob": bob}


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def alice_client(client, users):
    response = login(client, ALICE_EMAIL)
    assert response.status_code == 302, "Login should redirect on success"
    return client


@pytest.fixture
def bob_client(app, users):
    c = app.test_client()
    assert login(c, BOB_EMAIL).status_code == 302
    return c


# ---------------------------------------------------------------------- #
# Auth guard                                                              #
# ---------------------------------------------------------------------- #

class TestAuthGuard:
    def test_get_add_expense_logged_out_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_add_expense_logged_out_redirects_and_creates_no_row(self, client, users):
        response = client.post("/expenses/add", data=valid_form())
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert expense_rows() == [], "Logged-out POST must not create a row"

    @pytest.mark.parametrize("method", ["get", "post"])
    def test_deleted_user_session_redirects_to_login_without_error(
        self, alice_client, users, method
    ):
        execute("DELETE FROM users WHERE id = ?", (users["alice"],))
        response = getattr(alice_client, method)(
            "/expenses/add", data=valid_form() if method == "post" else None
        )
        assert response.status_code == 302, "Must redirect, not 500"
        assert "/login" in response.headers["Location"]
        assert expense_rows() == []
        with alice_client.session_transaction() as sess:
            assert "user_id" not in sess, "Stale session should be cleared"


# ---------------------------------------------------------------------- #
# GET form                                                                #
# ---------------------------------------------------------------------- #

class TestForm:
    def test_get_form_logged_in_returns_200(self, alice_client):
        response = alice_client.get("/expenses/add")
        assert response.status_code == 200

    def test_form_posts_to_add_expense_url(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        form = re.search(r"<form\b[^>]*>", body)
        assert form, "Expected a form"
        assert re.search(r"method=[\"']post[\"']", form.group(0), re.I)
        assert "/expenses/add" in form.group(0)

    def test_amount_input_attributes(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        tag = input_tag(body, "amount")
        assert "number" in tag
        assert "0.01" in tag
        assert "required" in tag
        assert "step" in tag

    def test_date_input_defaults_to_today_and_required(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        tag = input_tag(body, "date")
        assert "date" in tag and "required" in tag
        assert date.today().isoformat() in tag, "Date should default to today"

    def test_description_input_is_text_with_maxlength_200(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        tag = input_tag(body, "description")
        assert re.search(r"maxlength=[\"']200[\"']", tag)
        assert "required" not in tag, "Description is optional"

    def test_category_select_has_blank_option_and_all_seven_categories(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        select = select_tag(body, "category")
        assert "required" in re.search(r"<select\b[^>]*>", select).group(0)
        assert "Select a category" in select
        for category in EXPECTED_CATEGORIES:
            assert category in select, f"Missing category {category}"
        assert len(re.findall(r"<option\b", select)) == 8, "Blank option + 7 categories"

    def test_form_has_labels_for_each_field(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        for name in ("amount", "category", "date", "description"):
            assert re.search(r"<label\b[^>]*for=[\"']" + name + r"[\"']", body), (
                f"Expected a label for {name}"
            )

    def test_form_has_cancel_link_to_profile(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        assert re.search(r"<a\b[^>]*href=[\"']/profile[\"'][^>]*>\s*Cancel", body), (
            "Expected a Cancel link to /profile"
        )

    def test_form_extends_base_layout(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        assert "add_expense.css" in body, "Page should load add_expense.css"

    def test_cancel_target_returns_to_profile_without_creating_row(self, alice_client):
        response = alice_client.get("/profile")
        assert response.status_code == 200
        assert expense_rows() == []


# ---------------------------------------------------------------------- #
# Profile page link                                                       #
# ---------------------------------------------------------------------- #

class TestProfileLink:
    def test_profile_has_add_expense_link_without_expenses(self, alice_client):
        body = alice_client.get("/profile").get_data(as_text=True)
        assert re.search(
            r"<a\b[^>]*href=[\"']/expenses/add[\"'][^>]*>\s*(?:<[^>]+>\s*)*\+?\s*Add expense",
            body, re.I,
        ), "Expected an 'Add expense' link in the empty state"

    def test_profile_has_add_expense_link_with_expenses(self, alice_client, users):
        execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (users["alice"], 5.0, "Food", "2024-01-01", "existing"),
        )
        body = alice_client.get("/profile").get_data(as_text=True)
        assert re.search(
            r"<a\b[^>]*href=[\"']/expenses/add[\"'][^>]*>\s*(?:<[^>]+>\s*)*\+?\s*Add expense",
            body, re.I,
        ), "Expected an 'Add expense' link in the populated state"

    def test_add_expense_link_target_opens_form(self, alice_client):
        assert alice_client.get("/expenses/add").status_code == 200


# ---------------------------------------------------------------------- #
# Happy path                                                              #
# ---------------------------------------------------------------------- #

class TestHappyPath:
    def test_valid_submission_redirects_to_profile(self, alice_client):
        response = alice_client.post("/expenses/add", data=valid_form())
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile"), (
            "Should redirect to the unfiltered profile page"
        )

    def test_valid_submission_shows_success_message(self, alice_client):
        response = alice_client.post(
            "/expenses/add", data=valid_form(), follow_redirects=True
        )
        assert response.status_code == 200
        assert "Expense added." in response.get_data(as_text=True)

    def test_new_expense_appears_in_transactions_with_correct_details(self, alice_client):
        response = alice_client.post(
            "/expenses/add", data=valid_form(), follow_redirects=True
        )
        body = response.get_data(as_text=True)
        assert "Team lunch" in body
        assert "Food" in body
        assert "₹100.50" in body
        assert date.today().strftime("%d %b %Y") in body

    def test_stats_reflect_new_expense(self, alice_client):
        body = alice_client.post(
            "/expenses/add", data=valid_form(), follow_redirects=True
        ).get_data(as_text=True)
        assert body.count("₹100.50") >= 2, (
            "Total spent and Food category total should both show ₹100.50"
        )
        assert '<p class="stat-value">1</p>' in body, "Transaction count should be 1"

    def test_second_expense_increases_total_by_amount(self, alice_client):
        alice_client.post("/expenses/add", data=valid_form())
        body = alice_client.post(
            "/expenses/add",
            data=valid_form(amount="50", description="Second"),
            follow_redirects=True,
        ).get_data(as_text=True)
        assert "₹150.50" in body, "Total should be 100.50 + 50.00"
        assert '<p class="stat-value">2</p>' in body, "Transaction count should be 2"

    def test_db_row_has_session_user_amount_and_iso_date(self, alice_client, users):
        today = date.today().isoformat()
        alice_client.post("/expenses/add", data=valid_form())
        rows = expense_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row["user_id"] == users["alice"]
        assert row["amount"] == 100.5
        assert row["category"] == "Food"
        assert row["description"] == "Team lunch"
        assert row["date"] == today
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"])

    def test_refreshing_profile_does_not_duplicate_or_repeat_message(self, alice_client):
        alice_client.post("/expenses/add", data=valid_form(), follow_redirects=True)
        second = alice_client.get("/profile")
        assert "Expense added." not in second.get_data(as_text=True)
        assert len(expense_rows()) == 1

    def test_future_date_is_allowed_and_stored(self, alice_client):
        response = alice_client.post("/expenses/add", data=valid_form(date="2099-12-31"))
        assert response.status_code == 302
        assert expense_rows()[0]["date"] == "2099-12-31"

    def test_amount_is_rounded_to_two_decimals(self, alice_client):
        alice_client.post("/expenses/add", data=valid_form(amount="10.456"))
        rows = expense_rows()
        assert len(rows) == 1
        assert rows[0]["amount"] == 10.46

    @pytest.mark.parametrize("amount", ["0.01", "9999999.99"])
    def test_boundary_amounts_are_accepted(self, alice_client, amount):
        response = alice_client.post("/expenses/add", data=valid_form(amount=amount))
        assert response.status_code == 302
        assert expense_rows()[0]["amount"] == float(amount)

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_every_listed_category_is_accepted(self, alice_client, category):
        response = alice_client.post("/expenses/add", data=valid_form(category=category))
        assert response.status_code == 302
        assert expense_rows()[0]["category"] == category

    def test_description_of_exactly_200_chars_is_accepted(self, alice_client):
        alice_client.post("/expenses/add", data=valid_form(description="a" * 200))
        assert len(expense_rows()) == 1

    def test_description_is_stripped(self, alice_client):
        alice_client.post("/expenses/add", data=valid_form(description="  padded  "))
        assert expense_rows()[0]["description"] == "padded"

    @pytest.mark.parametrize("blank", ["", "   ", "\t "])
    def test_blank_description_is_stored_as_null(self, alice_client, blank):
        response = alice_client.post("/expenses/add", data=valid_form(description=blank))
        assert response.status_code == 302
        rows = expense_rows()
        assert len(rows) == 1
        assert rows[0]["description"] is None, "Blank description should be NULL"

    def test_missing_description_field_is_stored_as_null(self, alice_client):
        data = valid_form()
        del data["description"]
        response = alice_client.post("/expenses/add", data=data)
        assert response.status_code == 302
        assert expense_rows()[0]["description"] is None


# ---------------------------------------------------------------------- #
# Validation                                                              #
# ---------------------------------------------------------------------- #

class TestValidation:
    @pytest.mark.parametrize(
        "amount",
        ["0", "-5", "0.001", "abc", "nan", "inf", "-inf", "10000000", "", "   "],
    )
    def test_invalid_amount_shows_error_and_creates_no_row(self, alice_client, amount):
        response = alice_client.post("/expenses/add", data=valid_form(amount=amount))
        assert response.status_code == 200, "Validation errors re-render with 200"
        body = response.get_data(as_text=True)
        assert 'role="alert"' in body or "role='alert'" in body, "Expected an error alert"
        assert expense_rows() == []

    def test_missing_amount_field_shows_error(self, alice_client):
        data = valid_form()
        del data["amount"]
        response = alice_client.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert expense_rows() == []

    @pytest.mark.parametrize("category", ["Crypto", "food", "FOOD", "", " Food", "Food "])
    def test_invalid_category_shows_error_and_creates_no_row(self, alice_client, category):
        response = alice_client.post("/expenses/add", data=valid_form(category=category))
        assert response.status_code == 200
        assert 'role="alert"' in response.get_data(as_text=True)
        assert expense_rows() == []

    def test_missing_category_field_shows_error(self, alice_client):
        data = valid_form()
        del data["category"]
        response = alice_client.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert expense_rows() == []

    @pytest.mark.parametrize("bad_date", ["2026-02-30", "not-a-date", "", "   "])
    def test_invalid_date_shows_error_and_creates_no_row(self, alice_client, bad_date):
        response = alice_client.post("/expenses/add", data=valid_form(date=bad_date))
        assert response.status_code == 200
        assert 'role="alert"' in response.get_data(as_text=True)
        assert expense_rows() == []

    def test_missing_date_field_shows_error(self, alice_client):
        data = valid_form()
        del data["date"]
        response = alice_client.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert expense_rows() == []

    def test_description_over_200_chars_shows_error_and_creates_no_row(self, alice_client):
        response = alice_client.post(
            "/expenses/add", data=valid_form(description="a" * 201)
        )
        assert response.status_code == 200
        assert 'role="alert"' in response.get_data(as_text=True)
        assert expense_rows() == []

    def test_only_one_error_alert_is_shown_at_a_time(self, alice_client):
        response = alice_client.post(
            "/expenses/add",
            data=valid_form(amount="abc", category="Crypto", date="nope"),
        )
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert len(re.findall(r"role=[\"']alert[\"']", body)) == 1, (
            "Only one clear message at a time"
        )
        assert expense_rows() == []

    def test_no_error_alert_on_fresh_get(self, alice_client):
        body = alice_client.get("/expenses/add").get_data(as_text=True)
        assert not re.search(r"role=[\"']alert[\"']", body)

    def test_error_response_keeps_all_submitted_values(self, alice_client):
        response = alice_client.post(
            "/expenses/add",
            data={
                "amount": "-5",
                "category": "Transport",
                "date": "2031-07-04",
                "description": "Kept description",
            },
        )
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert 'value="-5"' in input_tag(body, "amount").replace("'", '"')
        assert "2031-07-04" in input_tag(body, "date")
        assert "Kept description" in input_tag(body, "description")
        selected = re.search(
            r"<option\b[^>]*value=[\"']Transport[\"'][^>]*>", select_tag(body, "category")
        )
        assert selected and "selected" in selected.group(0), "Category should stay selected"

    def test_error_response_escapes_submitted_description(self, alice_client):
        payload = '"><script>alert(1)</script>'
        response = alice_client.post(
            "/expenses/add", data=valid_form(amount="abc", description=payload)
        )
        body = response.get_data(as_text=True)
        assert "<script>alert(1)</script>" not in body, "Re-rendered value must be escaped"


# ---------------------------------------------------------------------- #
# Security and isolation                                                  #
# ---------------------------------------------------------------------- #

class TestSecurityAndIsolation:
    def test_user_id_in_request_is_ignored(self, alice_client, users):
        alice_client.post(
            "/expenses/add", data=valid_form(user_id=str(users["bob"]))
        )
        assert len(expense_rows(users["alice"])) == 1
        assert expense_rows(users["bob"]) == [], "user_id must come only from session"

    def test_expense_not_visible_on_other_users_profile(
        self, alice_client, bob_client, users
    ):
        alice_client.post(
            "/expenses/add", data=valid_form(description="alice-private-note")
        )
        body = bob_client.get("/profile").get_data(as_text=True)
        assert "alice-private-note" not in body
        assert "₹100.50" not in body

    def test_script_description_is_displayed_as_plain_text(self, alice_client):
        payload = "<script>alert(1)</script>"
        body = alice_client.post(
            "/expenses/add", data=valid_form(description=payload), follow_redirects=True
        ).get_data(as_text=True)
        assert payload not in body, "Raw script tag must not be rendered"
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_sql_injection_description_is_stored_as_plain_text(self, alice_client):
        payload = "'); DROP TABLE expenses; --"
        response = alice_client.post("/expenses/add", data=valid_form(description=payload))
        assert response.status_code == 302
        rows = expense_rows()
        assert len(rows) == 1
        assert rows[0]["description"] == payload
        tables = query("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
        assert tables, "expenses table must still exist"

    def test_sql_injection_in_category_is_rejected(self, alice_client):
        response = alice_client.post(
            "/expenses/add", data=valid_form(category="Food'; DROP TABLE expenses; --")
        )
        assert response.status_code == 200
        assert expense_rows() == []


# ---------------------------------------------------------------------- #
# Helper and stub routes                                                  #
# ---------------------------------------------------------------------- #

class TestHelperAndStubs:
    def test_create_expense_helper_inserts_row_and_returns_id(self, users):
        new_id = db_module.create_expense(
            users["alice"], 12.34, "Bills", "2024-03-05", "helper"
        )
        rows = query("SELECT * FROM expenses WHERE id = ?", (new_id,))
        assert len(rows) == 1
        row = rows[0]
        assert row["user_id"] == users["alice"]
        assert row["amount"] == 12.34
        assert row["category"] == "Bills"
        assert row["date"] == "2024-03-05"
        assert row["description"] == "helper"
        assert row["created_at"], "created_at should be populated"

    def test_edit_stub_route_still_returns_stub_text(self, alice_client):
        response = alice_client.get("/expenses/1/edit")
        assert response.status_code == 200
        assert "Edit expense" in response.get_data(as_text=True)
        assert "coming in Step 8" in response.get_data(as_text=True)

    def test_delete_stub_route_still_returns_stub_text(self, alice_client):
        response = alice_client.get("/expenses/1/delete")
        assert response.status_code == 200
        assert "Delete expense" in response.get_data(as_text=True)
        assert "coming in Step 9" in response.get_data(as_text=True)

    def test_app_py_contains_no_sql(self):
        with open(os.path.join(PROJECT_ROOT, "app.py"), encoding="utf-8") as handle:
            source = handle.read()
        # Match whole SQL statements and DB calls, so ordinary English such as
        # "Please select a valid category." is not mistaken for SQL.
        sql_patterns = (
            r"\bSELECT\b.+\bFROM\b",
            r"\bINSERT\s+INTO\b",
            r"\bUPDATE\b.+\bSET\b",
            r"\bDELETE\s+FROM\b",
            r"\bCREATE\s+TABLE\b",
            r"\.execute(many|script)?\(",
        )
        for pattern in sql_patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            assert match is None, f"app.py must not contain SQL: {match and match.group(0)}"


# ---------------------------------------------------------------------- #
# CSRF protection (added after code review)                               #
# ---------------------------------------------------------------------- #

def form_token(client, path):
    body = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([0-9a-f]+)"', body)
    assert match, f"Expected a CSRF token field on {path}"
    return match.group(1)


class TestCsrf:
    @pytest.fixture(autouse=True)
    def enable_csrf(self, app):
        app.config["CSRF_ENABLED"] = True

    @pytest.fixture
    def signed_in(self, app, users):
        client = app.test_client()
        response = client.post(
            "/login",
            data={
                "email": ALICE_EMAIL,
                "password": PASSWORD,
                "csrf_token": form_token(client, "/login"),
            },
        )
        assert response.status_code == 302
        return client

    @pytest.mark.parametrize("path", ["/login", "/register"])
    def test_public_post_without_token_is_rejected(self, app, path):
        client = app.test_client()
        client.get(path)
        assert client.post(path, data={}).status_code == 400

    @pytest.mark.parametrize("path", ["/login", "/register"])
    def test_public_post_without_any_session_is_rejected(self, app, path):
        assert app.test_client().post(path, data={}).status_code == 400

    def test_add_expense_with_valid_token_saves(self, signed_in):
        token = form_token(signed_in, "/expenses/add")
        response = signed_in.post("/expenses/add", data=valid_form(csrf_token=token))
        assert response.status_code == 302
        assert len(expense_rows()) == 1

    def test_add_expense_without_token_is_rejected(self, signed_in):
        signed_in.get("/expenses/add")
        response = signed_in.post("/expenses/add", data=valid_form())
        assert response.status_code == 400
        assert expense_rows() == []

    @pytest.mark.parametrize("token", ["wrong", "", "tökén"])
    def test_add_expense_with_bad_token_is_rejected(self, signed_in, token):
        signed_in.get("/expenses/add")
        response = signed_in.post("/expenses/add", data=valid_form(csrf_token=token))
        assert response.status_code == 400
        assert expense_rows() == []

    def test_token_from_another_session_is_rejected(self, app, signed_in):
        other = app.test_client()
        other_token = form_token(other, "/login")
        signed_in.get("/expenses/add")
        response = signed_in.post("/expenses/add", data=valid_form(csrf_token=other_token))
        assert response.status_code == 400
        assert expense_rows() == []

    def test_register_with_valid_token_creates_user(self, app):
        client = app.test_client()
        response = client.post(
            "/register",
            data={
                "name": "Cara",
                "email": "cara@example.com",
                "password": PASSWORD,
                "csrf_token": form_token(client, "/register"),
            },
        )
        assert response.status_code == 302
        assert db_module.get_user_by_email("cara@example.com") is not None

    def test_session_cookie_is_samesite_lax(self, app):
        client = app.test_client()
        response = client.get("/login")
        assert "SameSite=Lax" in response.headers.get("Set-Cookie", "")
