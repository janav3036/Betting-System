from flask import Blueprint, render_template, request, redirect,url_for, session
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from models import db, Event, Bet, User

betting_bp = Blueprint("betting", __name__)

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

        yes_pool = sum(b.amount for b in bets if b.side == "YES")
        no_pool = sum(b.amount for b in bets if b.side == "NO")

        total = yes_pool + no_pool

        if total>0:
            yes_prob = round(yes_pool/total*100,1)
            no_prob = round(no_pool/total*100,1)
        else:
            yes_prob=50
            no_prob=50

        yes_odds = round(total / yes_pool, 2) if yes_pool > 0 else 2.0
        no_odds = round(total / no_pool, 2) if no_pool > 0 else 2.0
        
        user_bet = Bet.query.filter_by(
            event_id = event.id,
            user_id=user.id
        ).first()

        event_data.append({
            "event": event,
            "yes_pool": yes_pool,
            "no_pool": no_pool,
            "yes_prob": yes_prob,
            "no_prob": no_prob,
            "yes_odds": yes_odds,
            "no_odds": no_odds,
            "user_bet": user_bet
        })

    return render_template(
        "dashboard.html",
        event_data=event_data,
        current_user=user
    )
@betting_bp.route("/bet", methods = ["POST"])
def place_bet():
    event_id = int(request.form.get("event_id"))
    side = request.form.get("side")
    amount = int(request.form.get("amount"))
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user_id = session["user_id"]
    user = db.session.get(User, user_id)
    
    if user.coins<amount:
        print("Not enough coins")
        return redirect(url_for("betting.dashboard"))

    bets = Bet.query.filter_by(event_id=event_id).all()

    yes_pool = sum(b.amount for b in bets if b.side == "YES")
    no_pool = sum(b.amount for b in bets if b.side == "NO")

    if side == "YES":
        yes_pool += amount
    else:
        no_pool += amount

    total = yes_pool + no_pool

    if side == "YES":
        odds = total / yes_pool if yes_pool > 0 else 2.0
    else:
        odds = total / no_pool if no_pool > 0 else 2.0

    
    bet = Bet(
        user_id = user_id,
        event_id = event_id,
        side = side,
        amount = amount,
        odds_at_time = round(odds, 2)

    )

    try:
        db.session.add(bet)
        user.coins -= amount
        db.session.commit()
        print("BET: ", user_id, event_id, side)

    except IntegrityError:
        db.session.rollback()
        print("Duplicate bet prevented")

    return redirect(url_for("betting.dashboard"))

@betting_bp.route('/leaderboard')
def leaderboard():
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    
    current_user = db.session.get(User, session['user_id'])

    total_users = User.query.order_by(User.coins.desc()).limit(7).all()

    week_start = datetime.utcnow() - timedelta(days=7)

    weekly_results = (
        db.session.query(
            User.username,
            db.func.sum(Bet.amount * Bet.odds_at_time).label("weekly_profit")
        )
        .join(Bet, Bet.user_id == User.id)
        .join(Event, Event.id == Bet.event_id)
        .filter(Event.status == 'resolved')
        .filter(Event.created_at >=week_start)
        .group_by(User.id)
        .order_by(db.desc("weekly_profit"))
        .limit(7)
        .all()
    )
    return render_template(
        "leaderboard.html", 
        total_users=total_users,
        weekly_results=weekly_results,
        current_user=current_user
    )
