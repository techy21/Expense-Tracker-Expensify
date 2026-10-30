# Spec: Backend Routes for Profile Page

## Overview

This feature replaces the hardcoded sample data in the `/profile` route with real data from SQLite, so each logged-in user sees their own account details, spending stats, transaction history, and category breakdown. Step 4 established the page design with static data; this step connects that design to the backend using the existing `users` and `expenses` tables, and gives the later add, edit, and delete expense steps a page that reflects their changes.

## Depends on

- Step 1: Database setup (`users` and `expenses` tables, `get_db()`, seed data)
- Step 2: Registration (user accounts can be created)
- Step 3: Login + Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (`templates/profile.html` and its context variables)

## Routes

No new routes. The existing route changes as follows:

- `GET /profile` — render the profile page from database data instead of hardcoded values — logged-in

## Database changes

No database changes. The existing `users` and `expenses` tables are sufficient.

New query helpers in `database/db.py`:

- `get_user_profile(user_id)` — returns a dict with `name`, `email`, `initials`, and `member_since`, or `None` if the user does not exist
  - `initials`: first letter of up to the first two words of the name, uppercased (`Demo User` → `DU`, `Cher` → `C`)
  - `member_since`: `created_at` formatted as `October 2026`
- `get_user_transactions(user_id)` — returns a list of dicts with `date`, `description`, `category`, and `amount`, ordered by `date DESC, id DESC`
  - `date`: formatted as `25 Oct 2026`
  - `description`: empty string when the stored value is `NULL`
- `get_user_categories(user_id)` — returns a list of dicts with `name`, `total`, and `percent`, ordered by `total DESC, category ASC`
  - `percent`: the category's share of the user's total spending, rounded to a whole number; `0` when the total is `0`
- `get_user_stats(user_id)` — returns a dict with `total_spent`, `transaction_count`, and `top_category`
  - `total_spent`: `0` when the user has no expenses
  - `top_category`: the highest-spending category, using the same ordering as `get_user_categories`; `"—"` when the user has no expenses

## Templates

- **Create:** None
- **Modify:** None. `templates/profile.html` already renders the required context variables and has empty states for transactions and categories.

## Files to change

- `app.py` — remove the hardcoded data from `profile()` and call the new helpers
- `database/db.py` — add the four query helpers

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All SQL lives in `database/db.py`; `profile()` only checks the session, fetches data, and renders the template
- Every expense query filters by `user_id` from the session, never from request input
- Keep the context variable names the template already uses: `user`, `stats`, `transactions`, `categories`
- Unauthenticated requests still redirect to `/login`
- If `session["user_id"]` refers to a user that no longer exists, clear the session and redirect to `/login`
- Do not implement the add, edit, or delete expense stub routes

## Definition of done

- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@expensify.com` / `demo123` shows `Demo User`, `demo@expensify.com`, initials `DU`, and the month and year the account was created
- [ ] The demo user's stats show total spent `₹265.54`, `8` transactions, and top category `Bills`
- [ ] The demo user's transaction table shows 8 rows, newest first, with dates formatted like `25 Oct 2026`
- [ ] The demo user's category breakdown lists 7 categories from highest to lowest total, starting with Bills at `₹80.00`
- [ ] A newly registered user with no expenses sees their own name and email, `₹0.00` total, `0` transactions, top category `—`, and both empty-state messages
- [ ] Adding a row to `expenses` for a user changes that user's profile page after refresh and does not change any other user's page
- [ ] Logging in, deleting that user's row from `users`, and refreshing `/profile` redirects to `/login` without an error
- [ ] `app.py` contains no hardcoded sample profile data and no SQL
