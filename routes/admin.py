from flask import Blueprint, request, redirect, url_for, session, render_template
from models import db, Event, User, Bet, Group, GroupMembership, GroupActivityLog, PendingInvite

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
            payout = round(bet.amount*bet.odds_at_time)
            winner.coins += payout

    db.session.commit()
    return redirect(url_for('betting.dashboard'))

@admin_bp.route("/admin/groups", methods=["GET"])
def admin_groups():
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session["user_id"])
    
    if not user.is_admin:
        return "Not authorized", 403
    
    groups=Group.query.all()
    group_data=[]
    for group in groups:
        owner = User.query.filter_by(id=group.owner_id).first()
        members = GroupMembership.query.filter_by(group_id = group.id).count()
        item = {
            "group": group,
            "owner": owner,
            "members": members
        }
        group_data.append(item)

    return render_template("admin_groups.html", group_data = group_data, current_user=user)

@admin_bp.route("/admin/groups/<int:group_id>/delete", methods=["POST"])
def admin_delete_group(group_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session["user_id"])
    
    if not user.is_admin:
        return "Not authorized", 403
    group = db.session.get(Group, group_id)
    
    GroupMembership.query.filter_by(group_id=group_id).delete()
    PendingInvite.query.filter_by(group_id=group_id).delete()
    GroupActivityLog.query.filter_by(group_id=group_id).delete()

    name = group.name
    db.session.delete(group)
    db.session.commit()
    
    return redirect(url_for("admin.admin_groups", message=f"{name} has been deleted"))
