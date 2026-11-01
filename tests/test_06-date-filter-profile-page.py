"""Tests for Step 06: date filter on the profile page.

Based on .claude/specs/06-date-filter-profile-page.md.

Isolation: database.db.DB_PATH is pointed at a temporary file before ``app``
is imported (app.py runs init_db()/seed_db() at import) and again per test,
so the real expense_tracker.db is never touched.
"""
import atexit
import calendar
import html as html_lib
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from urllib.parse import parse_qs, urlparse

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


# ---------------------------------------------------------------------- #
# Helpers                                                                 #
# ---------------------------------------------------------------------- #

def month_start_shift(d, delta_months):
    """First day of the month that is delta_months away from d's month."""
    year, month_index = divmod(d.year * 12 + d.month - 1 + delta_months, 12)
    return date(year, month_index + 1, 1)


def month_end_of(d):
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def add_expense(user_id, amount, category, on_date, description):
    conn = sqlite3.connect(db_module.DB_PATH)
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, on_date.isoformat(), description),
        )
        conn.commit()
    finally:
        conn.close()


def login(client, email):
    return client.post(
        "/login", data={"email": email, "password": PASSWORD}, follow_redirects=False
    )


def page(client, **params):
    response = client.get("/profile", query_string=params)
    return response, response.get_data(as_text=True)


def stat_shown(body, value):
    """True if value appears as the sole text of some element, e.g. >3<."""
    return re.search(r">\s*" + re.escape(str(value)) + r"\s*<", body) is not None


def preset_anchor(body, label):
    """Return (opening_tag_attributes, href) of the anchor labelled `label`."""
    match = re.search(
        r"<a\b([^>]*)>\s*(?:<[^>]+>\s*)*" + re.escape(label) + r"\s*(?:<[^>]+>\s*)*</a>",
        body,
    )
    assert match, f"Expected a link labelled {label!r} on the profile page"
    attrs = match.group(1)
    href_match = re.search(r'href="([^"]*)"', attrs)
    assert href_match, f"Link {label!r} must have an href"
    return attrs, html_lib.unescape(href_match.group(1))


def preset_range(body, label):
    _, href = preset_anchor(body, label)
    query = parse_qs(urlparse(href).query)
    return query.get("start_date", [None])[0], query.get("end_date", [None])[0], href


def date_input_tag(body, name):
    match = re.search(r'<input\b[^>]*name="' + name + r'"[^>]*>', body)
    assert match, f"Expected an <input> named {name}"
    return match.group(0)


def error_signal(body):
    lowered = body.lower()
    return sum(lowered.count(word) for word in ("error", "invalid", "valid date", "must be"))


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
def may_data(users):
    """Alice gets 8 expenses in a fixed month (2024-05); Bob gets one decoy."""
    uid = users["alice"]
    rows = [
        (12.50, "Food", 1, "alice-lunch"),
        (25.00, "Transport", 3, "alice-bus"),
        (80.00, "Bills", 5, "alice-electric"),
        (15.75, "Health", 8, "alice-pharmacy"),
        (30.00, "Entertainment", 12, "alice-movie"),
        (49.99, "Shopping", 15, "alice-shoes"),
        (10.00, "Other", 20, "alice-giftwrap"),
        (42.30, "Food", 25, "alice-groceries"),
    ]
    for amount, category, day, description in rows:
        add_expense(uid, amount, category, date(2024, 5, day), description)
    add_expense(users["bob"], 999.99, "Shopping", date(2024, 5, 2), "bob-secret-purchase")
    return users


@pytest.fixture
def alice_client(client, may_data):
    response = login(client, ALICE_EMAIL)
    assert response.status_code == 302, "Login should redirect on success"
    return client


ALL_ALICE = {
    "alice-lunch", "alice-bus", "alice-electric", "alice-pharmacy",
    "alice-movie", "alice-shoes", "alice-giftwrap", "alice-groceries",
}


def present(body, descriptions):
    return {d for d in descriptions if d in body}


# ---------------------------------------------------------------------- #
# Auth guard                                                              #
# ---------------------------------------------------------------------- #

class TestAuthGuard:
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"start_date": "2026-01-01"},
            {"start_date": "2026-01-01", "end_date": "2026-02-01"},
            {"start_date": "not-a-date"},
        ],
    )
    def test_profile_logged_out_with_filter_redirects_to_login(self, client, params):
        response = client.get("/profile", query_string=params)
        assert response.status_code == 302, "Logged-out request must redirect"
        assert urlparse(response.headers["Location"]).path == "/login", (
            "Logged-out request must redirect to /login"
        )


