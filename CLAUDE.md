# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (Windows)
source .venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
# Starts on http://localhost:5000 with debug=True
```

No test or lint infrastructure is configured.

## Architecture

Flask app with blueprint-based routing, SQLAlchemy ORM over SQLite, bcrypt auth, and Jinja2 server-side templates. No JavaScript framework — minimal inline JS only.

**Entry point:** `app.py` — initializes Flask, registers the four blueprints, and calls `db.create_all()` on startup.

**Blueprints (`routes/`):**
- `auth_bp` — register, login, logout, profile, my_bets, directory, delete_account
- `betting_bp` — dashboard (event list + bet placement), leaderboard, nominate
- `admin_bp` — create/resolve events, manage groups, reveal MLT nominees, delete users
- `groups_bp` — create groups, invite, accept, leave, remove members, transfer ownership

**Auth pattern:** Session-based (`session['user_id']`), no Flask-Login. Every protected route manually checks `session.get('user_id')` and redirects to `auth.login` if missing. Admin routes additionally check `user.is_admin`.

## Database Models (`models.py`)

Nine models; key relationships:

- **User** → Bets (1:M), GroupMemberships (1:M), Groups owned (1:M), Nominations (1:M)
- **Event** → Bets (1:M), Nominees (1:M)
- **Bet** — unique constraint on `(user_id, event_id)` so one bet per user per event; `side` stores `"YES"/"NO"` for standard events or a roll number string for MLT events
- **Group** → GroupMemberships (1:M), PendingInvites (1:M), GroupActivityLogs (1:M)
- **GroupMembership** — `status` is `"invited"` or `"member"`; `coins_at_join` snapshot used for group P&L
- **PendingInvite** — stores invites for unregistered users by `roll_number`; converted to GroupMembership on registration
- **GroupActivityLog** — audit trail for group events (`"created"`, `"joined"`, `"invited"`, `"removed"`, `"left"`, `"ownership_transferred"`)
- **Nomination** — one per user per MLT event during nomination phase; unique constraint on `(nominator_id, event_id)`
- **Nominee** — top 5 revealed candidates for an MLT event; populated by admin via reveal route

## Key Business Logic

**Standard event odds** (in `routes/betting.py`): Live YES/NO odds computed from ratio of coins bet on each side. `prev_yes_odds` / `prev_no_odds` on `Event` track last snapshot for movement arrows.

**MLT event odds** (in `routes/betting.py`): Per-nominee pool odds — `total_pool / nominee_pool`. Default odds `1.0` when no bets yet.

**Bet resolution** (`/resolve/<event_id>/<result>` in `admin_bp`): Pays out winners proportionally based on `odds_at_time`. Sets `event.status = "resolved"` and `event.result`. Works for both standard (result = `"YES"`/`"NO"`) and MLT (result = roll number string) events.

**Most Likely To game flow:**
1. Admin creates event with `event_type="most_likely_to"` → `phase="nomination"`
2. Users submit one anonymous nomination (roll number) via `POST /nominate`
3. Admin triggers `POST /admin/mlt/<event_id>/reveal` → top 5 nominees saved, `phase="betting"`
4. Users place bets on a nominee (side = roll number) via standard `POST /bet`
5. Admin resolves by clicking a roll number link → standard resolve flow pays out

**Leaderboard tabs:**
- *Weekly* — sum of realized P&L from resolved events in the last 7 days
- *All-Time* — current coin balance ranking
- *Group* — groups ranked by total member coins; group P&L uses `coins_at_join` snapshots

**Group invites for unregistered users**: Stored in `PendingInvite` by `roll_number`. When a new user registers, `routes/auth.py` checks for matching pending invites and auto-creates `GroupMembership` records.

**Student directory** (`students.csv` in project root): Two-column CSV (`name,roll_number`). Admin edits directly. Registration validates roll numbers against this file — unrecognised roll numbers are hard-blocked. `load_students()` helper in `routes/auth.py` reads the CSV with `utf-8-sig` encoding (handles Excel BOM). `/directory` route cross-references CSV against users table to show registered status.

**Admin account**: Created directly via Flask shell, not through the registration form. Roll number is `"ADMIN"` (not in students.csv).

**Account deletion**: Admin can delete any non-admin user from the directory page (`POST /admin/users/<user_id>/delete`). Users can delete their own account from their profile (`POST /delete_account`). Both routes block deletion if the user owns a group with other members, auto-delete solo-owned groups, and clean up bets, memberships, logs, and nominations.

## Configuration

In `app.py`:
```python
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only')
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
```
`SECRET_KEY` reads from the environment; falls back to `'dev-only'` locally. Database file lives at `instance/database.db` (created automatically on first run).

CSRF protection is enabled via Flask-WTF (`CSRFProtect(app)`). Every `<form method="POST">` must include:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

## Key Conventions

- `Event.status` is always lowercase: `"open"` or `"resolved"`. Never `"Resolved"`.
- `Event.event_type` is `"standard"` or `"most_likely_to"`.
- `Event.phase` is `None` for standard events, `"nomination"` or `"betting"` for MLT events.
- `Bet.status` tracks bet outcome: `"pending"`, `"won"`, `"lost"`. There is no `bet.outcome` field.
- `Bet.side` is `"YES"`/`"NO"` for standard events, or a roll number string (e.g. `"A032"`) for MLT events.
- `Event.result` stores `"YES"`/`"NO"` for standard events, or a roll number for MLT events.
- Every route that renders a template extending `base.html` must pass `current_user=user` — the navbar references it unconditionally.
- Admin navbar has two links: **Create Event** (`admin.create_event`) and **Manage Groups** (`admin.admin_groups`).
- Admin profile renders `admin_profile.html` (no bet stats). Regular users render `profile.html`.
- Admin is blocked from `my_bets` route — redirects to dashboard.
- Roll numbers are always stored and compared uppercase (normalised on input with `.strip().upper()`).
