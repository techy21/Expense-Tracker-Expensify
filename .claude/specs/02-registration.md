# Spec: Registration

## Overview

Turn the static `/register` page into a working sign-up flow. A visitor submits
their name, email and password; the app validates the input, hashes the
password with werkzeug, inserts a new row into the existing `users` table and
redirects to the sign-in page with a success message. This is Step 2 of the
Spendlify roadmap: it builds directly on the data layer from Step 1 and creates
the accounts that Step 3 (Login and Logout) will authenticate. Registration
does not log the user in or create a session; that belongs to Step 3.

## Depends on

- Step 1 — Database Setup (`users` table, `get_db()`, `init_db()`, werkzeug
  hashing already in place)

## Routes

- GET /register — render the registration form — public
- POST /register — validate input, create the user, redirect to `/login` with a
  success flash on success, or re-render the form with an error — public

Both are served by the existing `register()` view in `app.py`, updated to
accept `methods=["GET", "POST"]`. No other routes are added, and the stub
routes for Steps 3–9 stay untouched.

## Database changes

No database changes. The `users` table in `database/db.py` already has every
column this feature needs (`name`, `email UNIQUE NOT NULL`, `password_hash`,
`created_at`).

New helper functions in `database/db.py` (code only, no schema change):

- `get_user_by_email(email)` — returns the matching `users` row or `None`
- `create_user(name, email, password)` — hashes the password with
  `generate_password_hash`, inserts the row with a parameterised query and
  returns the new user id

## Templates

- Create: none
- Modify:
  - `templates/register.html`
    - change `action="/register"` to `action="{{ url_for('register') }}"`
    - repopulate the `name` and `email` inputs with the submitted values
      (`value="{{ name or '' }}"`, same for `email`) when the form is
      re-rendered after an error; never repopulate the password
    - add `minlength="8"` to the password input
  - `templates/login.html`
    - change `action="/login"` to `action="{{ url_for('login') }}"`
    - render flashed messages above the form using
      `get_flashed_messages(with_categories=true)`, so the "Account created"
      message shows after the redirect

## Files to change

- `app.py` — import `request`, `redirect`, `url_for` and `flash`; set
  `app.secret_key` (read from the `SECRET_KEY` environment variable with a dev
  fallback); make `register()` handle GET and POST
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — `url_for` action, keep submitted values,
  `minlength`
- `templates/login.html` — `url_for` action, show flashed messages
- `static/css/style.css` — add an `.auth-success` class next to the existing
  `.auth-error`, styled with `var(--accent)` and `var(--accent-light)`

## Files to create

- None

## New dependencies

No new dependencies. Uses `flask` and `werkzeug`, which are already in
`requirements.txt`.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders); never f-strings or `%` in SQL
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log
  the plain-text password
- Use CSS variables; never hardcode hex values in new CSS
- All templates extend `base.html`
- All database access goes through functions in `database/db.py`; the
  `register()` route never runs SQL directly
- Every internal link and form action uses `url_for()`
- Routes stay in `app.py`; no blueprints
- Strip whitespace from `name` and `email`, and lowercase `email` before
  checking and storing it
- Validate on the server even though the form has HTML `required` attributes:
  - all three fields are required
  - the email must contain `@`
  - the password must be at least 8 characters
- Check for an existing email with `get_user_by_email()` before inserting, and
  also catch `sqlite3.IntegrityError` in `create_user()` (or its caller) as a
  fallback for the UNIQUE constraint
- On a validation failure, re-render `register.html` with `error` set to one
  clear message. This is user feedback, not an HTTP error, so don't use
  `abort()` here
- On success, `flash("Account created. Please sign in.", "success")` and
  `redirect(url_for("login"))` (Post/Redirect/Get)
- Do not create a session or log the user in; that is Step 3
- Keep the dev server on port 5001

## Definition of done

- [ ] `GET /register` shows the form exactly as before
- [ ] Submitting a valid name, new email and an 8+ character password redirects
      to `/login` and shows "Account created. Please sign in."
- [ ] The new user appears in the `users` table with a werkzeug hash (starting
      with `scrypt:` or `pbkdf2:`) in `password_hash`, not the plain password
- [ ] The stored email is lowercase with no surrounding whitespace
- [ ] Registering with `demo@spendlify.com` (or `DEMO@Spendlify.com`) shows
      an "email already registered" error and creates no new row
- [ ] Submitting a password shorter than 8 characters shows an error and
      creates no row
- [ ] Submitting a blank or whitespace-only name shows an error
- [ ] After an error, the name and email fields keep their submitted values and
      the password field is empty
- [ ] Refreshing `/login` after a successful registration does not resubmit the
      form or show the flash message again
- [ ] The success message uses the `.auth-success` style and matches the
      existing auth card design
- [ ] View source on `/register` and `/login` shows form actions generated by
      `url_for` (no hardcoded paths in the templates)
- [ ] `python app.py` starts on port 5001 without errors and all other existing
      pages still load