# ---------------------------------------------------------------------- #
# Unfiltered behaviour                                                    #
# ---------------------------------------------------------------------- #

class TestUnfiltered:
    def test_no_params_shows_all_expenses_and_totals(self, alice_client):
        response, body = page(alice_client)
        assert response.status_code == 200
        assert present(body, ALL_ALICE) == ALL_ALICE, "All 8 transactions expected"
        assert "₹265.54" in body, "Total of all expenses expected"
        assert stat_shown(body, 8), "Transaction count 8 expected"
        assert "Bills" in body, "Top category Bills expected"

    def test_blank_params_behave_like_no_filter(self, alice_client):
        response, body = page(alice_client, start_date="", end_date="")
        assert response.status_code == 200
        assert present(body, ALL_ALICE) == ALL_ALICE
        assert "₹265.54" in body
        assert error_signal(body) == error_signal(page(alice_client)[1]), (
            "Blank filter values must not produce an error"
        )

    def test_filter_form_is_present_with_expected_fields(self, alice_client):
        _, body = page(alice_client)
        assert re.search(r"<form\b[^>]*method=\"get\"", body, re.I), "GET filter form expected"
        assert 'type="date"' in date_input_tag(body, "start_date")
        assert 'type="date"' in date_input_tag(body, "end_date")
        assert "Apply" in body, "Apply button expected"
        assert "This month" in body and "Last 3 months" in body

    def test_clear_link_hidden_when_no_filter_applied(self, alice_client):
        _, body = page(alice_client)
        assert not re.search(r">\s*Clear\s*<", body), "Clear must not show without a filter"

    def test_unfiltered_page_has_no_date_range_empty_messages(self, alice_client):
        _, body = page(alice_client)
        assert "No transactions in this date range." not in body
        assert "No spending in this date range." not in body


# ---------------------------------------------------------------------- #
# Filtering behaviour (spec definition-of-done numbers)                   #
# ---------------------------------------------------------------------- #

class TestFiltering:
    def test_range_day1_to_day5_stats_rows_and_categories(self, alice_client):
        response, body = page(alice_client, start_date="2024-05-01", end_date="2024-05-05")
        assert response.status_code == 200
        assert "₹117.50" in body
        assert stat_shown(body, 3), "3 transactions expected"
        assert present(body, ALL_ALICE) == {"alice-lunch", "alice-bus", "alice-electric"}
        for excluded in ("Health", "Entertainment", "Shopping"):
            assert excluded not in body, f"{excluded} is outside the range"
        for included in ("Bills", "Transport", "Food"):
            assert included in body

    def test_range_day1_to_day5_category_percentages(self, alice_client):
        _, body = page(alice_client, start_date="2024-05-01", end_date="2024-05-05")
        for pct in ("68%", "21%", "11%"):
            assert pct in body, f"Expected percentage {pct} computed against range total"

    def test_single_day_range_is_inclusive_on_both_bounds(self, alice_client):
        _, body = page(alice_client, start_date="2024-05-12", end_date="2024-05-12")
        assert "₹30.00" in body
        assert stat_shown(body, 1)
        assert present(body, ALL_ALICE) == {"alice-movie"}
        assert "Entertainment" in body

    def test_start_only_means_from_date_onward(self, alice_client):
        _, body = page(alice_client, start_date="2024-05-20")
        assert "₹52.30" in body
        assert stat_shown(body, 2)
        assert present(body, ALL_ALICE) == {"alice-giftwrap", "alice-groceries"}

    def test_end_only_means_up_to_date(self, alice_client):
        _, body = page(alice_client, end_date="2024-05-03")
        assert "₹37.50" in body
        assert stat_shown(body, 2)
        assert present(body, ALL_ALICE) == {"alice-lunch", "alice-bus"}

    def test_start_bound_is_inclusive(self, alice_client):
        _, body = page(alice_client, start_date="2024-05-25")
        assert "alice-groceries" in body and "alice-giftwrap" not in body

    def test_end_bound_is_inclusive(self, alice_client):
        _, body = page(alice_client, end_date="2024-05-01")
        assert "alice-lunch" in body and "alice-bus" not in body

    def test_filter_range_spanning_whole_dataset_matches_unfiltered(self, alice_client):
        _, body = page(alice_client, start_date="2000-01-01", end_date="2100-12-31")
        assert present(body, ALL_ALICE) == ALL_ALICE
        assert "₹265.54" in body

    def test_refresh_keeps_results_and_date_inputs(self, alice_client):
        params = {"start_date": "2024-05-01", "end_date": "2024-05-05"}
        _, first = page(alice_client, **params)
        _, second = page(alice_client, **params)
        for body in (first, second):
            assert "₹117.50" in body
            assert 'value="2024-05-01"' in date_input_tag(body, "start_date")
            assert 'value="2024-05-05"' in date_input_tag(body, "end_date")

    def test_only_start_applied_keeps_start_input_and_leaves_end_empty(self, alice_client):
        _, body = page(alice_client, start_date="2024-05-20")
        assert 'value="2024-05-20"' in date_input_tag(body, "start_date")
        assert not re.search(r'value="\d{4}-', date_input_tag(body, "end_date"))

    def test_clear_link_shown_only_when_filter_applied_and_points_to_profile(self, alice_client):
        _, body = page(alice_client, start_date="2024-05-01")
        match = re.search(r'<a\b[^>]*href="([^"]*)"[^>]*>\s*Clear\s*</a>', body)
        assert match, "Clear link expected while filtered"
        assert urlparse(html_lib.unescape(match.group(1))).path == "/profile"
        assert urlparse(html_lib.unescape(match.group(1))).query == "", (
            "Clear must link to bare /profile"
        )
        cleared, cleared_body = page(alice_client)
        assert cleared.status_code == 200
        assert present(cleared_body, ALL_ALICE) == ALL_ALICE
        assert not re.search(r">\s*Clear\s*<", cleared_body)

    def test_surrounding_whitespace_in_values_is_tolerated(self, alice_client):
        response, body = page(alice_client, start_date=" 2024-05-12 ", end_date="2024-05-12")
        assert response.status_code == 200
        assert "₹30.00" in body


