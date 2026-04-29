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
- `auth_bp` — register, login, logout, profile
- `betting_bp` — dashboard (event list + bet placement), leaderboard
- `admin_bp` — create/resolve events, manage groups
- `groups_bp` — create groups, invite, accept, leave, remove members, transfer ownership

**Auth pattern:** Session-based (`session['user_id']`), no Flask-Login. Every protected route manually checks `session.get('user_id')` and redirects to `auth.login` if missing. Admin routes additionally check `user.is_admin`.

## Database Models (`models.py`)

Seven models; key relationships:

- **User** → Bets (1:M), GroupMemberships (1:M), Groups owned (1:M)
- **Event** → Bets (1:M)
- **Bet** — unique constraint on `(user_id, event_id)` so one bet per user per event
- **Group** → GroupMemberships (1:M), PendingInvites (1:M), GroupActivityLogs (1:M)
- **GroupMembership** — `status` is `"invited"` or `"member"`; `coins_at_join` snapshot used for group P&L
- **PendingInvite** — stores invites for unregistered users by `roll_number`; converted to GroupMembership on registration
- **GroupActivityLog** — audit trail for group events (`"created"`, `"joined"`, `"invited"`, `"removed"`, `"left"`, `"ownership_transferred"`)

## Key Business Logic

**Odds calculation** (in `routes/betting.py`): Live YES/NO odds are computed from the ratio of coins bet on each side across all bets for an event. `prev_yes_odds` / `prev_no_odds` on `Event` track the last snapshot for movement arrows.

**Bet resolution** (`/resolve/<event_id>/<result>` in `admin_bp`): Pays out winners proportionally based on their `odds_at_time`. Sets `event.status = "resolved"` and `event.result`.

**Leaderboard tabs:**
- *Weekly* — sum of realized P&L from resolved events in the last 7 days
- *All-Time* — current coin balance ranking
- *Group* — groups ranked by total member coins; group P&L uses `coins_at_join` snapshots

**Group invites for unregistered users**: Stored in `PendingInvite` by `roll_number`. When a new user registers, `routes/auth.py` checks for matching pending invites and auto-creates `GroupMembership` records.

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
- `Bet.status` tracks bet outcome: `"pending"`, `"won"`, `"lost"`. There is no `bet.outcome` field.
- Every route that renders a template extending `base.html` must pass `current_user=user` — the navbar references it unconditionally.
- Admin navbar has two links: **Create Event** (`admin.create_event`) and **Manage Groups** (`admin.admin_groups`).
