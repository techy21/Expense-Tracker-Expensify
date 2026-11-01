# Spec: Add Expense

## Overview

This feature replaces the `/expenses/add` stub with a working form that lets a logged-in user record a new expense. The user enters an amount, category, date, and optional description; the app validates the input on the server, saves the expense against the user in the session, and returns to the profile page with a success message. Until now, expenses could only come from seed data or direct database changes, so this is the first step where users create their own data. It also gives Step 8 (Edit Expense) and Step 9 (Delete Expense) real user-created rows to work with.

## Depends on

- Step 1: Database setup (`expenses` table, `get_db()`, `CATEGORIES`)
- Step 3: Login + Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`)
- Step 5: Backend routes for profile page (stats, transactions, and categories read from the database)
- Step 6: Date filter for profile page (`normalise_date()` in `app.py`)

## Routes

No new URLs. The existing `add_expense()` stub in `app.py` is replaced and updated to accept `methods=["GET", "POST"]`:

- `GET /expenses/add` — render the add expense form, with the date defaulting to today — logged-in
- `POST /expenses/add` — validate the form and save the expense; on success, flash a message and redirect to `/profile`; on failure, re-render the form with an error and the submitted values — logged-in

Access behaviour for both methods:

- Logged-out requests redirect to `/login`, and nothing is saved
- If `session["user_id"]` refers to a user that no longer exists, clear the session and redirect to `/login`, matching `profile()`

The `/expenses/<id>/edit` and `/expenses/<id>/delete` stubs stay unchanged.

## Database changes

No database changes. The existing `expenses` table already has every column this feature needs (`user_id`, `amount`, `category`, `date`, `description`, `created_at`).

New helper in `database/db.py` (code only, no schema change):

- `create_expense(user_id, amount, category, expense_date, description)` — inserts one row with a parameterised query, commits, closes the connection, and returns the new expense id

The existing `CATEGORIES` list in `database/db.py` is the only source of valid categories.

## Templates

- **Create:** `templates/add_expense.html` — extends `base.html`, loads `static/css/add_expense.css` through the `head` block, and contains:
  - A `method="POST"` form with `action="{{ url_for('add_expense') }}"`
  - A labelled `amount` input: `type="number"`, `step="0.01"`, `min="0.01"`, `required`
  - A labelled `category` `<select>`, with a blank "Select a category" option followed by the values of `CATEGORIES`, `required`
  - A labelled `date` input: `type="date"`, `required`
  - A labelled optional `description` input: `type="text"`, `maxlength="200"`
  - A submit button and a "Cancel" link to `url_for('profile')`
  - The validation error above the form when there is one, with `role="alert"`
  - Submitted values kept in all four fields after an error
- **Modify:** `templates/profile.html`
  - Add an "Add expense" link to `url_for('add_expense')` in the transaction history panel header, so it shows in both the empty and populated states
  - Render flashed messages above the user info card using `get_flashed_messages(with_categories=true)` and the existing `.auth-success` / `.auth-error` classes, because the profile page does not display flashes yet

## Files to change

- `app.py` — import `math` and `create_expense` / `CATEGORIES`; add a small `parse_expense_form()` helper; replace the `add_expense()` stub
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — add the "Add expense" link and flashed messages
- `static/css/profile.css` — style the transaction history panel header that holds the link, including at the existing responsive breakpoints
- `CLAUDE.md` — change `/expenses/add` in the route table to implemented and list `GET` and `POST`

## Files to create

- `templates/add_expense.html`
- `static/css/add_expense.css`

## New dependencies

No new dependencies. Validation uses Python's standard `math` and `datetime` modules.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — never build SQL with f-strings or by inserting request values
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags
- No JavaScript is needed; the form works with a normal POST submit
- All SQL lives in `database/db.py`; `add_expense()` only checks the session, gets validated values, saves them, and responds
- `user_id` comes only from the session, never from request input
- Use `url_for()` for every internal link and form action
- Routes stay in `app.py`; no blueprints
- Validate on the server even though the form has HTML validation attributes, and report one clear message at a time:
  - **Amount:** required and numeric. Reject `nan` and `inf` using `math.isfinite()`. Round to 2 decimal places, then require a value from `0.01` to `9999999.99`
  - **Category:** must exactly match a value in `CATEGORIES`
  - **Date:** required and a real date. Parse it with the existing `normalise_date()` so it is stored as `YYYY-MM-DD`. Future dates are allowed
  - **Description:** optional. Strip whitespace, allow at most 200 characters, and store blank values as `NULL`
- A validation failure is user feedback, not an HTTP error, so re-render the form with HTTP 200 and do not use `abort()`
- On success, call `flash("Expense added.", "success")` and `redirect(url_for("profile"))` (Post/Redirect/Get)
- Redirect to the unfiltered profile page so the new expense is always visible
- Added after code review: every POST form includes a session CSRF token, and a missing or wrong token returns HTTP 400 through `abort(400)`
- Do not implement the edit or delete expense stub routes
- Keep the dev server on port 5001

## Definition of done

- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Sending `POST /expenses/add` while logged out redirects to `/login` and creates no row
- [ ] Visiting `/expenses/add` while logged in shows the form, with today's date filled in and all 7 categories available
- [ ] The profile page has an "Add expense" link that opens the form, both with and without existing expenses
- [ ] Submitting `100.50`, `Food`, today's date, and `Team lunch` redirects to `/profile` and shows "Expense added."
- [ ] The new expense appears at or near the top of the transaction table with the correct date, description, category, and `₹100.50`
- [ ] Total spent rises by `₹100.50`, the transaction count rises by 1, and the Food category total rises by `₹100.50`
- [ ] The new row in `expenses` has the logged-in user's `user_id`, `amount` `100.5`, and its date in `YYYY-MM-DD` format
- [ ] Refreshing `/profile` after adding an expense does not create a second row or show the message again
- [ ] An expense with a blank or whitespace-only description saves successfully with `NULL` in the `description` column
- [ ] Amounts of `0`, `-5`, `0.001`, `abc`, `nan`, `inf`, `10000000`, and blank each show an error and create no row
- [ ] A category outside the list, such as `Crypto` sent by a modified request, shows an error and creates no row
- [ ] Dates of `2026-02-30`, `not-a-date`, and blank each show an error and create no row
- [ ] A description longer than 200 characters sent by a modified request shows an error and creates no row
- [ ] After a validation error, all four fields keep their submitted values
- [ ] A `user_id` field added to the form by a modified request is ignored, and the expense belongs to the logged-in user
- [ ] An expense added by one user does not appear on another user's profile page
- [ ] A description containing `<script>alert(1)</script>` displays as plain text on the profile page
- [ ] A description containing `'); DROP TABLE expenses; --` is stored as plain text, and the `expenses` table still exists
- [ ] Logging in, deleting that user's row from `users`, and opening or submitting the form redirects to `/login` without a server error
- [ ] "Cancel" returns to `/profile` without creating a row
- [ ] The form is usable at phone width without horizontal page scrolling
- [ ] `app.py` contains no SQL, and `python app.py` starts on port 5001 without errors
- [ ] `/expenses/<id>/edit` and `/expenses/<id>/delete` still return their stub text