# ---------------------------------------------------------------------- #
# Empty ranges                                                            #
# ---------------------------------------------------------------------- #

class TestEmptyRange:
    def test_range_without_expenses_shows_zero_stats_and_empty_messages(self, alice_client):
        response, body = page(alice_client, start_date="2023-01-01", end_date="2023-01-31")
        assert response.status_code == 200
        assert "₹0.00" in body
        assert stat_shown(body, 0)
        assert "—" in body, "Top category should be an em dash"
        assert "No transactions in this date range." in body
        assert "No spending in this date range." in body
        assert present(body, ALL_ALICE) == set()

    def test_filtered_empty_range_still_shows_clear_link(self, alice_client):
        _, body = page(alice_client, start_date="2023-01-01", end_date="2023-01-31")
        assert re.search(r">\s*Clear\s*<", body)

    def test_user_with_no_expenses_and_no_filter_does_not_show_range_messages(self, client, users):
        login(client, BOB_EMAIL)
        # Bob has one expense only in may_data; this fixture set has none.
        _, body = page(client)
        assert "No transactions in this date range." not in body
        assert "No spending in this date range." not in body


# ---------------------------------------------------------------------- #
# Validation                                                              #
# ---------------------------------------------------------------------- #

class TestValidation:
    @pytest.mark.parametrize(
        "params",
        [
            {"start_date": "not-a-date"},
            {"start_date": "2026-02-30"},
            {"end_date": "2026-02-30"},
            {"end_date": "garbage"},
            {"start_date": "2024-13-01"},
            {"start_date": "05/01/2024"},
            {"start_date": "2024-05-01", "end_date": "nope"},
            {"start_date": "20240501"},
        ],
    )
    def test_invalid_date_returns_200_with_error_and_all_expenses(self, alice_client, params):
        baseline = error_signal(page(alice_client)[1])
        response, body = page(alice_client, **params)
        assert response.status_code == 200, "Invalid filter is feedback, not an HTTP error"
        assert error_signal(body) > baseline, "An error message is expected"
        assert present(body, ALL_ALICE) == ALL_ALICE, "All expenses must be shown"
        assert "₹265.54" in body

    def test_start_after_end_returns_200_with_error_and_all_expenses(self, alice_client):
        baseline = error_signal(page(alice_client)[1])
        response, body = page(alice_client, start_date="2024-05-20", end_date="2024-05-10")
        assert response.status_code == 200
        assert error_signal(body) > baseline, "An error message is expected"
        assert present(body, ALL_ALICE) == ALL_ALICE
        assert "₹265.54" in body

    def test_start_equal_to_end_is_valid(self, alice_client):
        baseline = error_signal(page(alice_client)[1])
        response, body = page(alice_client, start_date="2024-05-12", end_date="2024-05-12")
        assert response.status_code == 200
        assert error_signal(body) == baseline, "Equal bounds are not an error"

    def test_valid_filter_shows_no_error(self, alice_client):
        baseline = error_signal(page(alice_client)[1])
        _, body = page(alice_client, start_date="2024-05-01", end_date="2024-05-05")
        assert error_signal(body) == baseline

    @pytest.mark.parametrize(
        "payload",
        ["' OR 1=1 --", "'; DROP TABLE expenses; --", "2024-05-01' OR '1'='1"],
    )
    def test_sql_injection_attempt_is_treated_as_invalid_date(self, alice_client, payload):
        baseline = error_signal(page(alice_client)[1])
        response, body = page(alice_client, start_date=payload)
        assert response.status_code == 200, "Injection attempt must not cause a server error"
        assert error_signal(body) > baseline
        assert present(body, ALL_ALICE) == ALL_ALICE
        assert "bob-secret-purchase" not in body
        # Table must still exist and be intact.
        conn = sqlite3.connect(db_module.DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        finally:
            conn.close()
        assert count == 9, "No expenses may be lost or altered"

    def test_sql_injection_in_end_date_is_handled(self, alice_client):
        response, body = page(alice_client, end_date="' OR 1=1 --")
        assert response.status_code == 200
        assert "bob-secret-purchase" not in body

    def test_very_long_value_does_not_cause_server_error(self, alice_client):
        response, body = page(alice_client, start_date="9" * 5000)
        assert response.status_code == 200
        assert present(body, ALL_ALICE) == ALL_ALICE


# ---------------------------------------------------------------------- #
# Data isolation and user card                                            #
# ---------------------------------------------------------------------- #

class TestIsolationAndUserCard:
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"start_date": "2024-05-01", "end_date": "2024-05-31"},
            {"start_date": "2024-05-02", "end_date": "2024-05-02"},
            {"end_date": "2024-05-05"},
        ],
    )
    def test_filter_never_shows_other_users_expenses(self, alice_client, params):
        _, body = page(alice_client, **params)
        assert "bob-secret-purchase" not in body
        assert "999.99" not in body

    def test_other_user_sees_only_their_own_data_in_same_range(self, client, may_data):
        login(client, BOB_EMAIL)
        _, body = page(client, start_date="2024-05-01", end_date="2024-05-31")
        assert "bob-secret-purchase" in body
        assert "₹999.99" in body
        assert present(body, ALL_ALICE) == set()

    def test_user_id_in_query_string_is_ignored(self, alice_client, may_data):
        _, body = page(alice_client, user_id=may_data["bob"], start_date="2024-05-01")
        assert "bob-secret-purchase" not in body

    def test_user_info_card_unchanged_when_filtering(self, alice_client):
        conn = sqlite3.connect(db_module.DB_PATH)
        try:
            created = conn.execute(
                "SELECT created_at FROM users WHERE email = ?", (ALICE_EMAIL,)
            ).fetchone()[0]
        finally:
            conn.close()
        member_since = date.fromisoformat(created[:10]).strftime("%B %Y")

        for params in (
            {},
            {"start_date": "2024-05-01", "end_date": "2024-05-05"},
            {"start_date": "2023-01-01", "end_date": "2023-01-02"},
            {"start_date": "bad"},
        ):
            _, body = page(alice_client, **params)
            assert "Alice Smith" in body, f"Name missing for {params}"
            assert ALICE_EMAIL in body, f"Email missing for {params}"
            assert member_since in body, f"Member-since missing for {params}"


