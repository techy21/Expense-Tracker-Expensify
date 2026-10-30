# Spec: Login and Logout

## Overview

Turn the static `/login` page into a working sign-in flow and replace the
`/logout` stub with a real sign-out. A registered user submits their email and
password; the app looks up the user, checks the password against the stored
werkzeug hash and, on success, stores the user's id and name in Flask's signed
session cookie. Logging out clears that session. This is Step 3 of the
Expensify roadmap: it authenticates the accounts created in Step 2 and gives
Step 4 (Profile) and the expense steps a logged-in user to work with. The
navbar also changes based on whether someone is signed in.

## Depends on

- Step 1: Database Setup (`users` table, `get_db()`, seeded demo user
  `demo@expensify.com` / `demo123`)
- Step 2: Registration (`get_user_by_email()`, `app.secret_key`, flashed
  messages rendered on `login.html`, `.auth-success` / `.auth-error` styles)

## Routes

- `GET /login`: render the sign-in form. If already signed in, redirect to
  `/profile`. Public.
- `POST /login`: validate credentials. On success, set the session and redirect
  to `/profile`. On failure, re-render the form with an error. Public.
- `GET /logout`: clear the session, flash "You have been signed out." and
  redirect to `/login`. Public (safe to hit when not signed in).

`login()` in `app.py` is updated to accept `methods=["GET", "POST"]`, and the
existing `logout()` stub is replaced. No other new routes. The `/profile` stub
stays as it is; Step 4 implements it.

## Database changes

No database changes. The `users` table already stores `email` (UNIQUE,
lowercased by registration) and `password_hash`, and `get_user_by_email()` in
`database/db.py` already returns both.

No new DB helpers are required. Password checking uses werkzeug's
`check_password_hash` and runs in the route after `get_user_by_email()`
returns the row. It is not a DB query.

## Templates

- **Create:** none
- **Modify:**
  - `templates/login.html`
    - repopulate the `email` input with the submitted value
      (`value="{{ email or '' }}"`) after a failed attempt; never repopulate
      the password
  - `templates/base.html`
    - when `session.user_id` is set, the navbar shows the user's name (from
      `session.user_name`) and a "Sign out" link to `url_for('logout')`
      instead of the "Sign in" / "Get started" links
    - when not signed in, the navbar is unchanged

## Files to change

- `app.py`: import `session` from flask and `check_password_hash` from
  `werkzeug.security`; make `login()` handle GET and POST; replace the
  `logout()` stub
- `templates/login.html`: keep the submitted email after an error
- `templates/base.html`: navbar changes depending on session state
- `static/css/style.css`: only if needed, a small style for the signed-in
  user's name in the navbar (e.g. `.nav-user`) using existing CSS variables

## Files to create

- None

## New dependencies

No new dependencies. Uses `flask` (sessions) and `werkzeug.security`
(`check_password_hash`), both already in `requirements.txt`.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders). Never use f-strings or `%`
  in SQL.
- Passwords hashed with werkzeug: verify with `check_password_hash`. Never
  compare plain text, and never log or store the submitted password.
- Use CSS variables. Never hardcode hex values in new CSS.
- All templates extend `base.html`
- All database access goes through `database/db.py`. Routes never run SQL
  directly.
- Every internal link and form action uses `url_for()`
- Routes stay in `app.py`. No blueprints.
- Strip whitespace from `email` and lowercase it before the lookup, to match
  how Step 2 stores it
- Server-side validation: both fields are required. Do not enforce the
  8-character minimum on login, because the seeded demo password `demo123` is
  7 characters.
- Use one generic message for an unknown email and a wrong password alike:
  "Invalid email or password." Never reveal which part was wrong.
- On failure, re-render `login.html` with `error` and `email`. This is user
  feedback, not an HTTP error, so don't use `abort()`.
- On success:
  - call `session.clear()` first, then set `session["user_id"]` and
    `session["user_name"]`
  - `redirect(url_for("profile"))` (Post/Redirect/Get)
- Logout calls `session.clear()`, flashes
  `("You have been signed out.", "success")` and redirects to
  `url_for("login")`
- Do not implement `/profile` or add a `login_required` decorator to the stub
  routes. Those belong to later steps.
- Keep the dev server on port 5001

## Definition of done

- [ ] `GET /login` shows the sign-in form as before
- [ ] Signing in with `demo@expensify.com` / `demo123` redirects to `/profile`
- [ ] Signing in with `DEMO@Expensify.com ` (mixed case, trailing space) also
      works
- [ ] A user freshly created via `/register` can sign in with their password
- [ ] A wrong password shows "Invalid email or password." and keeps the email
      in the field with the password field empty
- [ ] An unknown email shows the same "Invalid email or password." message
- [ ] Submitting blank fields (bypassing HTML `required`) shows an error and
      does not sign in
- [ ] After signing in, the navbar shows the user's name and a "Sign out" link,
      with no "Sign in" or "Get started" links
- [ ] Visiting `/login` while signed in redirects to `/profile`
- [ ] Clicking "Sign out" redirects to `/login`, shows "You have been signed
      out." and the navbar shows "Sign in" / "Get started" again
- [ ] Visiting `/logout` while not signed in does not error
- [ ] Refreshing `/profile` after login does not resubmit the login form
- [ ] View source shows the navbar's sign-out link and form actions generated
      by `url_for` (no hardcoded paths)
- [ ] `python app.py` starts on port 5001 without errors and all other existing
      pages still load
