# Spec: Date Filter for Profile Page

## Overview

This feature lets a logged-in user narrow their profile page to a chosen date range. A small form above the summary stats submits an optional start date and end date, and the stats, transaction history, and category breakdown all update to cover only that range. Step 5 connected the profile page to real data but always shows all of a user's expenses; this step makes that data easier to explore before the add, edit, and delete expense steps increase how much of it there is. The filter lives in the URL's query string, so a filtered view survives a refresh and can be bookmarked.

## Depends on

- Step 1: Database setup (`expenses.date` stored as `YYYY-MM-DD`)
- Step 3: Login + Logout (`session["user_id"]` is set on login)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`)
- Step 5: Backend routes for profile page (`get_user_transactions`, `get_user_categories`, `get_user_stats`)

## Routes

No new routes. The existing route changes as follows:

- `GET /profile` — accepts optional `start_date` and `end_date` query parameters (`YYYY-MM-DD`) and renders the page for that range — logged-in

Filter behaviour:

- Both bounds are inclusive
- Either bound can be used alone: start only means "from this date onward", end only means "up to this date"
- With no parameters, or with both left blank, the page shows all expenses as it does today
- If a value is not a valid `YYYY-MM-DD` date, or `start_date` is later than `end_date`, the page returns HTTP 200 with a clear error message and all expenses unfiltered
- "This month" links to the first through last day of the current calendar month
- "Last 3 months" links to the first day of the month two months ago through the last day of the current month, so on 31 Oct 2026 it covers 1 Aug to 31 Oct 2026

## Database changes

No database changes. The existing `expenses.date` column stores `YYYY-MM-DD` text, which compares correctly in date order.

Changes to query helpers in `database/db.py`:

- `get_user_transactions(user_id, start_date=None, end_date=None)`
- `get_user_categories(user_id, start_date=None, end_date=None)`
- `get_user_stats(user_id, start_date=None, end_date=None)` — also passes the range to its `get_user_categories` call

All three add the same parameterised condition to their `WHERE` clause, and `None` means that bound is not applied:

```sql
AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)
```

`get_user_profile` does not change. Category `percent` values are calculated against the total for the selected range.

## Templates

- **Create:** None
- **Modify:** `templates/profile.html`
  - Add a filter form between the user info card and the stats grid, using `method="get"`, `action="{{ url_for('profile') }}"`, two labelled `<input type="date">` fields named `start_date` and `end_date`, and an "Apply" button
  - Add "This month" and "Last 3 months" buttons, as links built with `url_for('profile', ...)`, highlighting the one that matches the applied range
  - Keep the applied dates in the inputs after submitting
  - Show a "Clear" link to `url_for('profile')` only while a filter is applied
  - Show the validation error near the form when there is one
  - When a filter is applied and matches nothing, show "No transactions in this date range." and "No spending in this date range." in place of the current empty-state messages

## Files to change

- `app.py` — add a small helper that reads and validates the two query parameters, then pass the range to the three query helpers and the filter state to the template
- `database/db.py` — add the optional date range to the three query helpers
- `templates/profile.html` — add the filter form, error message, and filtered empty states
- `static/css/profile.css` — add styles for the filter form and error message, including the existing responsive breakpoints

## Files to create

None.

## New dependencies

No new dependencies. Date validation uses Python's standard `datetime` module.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — never build SQL with f-strings or by inserting request values
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles and no inline `<style>` tags
- No JavaScript is needed; the form works with a normal GET submit
- All SQL lives in `database/db.py`; `profile()` only checks the session, gets the filter values, fetches data, and renders the template
- Every expense query filters by `user_id` from the session, never from request input
- Parse dates with `datetime.strptime(value, "%Y-%m-%d")` and pass the normalised `date.isoformat()` value to the query helpers
- An invalid filter is user feedback, not an HTTP error, so do not use `abort()` for it
- Keep the existing context variable names (`user`, `stats`, `transactions`, `categories`)
- Use `url_for()` for every internal link and form action
- Unauthenticated requests still redirect to `/login`, including requests with filter parameters
- Do not implement the add, edit, or delete expense stub routes
- Keep the dev server on port 5001

## Definition of done

The demo-user checks below use dates from the month the database was seeded, because the seed data is created in that month.

- [ ] Visiting `/profile?start_date=2026-01-01` while logged out redirects to `/login`
- [ ] Visiting `/profile` with no parameters shows all demo-user data: `₹265.54`, `8` transactions, top category `Bills`
- [ ] Filtering the demo user from day 1 to day 5 of the seed month shows `₹117.50`, `3` transactions, top category `Bills`, 3 table rows, and 3 categories
- [ ] For that same range, the category bars reflect the range: Bills `68%`, Transport `21%`, Food `11%`
- [ ] Setting start and end to day 12 of the seed month includes that day's expense: `₹30.00`, `1` transaction, top category `Entertainment`
- [ ] Setting only a start date of day 20 of the seed month shows 2 transactions totalling `₹52.30`
- [ ] Setting only an end date of day 3 of the seed month shows 2 transactions totalling `₹37.50`
- [ ] Refreshing a filtered page keeps the same results, and the date inputs still show the applied dates
- [ ] "This month" shows only the current calendar month's expenses, fills in the date inputs, and is highlighted
- [ ] "Last 3 months" shows the current and two previous calendar months, including across a year boundary, and is highlighted
- [ ] Clicking "Clear" returns to `/profile` with all data, and the "Clear" link is not shown there
- [ ] A range with no expenses shows `₹0.00`, `0` transactions, top category `—`, and both date-range empty-state messages
- [ ] `/profile?start_date=not-a-date` and `/profile?start_date=2026-02-30` return HTTP 200 with an error message and all expenses
- [ ] A start date later than the end date shows an error message and all expenses
- [ ] `/profile?start_date=' OR 1=1 --` shows the invalid-date error and does not cause a server error
- [ ] Filtering never shows another user's expenses
- [ ] The member-since date and the rest of the user info card do not change when filtering
- [ ] The filter form is usable at phone width without horizontal page scrolling
- [ ] `app.py` contains no SQL, and `python app.py` starts on port 5001 without errors