# ---------------------------------------------------------------------- #
# Quick-filter buttons using the real current date                        #
# ---------------------------------------------------------------------- #

@pytest.fixture
def relative_data(users, alice_client):
    """Alice's expenses placed relative to today, at month edges."""
    today = date.today()
    this_start = month_start_shift(today, 0)
    this_end = month_end_of(today)
    prev_end = month_end_of(month_start_shift(today, -1))
    two_ago_start = month_start_shift(today, -2)
    three_ago_end = month_end_of(month_start_shift(today, -3))
    next_start = month_start_shift(today, 1)

    uid = users["alice"]
    add_expense(uid, 1.00, "Food", this_start, "rel-this-first")
    add_expense(uid, 2.00, "Food", this_end, "rel-this-last")
    add_expense(uid, 4.00, "Bills", prev_end, "rel-prev-last")
    add_expense(uid, 8.00, "Bills", two_ago_start, "rel-two-ago-first")
    add_expense(uid, 16.00, "Other", three_ago_end, "rel-three-ago-last")
    add_expense(uid, 32.00, "Other", next_start, "rel-next-first")
    add_expense(users["bob"], 64.00, "Other", this_start, "rel-bob-this-month")
    return {
        "this_start": this_start,
        "this_end": this_end,
        "three_start": two_ago_start,
    }


