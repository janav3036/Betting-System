from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy import case
from models import db, Event, Bet, User, Group, GroupMembership, Nomination, Nominee
from routes.auth import load_students

betting_bp = Blueprint("betting", __name__)


# DASHBOARD
@betting_bp.route("/")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])

    if user is None:
        session.clear()
        return redirect(url_for("auth.login"))

    events = Event.query.all()

    event_data = []

    for event in events:

        bets = Bet.query.filter_by(event_id=event.id).all()
        user_bet = Bet.query.filter_by(event_id = event.id, user_id = user.id).first()

        if event.event_type == 'most_likely_to':
            nominees = Nominee.query.filter_by(event_id = event.id).all()
            total_pool = sum(b.amount for b in bets)

            nominee_data = []
            for n in nominees:
                pool = sum(b.amount for b in bets if b.side == n.roll_number)
                odds = round(total_pool/pool,2) if pool>0 else None
                nominee_data.append({
                    "roll_number": n.roll_number,
                    "pool": pool,
                    "odds": odds
                })

            user_nomination = None
            if event.phase == "nomination":
                user_nomination = Nomination.query.filter_by(
                    event_id = event.id,
                    nominator_id = user.id
                ).first()

            event_data.append({
            "event": event,
            "nominees": nominee_data,
            "user_bet": user_bet,
            "user_nomination": user_nomination,
            "yes_pool": 0, "no_pool": 0,
            "yes_prob": 0, "no_prob": 0,
            "yes_odds": 0, "no_odds": 0,
            "yes_direction": "same", "no_direction": "same"
        })

        else:
            yes_pool = sum(b.amount for b in bets if b.side == "YES")
            no_pool = sum(b.amount for b in bets if b.side == "NO")
            total = yes_pool + no_pool

            if total > 0:
                yes_prob = round((yes_pool / total) * 100, 1)
                no_prob = round((no_pool / total) * 100, 1)
            else:
                yes_prob = 50
                no_prob = 50

            yes_odds = round(total / yes_pool, 2) if yes_pool > 0 else 2.0
            no_odds = round(total / no_pool, 2) if no_pool > 0 else 2.0

            yes_direction = "same"
            no_direction = "same"

            if event.prev_yes_odds:
                if yes_odds > event.prev_yes_odds:
                    yes_direction = "up"
                elif yes_odds < event.prev_yes_odds:
                    yes_direction = "down"

            if event.prev_no_odds:
                if no_odds > event.prev_no_odds:
                    no_direction = "up"
                elif no_odds < event.prev_no_odds:
                    no_direction = "down"

            event_data.append({
                "event": event,
                "yes_pool": yes_pool,
                "no_pool": no_pool,
                "yes_prob": yes_prob,
                "no_prob": no_prob,
                "yes_odds": yes_odds,
                "no_odds": no_odds,
                "yes_direction": yes_direction,
                "no_direction": no_direction,
                "user_bet": user_bet,
                "nominees": [],
                "user_nomination": None
            })          
            
    return render_template(
        "dashboard.html",
        event_data=event_data,
        current_user=user,
        students=load_students()
    )


# PLACE BET
@betting_bp.route("/bet", methods=["POST"])
def place_bet():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user_id = session["user_id"]
    user = db.session.get(User, user_id)

    event_id = int(request.form.get("event_id"))
    side = request.form.get("side")
    amount = int(request.form.get("amount"))

    if amount <= 0:
        return redirect(url_for("betting.dashboard"))

    if user.coins < amount:
        print("Not enough coins")
        return redirect(url_for("betting.dashboard"))

    bets = Bet.query.filter_by(event_id=event_id).all()

    event = db.session.get(Event, event_id)
    if event.event_type == "most_likely_to":
        total = sum(b.amount for b in bets)
        side_pool = sum(b.amount for b in bets if b.side == side)
        odds = round(total / side_pool, 2) if side_pool > 0 else 1.0

        yes_odds = 0
        no_odds = 0
    else:
        yes_pool = sum(b.amount for b in bets if b.side == "YES")
        no_pool = sum(b.amount for b in bets if b.side == "NO")
        total = yes_pool + no_pool

        if side == "YES":
            odds = total / yes_pool if yes_pool > 0 else 2.0
        else:
            odds = total / no_pool if no_pool > 0 else 2.0

        yes_odds = round(total / yes_pool, 2) if yes_pool > 0 else 2.0
        no_odds = round(total / no_pool, 2) if no_pool > 0 else 2.0
    # store previous odds for movement tracking
    event.prev_yes_odds = yes_odds
    event.prev_no_odds = no_odds

    bet = Bet(
        user_id=user_id,
        event_id=event_id,
        side=side,
        amount=amount,
        odds_at_time=round(odds, 2)
    )

    try:
        db.session.add(bet)

        # deduct coins
        user.coins -= amount

        db.session.commit()

        print("BET:", user_id, event_id, side)

    except IntegrityError:
        db.session.rollback()
        print("Duplicate bet prevented")

    return redirect(url_for("betting.dashboard"))

# LEADERBOARD
@betting_bp.route("/leaderboard")
def leaderboard():

    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    current_user = db.session.get(User, session["user_id"])

    # total leaderboard
    total_users = User.query.filter(User.is_admin==False).order_by(User.coins.desc()).limit(7).all()

    # weekly leaderboard
    week_start = datetime.utcnow() - timedelta(days=7)

    weekly_results = (
        db.session.query(
            User.username,
            db.func.sum(
                case(
                    (Bet.side == Event.result,
                     Bet.amount * Bet.odds_at_time - Bet.amount),
                    else_=-Bet.amount
                )
            ).label("weekly_profit")
        )
        .join(Bet, Bet.user_id == User.id)
        .join(Event, Event.id == Bet.event_id)
        .filter(Event.status == "resolved")
        .filter(Event.created_at >= week_start)
        .group_by(User.id)
        .order_by(db.desc("weekly_profit"))
        .limit(7)
        .all()
    )
    
    groups_data=[]
    for group in Group.query.all():
        memberships = GroupMembership.query.filter_by(group_id = group.id, status='member').all()
        if not memberships:
            continue
        total_coins=0
        total_pnl=0
        for m in memberships:
            member = db.session.get(User, m.user_id)
            total_coins+=member.coins
            total_pnl += (member.coins - m.coins_at_join) if m.coins_at_join is not None else 0
        groups_data.append({
            "group": group,
            "total_coins": total_coins,
            "average_coins" : round(total_coins/len(memberships), 1),
            "total_pnl": total_pnl,
            "member_count": len(memberships)
        })

    return render_template(
        "leaderboard.html",
        total_users=total_users,
        weekly_results=weekly_results,
        group_data=groups_data,
        current_user=current_user
    )

@betting_bp.route("/nominate", methods=["POST"])
def nominate():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    user_id = session["user_id"]
    event_id = int(request.form.get("event_id"))
    roll_number = request.form.get("roll_number", "").strip().upper()

    if not roll_number:
        return redirect(url_for('betting.dashboard'))
    
    event = db.session.get(Event, event_id)
    if not event or event.event_type!="most_likely_to" or event.phase!="nomination":
        return redirect(url_for('betting.dashboard'))
    
    nomination = Nomination(
        event_id=event_id,
        nominator_id = user_id,
        roll_number=roll_number
    )

    try:
        db.session.add(nomination)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

    return redirect(url_for('betting.dashboard'))
