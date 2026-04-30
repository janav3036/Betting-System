from flask import Blueprint, request, redirect, url_for, session, render_template, send_file
import os
from models import db, Event, User, Bet, Group, GroupMembership, GroupActivityLog, PendingInvite, Nominee, Nomination

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
        event_type = request.form.get("event_type", "standard")

        if not title or not description:
            return render_template("create_event.html", error="Fields are empty." , current_user=user)
        
        event = Event(
            title=title,
            description=description,
            event_type = event_type,
            phase="nomination" if event_type== "most_likely_to" else None
        )

        db.session.add(event)
        db.session.commit()
        print("Event created")


        return redirect(url_for("betting.dashboard"))
    
    return render_template("create_event.html", current_user=user)

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
    try:
        for bet in bets:
            if bet.side == result:
                bet.status = 'won'
                winner = db.session.get(User, bet.user_id)
                payout = round(bet.amount * bet.odds_at_time)
                winner.coins += payout  
            else:
                bet.status = 'lost'

        db.session.commit()
    except Exception:
        db.session.rollback()
        return "Resolution Failed, please try again", 500
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


@admin_bp.route("/admin/mlt/<int:event_id>/reveal", methods=["POST"])
def reveal_nominees(event_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session["user_id"])
    
    if not user.is_admin:
        return "Not authorized", 403
    
    event = db.session.get(Event, event_id)
    if not event or event.event_type!="most_likely_to" or event.phase!="nomination":
        return redirect(url_for('betting.dashboard'))
    
    nominations  = Nomination.query.filter_by(event_id=event_id).all()

    counts={}
    for n in nominations:
        counts[n.roll_number] = counts.get(n.roll_number, 0)+1

    top5 = sorted(counts.items(), key= lambda x: x[1], reverse=True)[:5]

    for roll_number, count in top5:
        nominee = Nominee(
            event_id=event_id,
            roll_number=roll_number,
            nomination_count=count
        )
        db.session.add(nominee)

    event.phase='betting'
    db.session.commit()

    return redirect(url_for('betting.dashboard'))

@admin_bp.route('/admin/users/<int:user_id>/delete', methods=["POST"])
def admin_delete_user(user_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    user= db.session.get(User, session['user_id'])
    if not user.is_admin:
        return "Not authorized", 403
    
    target = db.session.get(User, user_id)
    if not target or target.is_admin:
        return "Cannot delete this user", 400

    owned_groups = Group.query.filter_by(owner_id=user_id).all()
    for group in owned_groups:
        other_members = GroupMembership.query.filter_by(
            group_id=group.id, status="member"
        ).filter(GroupMembership.user_id != user_id).first()
        if other_members:
            return f"User owns group '{group.name}' with other members. Transfer ownership first.", 400
        GroupMembership.query.filter_by(group_id=group.id).delete()
        GroupActivityLog.query.filter_by(group_id=group.id).delete()
        PendingInvite.query.filter_by(group_id=group.id).delete()
        db.session.delete(group)

    Bet.query.filter_by(user_id=user_id).delete()
    GroupMembership.query.filter_by(user_id=user_id).delete()
    GroupActivityLog.query.filter_by(user_id=user_id).delete()
    Nomination.query.filter_by(nominator_id=user_id).delete()

    db.session.delete(target)
    db.session.commit()

    return redirect(url_for("auth.directory"))

@admin_bp.route('/admin/mlt/<int:event_id>/nominations')
def nomination_counts(event_id):
    if "user_id" not in session:
        return {"error" : "unauthorized"}, 401
    user= db.session.get(User, session['user_id'])
    if not user.is_admin:
        return {"error": "Not authorized"}, 403
    
    from routes.auth import load_students
    from flask import jsonify

    nominations = Nomination.query.filter_by(event_id=event_id).all()
    counts={}
    for n in nominations:
        counts[n.roll_number] = counts.get(n.roll_number, 0)+1

    students = {s['roll_number'] : s['name'] for s in load_students()}
    top5 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return jsonify([
        {"roll": roll, "name": students.get(roll, roll), "count": count}
        for roll, count in top5
    ])

@admin_bp.route('/admin/events')
def admin_events():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session['user_id'])
    if not user.is_admin:
        return "Not authorized", 403

    events = Event.query.order_by(Event.created_at.desc()).all()
    event_data = [
        {'event': e, 'bet_count': Bet.query.filter_by(event_id=e.id).count()}
        for e in events
    ]
    return render_template('admin_events.html', current_user=user, event_data=event_data)


@admin_bp.route('/admin/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session['user_id'])
    if not user.is_admin:
        return "Not authorized", 403

    event = db.session.get(Event, event_id)
    if not event:
        return "Event not found", 404

    if event.status == 'open':
        bets = Bet.query.filter_by(event_id=event_id).all()
        for bet in bets:
            bettor = db.session.get(User, bet.user_id)
            if bettor:
                bettor.coins += bet.amount
            db.session.delete(bet)
    else:
        Bet.query.filter_by(event_id=event_id).delete()

    Nomination.query.filter_by(event_id=event_id).delete()
    Nominee.query.filter_by(event_id=event_id).delete()
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('admin.admin_events'))


@admin_bp.route('/admin/download-db')
def download_db():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session['user_id'])
    if not user.is_admin:
        return "Not authorized", 403
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance', 'database.db')
    return send_file(os.path.abspath(db_path), as_attachment=True, download_name='database.db')