REL_ALL = {
    "rel-this-first", "rel-this-last", "rel-prev-last", "rel-two-ago-first",
    "rel-three-ago-last", "rel-next-first", "rel-bob-this-month",
}


class TestPresetButtonsCurrentDate:
    def test_this_month_link_covers_first_to_last_day_of_current_month(self, alice_client, relative_data):
        _, body = page(alice_client)
        start, end, _ = preset_range(body, "This month")
        assert start == relative_data["this_start"].isoformat()
        assert end == relative_data["this_end"].isoformat()

    def test_last_3_months_link_covers_two_months_ago_through_month_end(self, alice_client, relative_data):
        _, body = page(alice_client)
        start, end, _ = preset_range(body, "Last 3 months")
        assert start == relative_data["three_start"].isoformat()
        assert end == relative_data["this_end"].isoformat()

    def test_this_month_link_shows_only_current_month_expenses(self, alice_client, relative_data):
        _, body = page(alice_client)
        _, _, href = preset_range(body, "This month")
        response = alice_client.get(href)
        assert response.status_code == 200
        result = response.get_data(as_text=True)
        assert present(result, REL_ALL) == {"rel-this-first", "rel-this-last"}
        assert "₹3.00" in result

    def test_last_3_months_link_shows_three_calendar_months(self, alice_client, relative_data):
        _, body = page(alice_client)
        _, _, href = preset_range(body, "Last 3 months")
        response = alice_client.get(href)
        assert response.status_code == 200
        result = response.get_data(as_text=True)
        assert present(result, REL_ALL) == {
            "rel-this-first", "rel-this-last", "rel-prev-last", "rel-two-ago-first",
        }
        assert "₹15.00" in result

    def test_this_month_fills_inputs_and_is_highlighted(self, alice_client, relative_data):
        _, baseline = page(alice_client)
        start, end, href = preset_range(baseline, "This month")
        _, body = page(alice_client, start_date=start, end_date=end)
        assert f'value="{start}"' in date_input_tag(body, "start_date")
        assert f'value="{end}"' in date_input_tag(body, "end_date")
        assert preset_anchor(body, "This month")[0] != preset_anchor(baseline, "This month")[0], (
            "This month must be highlighted when applied"
        )
        assert preset_anchor(body, "Last 3 months")[0] == preset_anchor(baseline, "Last 3 months")[0], (
            "Last 3 months must not be highlighted"
        )

    def test_last_3_months_fills_inputs_and_is_highlighted(self, alice_client, relative_data):
        _, baseline = page(alice_client)
        start, end, _ = preset_range(baseline, "Last 3 months")
        _, body = page(alice_client, start_date=start, end_date=end)
        assert f'value="{start}"' in date_input_tag(body, "start_date")
        assert f'value="{end}"' in date_input_tag(body, "end_date")
        assert preset_anchor(body, "Last 3 months")[0] != preset_anchor(baseline, "Last 3 months")[0]
        assert preset_anchor(body, "This month")[0] == preset_anchor(baseline, "This month")[0]

    def test_no_preset_highlighted_without_filter_or_with_custom_range(self, alice_client, relative_data):
        _, baseline = page(alice_client)
        _, custom = page(alice_client, start_date="2024-05-01", end_date="2024-05-05")
        for label in ("This month", "Last 3 months"):
            assert preset_anchor(custom, label)[0] == preset_anchor(baseline, label)[0], (
                f"{label} must not be highlighted for a custom range"
            )

    def test_preset_results_exclude_other_users(self, alice_client, relative_data):
        _, body = page(alice_client)
        _, _, href = preset_range(body, "This month")
        result = alice_client.get(href).get_data(as_text=True)
        assert "rel-bob-this-month" not in result


