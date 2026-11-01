---
name: expensify-ui
description: Design and build UI for Expensify, the Flask + Jinja + vanilla CSS personal expense tracker (github.com/techy21/Expense-Tracker-Expensify). Use whenever the user asks to design, create, build, redesign, or improve any Expensify page, screen, component, form, card, list, dashboard, profile, or expense view, including requests like "design the add expense page", "create UI for the dashboard", "build a component for categories", or "make the profile page look better", even if they don't say "Expensify" but are clearly working in that repo. Do not use for UI in other projects.
---

# Expensify UI

Expensify is a small Flask app. Templates are Jinja2, styles are plain CSS, JS is vanilla. The visual language is warm and editorial: off-white paper background, DM Serif Display headings, forest green accent. Your job is to add pages and components that look like they were always part of it.

The single most common failure is producing a generic "modern SaaS" screen (cool grays, blue buttons, heavy shadows, React code) that clashes with the existing pages. Consistency beats novelty here. Clean, modern, and usable means good hierarchy and spacing inside the existing look, not a new look.

## Before you design anything

1. **Read the real design.** Open `static/css/style.css` and `templates/base.html` in the repo. Then read `references/design-system.md` in this skill, which documents the tokens, components, and patterns for screens that don't exist yet. If the repo's CSS has changed since that reference was written, the repo wins.
2. **Read `CLAUDE.md` in the repo.** It sets hard constraints (below). Also check which routes are stubs. Don't implement backend logic for a stub route unless the user asked for that step. A UI request means templates and CSS, with the route only rendering the template.
3. **Look at the closest existing template** (login.html for forms, profile.html for signed-in pages) and reuse its classes.
4. **Ask for screenshots only if needed.** If the user wants to match something that isn't in the code (a mockup, a Figma frame, a site they like), ask for an image. Otherwise the CSS is the source of truth and you shouldn't make them do extra work.

## Hard constraints (from the project's CLAUDE.md)

- Jinja2 templates that `{% extends "base.html" %}`. One template per page.
- Every internal link uses `url_for()`. Never hardcode a URL.
- Page-specific CSS goes in a new file under `static/css/` (e.g. `expenses.css`), linked through `{% block head %}`. No inline `<style>` tags. Inline `style="width: 72%"` is acceptable only for data-driven values like bar widths.
- Vanilla JS only, and only when the page truly needs behavior. No React, no jQuery, no npm, no CDN JS libraries.
- No new pip packages.
- Name the product "Expensify" in all user-facing text.

"Components" in this project means Jinja macros or `{% include %}` partials, not JS components. If a piece of UI repeats (an expense row, a stat card), make it a macro in `templates/_components.html` or a partial like `templates/partials/_expense_row.html`.

## Icons

Use the bundled `assets/_icons.html`. It's a Jinja macro with 30 Lucide icons as inline SVG, so there's no dependency. Copy it to `templates/_icons.html` if the repo doesn't have it yet, then:

```jinja
{% from "_icons.html" import icon %}
<a href="{{ url_for('add_expense') }}" class="btn-primary">{{ icon("plus", 16) }} Add expense</a>
```

Available: wallet, plus, pencil, trash-2, receipt, calendar, tag, trending-up, trending-down, utensils, car, shopping-bag, house, zap, heart-pulse, film, search, funnel, x, check, circle-alert, log-out, user, arrow-left, chevron-down, piggy-bank, chart-pie, chart-column, inbox, ellipsis. If you need another, add a branch to the macro with the paths from lucide.dev and say so.

Icons should carry meaning: a category, an action, a status. Don't decorate headings with icons just to fill space. An icon-only button needs an `aria-label`. Give `.icon` `vertical-align: middle` (or use flex with a gap) so it lines up with text.

## Design rules

- **Use the tokens.** Every color, radius, and font comes from a `var(--...)` in style.css. Raw hex values only for new tokens you define at the top of your page CSS, with a name.
- **Cards are flat.** White surface, 1px `--border`, `--radius-md`. The one soft shadow (`0 8px 40px rgba(0,0,0,0.06)`) is for things that float: modals, dropdowns. Not for every card.
- **Spacing on an 8px rhythm** for new CSS: 0.5rem steps. Leave existing spacing alone unless asked.
- **Hierarchy through type, not color.** Display font for titles and big money figures, muted ink for supporting text. Green, amber, and danger carry meaning (under budget, nearing, over), so don't use them decoratively.
- **Money is rupees** (`₹`), formatted with thousands separators, and set in `tabular-nums` so columns align.
- **Responsive by default.** Works at 375px wide. Use the existing 900px and 600px breakpoints.
- **Every list has an empty state**, every form has visible errors (reuse `.auth-error`), every destructive action has a confirmation step.
- **Accessible basics:** real `<label for>` on inputs, buttons are `<button>`, links are `<a>`, visible focus (the accent border), sufficient contrast. Don't put light text on `--paper-warm`.

## What to deliver

Structure the response in this order. Keep the prose short. The user wants to see decisions and code, not an essay.

**1. Structure (a few lines).** The layout from top to bottom, and the two or three UX decisions that matter, each with its reason. Example: "Amount field comes first because that's what people know before anything else."

**2. Files.** One fenced block per file, each headed with its repo path:

- `templates/<page>.html`
- `static/css/<page>.css` (only new rules; reuse existing classes where they fit)
- `templates/_components.html` or partials, if you made macros
- `templates/_icons.html`, only if it's being added for the first time
- The `app.py` route change, only if the template needs a route to render it, kept to "render the template". Use sample data passed from the route or clearly marked placeholder data in the template if the DB step isn't built yet, and say which.

**3. Notes (only if there's something to say).** Anything the user has to do by hand, any new token you introduced, and any inconsistency you noticed in the existing code.

Don't dump code without the structure section, and don't explain every CSS property. If a design choice could reasonably go two ways and it matters, pick one, say why in one line, and mention the alternative.

## Redesigns

When the user asks to "improve" or "redesign" an existing page, read its current template and CSS first. Say in two or three lines what's weak about it now (hierarchy, spacing, missing states, mobile layout), then change only what fixes those problems. Keep class names the same where other pages use them, so you don't break anything elsewhere.
