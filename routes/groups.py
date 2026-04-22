from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime
from models import db, Group, User, GroupMembership, PendingInvite, GroupActivityLog

groups_bp = Blueprint("groups", __name__)

@groups_bp.route("/groups")
def groups():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    user = db.session.get(User, session["user_id"])
    memberships = GroupMembership.query.filter_by(user_id=user.id).all()

    group_data = []
    for member in memberships:
        group = db.session.get(Group, member.group_id)
        member_count = GroupMembership.query.filter_by(group_id=group.id, status="member").count()
        pnl = user.coins - member.coins_at_join if member.coins_at_join is not None else None
        group_data.append({
            "group":group,
            "membership": member,
            "member_count": member_count,
            "pnl": pnl,
            "is_owner": group.owner_id == user.id
        })

    return render_template("groups.html", group_data=group_data, current_user=user)

@groups_bp.route("/groups/create", methods=["POST"])
def create_group():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    user = db.session.get(User, session["user_id"])
    name = request.form.get("name", "").strip()

    if not name:
        return redirect(url_for("groups.groups"))
    
    group = Group(name=name, owner_id = user.id)
    db.session.add(group)
    db.session.flush()  # Get group.id before commit

    membership = GroupMembership(
        group_id = group.id,
        user_id= user.id,
        status="member",
        coins_at_join = user.coins

    )

    db.session.add(membership)

    log = GroupActivityLog(
        group_id = group.id,
        user_id = user.id,
        action="created"
    )
    db.session.add(log)

    db.session.commit()
    return redirect(url_for("groups.group_detail", group_id = group.id))


@groups_bp.route("/groups/<int: group_id>")
def group_detail(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)
    if not group:
        return redirect(url_for("groups.groups"))
    
    membership = GroupMembership.query.filter_by(group_id=group_id, user_id= user.id).first()

    if not membership:
        return redirect(url_for("groups.groups"))
    
    members= GroupMembership.query.filter_by(group_id=group_id, status="member").all()
    invited= GroupMembership.query.filter_by(group_id=group_id, status="invited").all()
    pending= PendingInvite.query.filter_by(group_id=group_id).all()


    member_data=[]
    for m in members:
        member_user = db.session.get(User, m.user_id)
        pnl = member_user.coins - m.coins_at_join if m.coins_at_join is not None else None
        member_data.append({
            "user": member_user,
            "coins": member_user.coins,
            "pnl": pnl,
            "is_owner": group.owner_id == member_user.id
        
        })

    member_data.sort(key = lambda x: x["pnl"], reverse=True)

    return render_template(
        "group_detail.html",
        group=group,
        current_user=user,
        membership=membership,
        member_data=member_data,
        invited=invited,
        pending=pending,
        is_owner=group.owner_id == user.id
    )