# ---------------------------------------------------------------------- #
# Quick-filter buttons with a frozen "today" (year boundaries)            #
# ---------------------------------------------------------------------- #

def freeze_today(monkeypatch, frozen):
    class FrozenDate(date):
        @classmethod
        def today(cls):
            return cls(frozen.year, frozen.month, frozen.day)

    monkeypatch.setattr(app_module, "date", FrozenDate)


class TestPresetButtonsYearBoundary:
    @pytest.mark.parametrize(
        "today, this_start, three_start, month_end",
        [
            (date(2026, 1, 15), "2026-01-01", "2025-11-01", "2026-01-31"),
            (date(2026, 2, 10), "2026-02-01", "2025-12-01", "2026-02-28"),
            (date(2026, 3, 31), "2026-03-01", "2026-01-01", "2026-03-31"),
            (date(2026, 10, 31), "2026-10-01", "2026-08-01", "2026-10-31"),
            (date(2026, 12, 1), "2026-12-01", "2026-10-01", "2026-12-31"),
            (date(2024, 2, 29), "2024-02-01", "2023-12-01", "2024-02-29"),
        ],
    )
    def test_preset_links_for_frozen_dates(
        self, alice_client, monkeypatch, today, this_start, three_start, month_end
    ):
        freeze_today(monkeypatch, today)
        _, body = page(alice_client)
        assert preset_range(body, "This month")[:2] == (this_start, month_end)
        assert preset_range(body, "Last 3 months")[:2] == (three_start, month_end)

    def test_last_3_months_across_year_boundary_filters_correctly(
        self, alice_client, users, monkeypatch
    ):
        freeze_today(monkeypatch, date(2026, 1, 15))
        uid = users["alice"]
        data = [
            (date(2025, 10, 31), "yb-oct31-out"),
            (date(2025, 11, 1), "yb-nov01-in"),
            (date(2025, 12, 31), "yb-dec31-in"),
            (date(2026, 1, 1), "yb-jan01-in"),
            (date(2026, 1, 31), "yb-jan31-in"),
            (date(2026, 2, 1), "yb-feb01-out"),
        ]
        for on_date, description in data:
            add_expense(uid, 5.00, "Food", on_date, description)
        names = {d for _, d in data}

        _, body = page(alice_client)
        _, _, href = preset_range(body, "Last 3 months")
        result = alice_client.get(href).get_data(as_text=True)
        assert present(result, names) == {
            "yb-nov01-in", "yb-dec31-in", "yb-jan01-in", "yb-jan31-in",
        }
        assert "₹20.00" in result

    def test_this_month_in_january_excludes_december(self, alice_client, users, monkeypatch):
        freeze_today(monkeypatch, date(2026, 1, 15))
        uid = users["alice"]
        add_expense(uid, 3.00, "Food", date(2025, 12, 31), "yb-dec31")
        add_expense(uid, 7.00, "Food", date(2026, 1, 1), "yb-jan01")
        add_expense(uid, 9.00, "Food", date(2026, 1, 31), "yb-jan31")
        add_expense(uid, 11.00, "Food", date(2026, 2, 1), "yb-feb01")

        _, body = page(alice_client)
        _, _, href = preset_range(body, "This month")
        result = alice_client.get(href).get_data(as_text=True)
        assert present(result, {"yb-dec31", "yb-jan01", "yb-jan31", "yb-feb01"}) == {
            "yb-jan01", "yb-jan31",
        }
        assert "₹16.00" in result

    def test_last_3_months_highlighted_across_year_boundary(self, alice_client, monkeypatch):
        freeze_today(monkeypatch, date(2026, 1, 15))
        _, baseline = page(alice_client)
        start, end, _ = preset_range(baseline, "Last 3 months")
        assert (start, end) == ("2025-11-01", "2026-01-31")
        _, body = page(alice_client, start_date=start, end_date=end)
        assert preset_anchor(body, "Last 3 months")[0] != preset_anchor(baseline, "Last 3 months")[0]
        assert preset_anchor(body, "This month")[0] == preset_anchor(baseline, "This month")[0]
