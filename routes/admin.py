from flask import Blueprint, request, redirect, url_for, session, render_template
from models import db, Event, User, Bet

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/create_event", methods=["POST","GET"])
def create_event():
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session["user_id"])
    
    if not user.is_admin:
        return "Not authorized", 403
    
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        event = Event(
            title=title,
            description=description
        )

        db.session.add(event)
        db.session.commit()
        print("Event created")


        return redirect(url_for("betting.dashboard"))
    
    return render_template("create_event.html")

@admin_bp.route('/resolve/<int:event_id>/<result>')
def resolve_event(event_id, result):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session["user_id"])
    
    if not user.is_admin:
        return "Not authorized", 403

    event = db.session.get(Event, event_id)

    event.status = 'resolved'
    event.result = result

    bets = Bet.query.filter_by(event_id=event.id).all()

    for bet in bets:
        if bet.side == result:
            winner = db.session.get(User, bet.user_id)
            payout = bet.amount*2
            winner.coins += payout

    db.session.commit()
    return redirect(url_for('betting.dashboard'))