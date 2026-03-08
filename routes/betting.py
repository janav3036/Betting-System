from flask import Blueprint, render_template, request, redirect,url_for, session
from sqlalchemy.exc import IntegrityError
from models import db, Event, Bet, User

betting_bp = Blueprint("betting", __name__)

@betting_bp.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session["user_id"])
    events = Event.query.all()
    return render_template("dashboard.html", events = events, current_user_coins = user.coins)

@betting_bp.route("/bet", methods = ["POST"])
def place_bet():
    event_id = int(request.form.get("event_id"))
    side = request.form.get("side")
    amount = int(request.form.get("amount"))

    user_id = 1
    user = User.query.get(user_id)

    if user.coins<amount:
        print("Not enough coins")
        return redirect(url_for("betting.dashboard"))

    user.coins -= amount

    bet = Bet(
        user_id = user_id,
        event_id = event_id,
        side = side,
        amount = amount,
        odds_at_time = 1.0

    )

    try:
        db.session.add(bet)
        db.session.commit()
        print("BET: ", user_id, event_id, side)

    except IntegrityError:
        db.session.rollback()
        print("Duplicate bet prevented")

    return redirect(url_for("betting.dashboard"))


