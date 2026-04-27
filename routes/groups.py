from flask import Blueprint, render_template, request, redirect, url_for, session
from datetime import datetime
from models import db, Group, User, GroupMembership, PendingInvite, GroupActivityLog
from sqlalchemy.exc import IntegrityError

groups_bp = Blueprint("groups", __name__)


def _get_group_detail_context(group, user):
    members = GroupMembership.query.filter_by(group_id=group.id, status='member').all()
    invited_memberships = GroupMembership.query.filter_by(group_id=group.id, status='invited').all()
    pending = PendingInvite.query.filter_by(group_id=group.id).all()
    membership = GroupMembership.query.filter_by(group_id=group.id, user_id=user.id).first()

    member_data = []
    for m in members:
        member_user = db.session.get(User, m.user_id)
        pnl = member_user.coins - m.coins_at_join if m.coins_at_join is not None else 0
        member_data.append({
            "user": member_user,
            "coins": member_user.coins,
            "pnl": pnl,
            "is_owner": group.owner_id == member_user.id
        })
    member_data.sort(key=lambda x: x["pnl"], reverse=True)
    invited = [{"user": db.session.get(User, m.user_id), "membership": m} for m in invited_memberships]

    return {
        "group": group,
        "current_user": user,
        "membership": membership,
        "member_data": member_data,
        "invited": invited,
        "pending": pending,
        "is_owner": group.owner_id == user.id
    }


@groups_bp.route("/groups")
def groups():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    memberships = GroupMembership.query.filter_by(user_id=user.id).all()

    active = []
    invited = []
    for m in memberships:
        group = db.session.get(Group, m.group_id)
        member_count = GroupMembership.query.filter_by(group_id=group.id, status="member").count()
        pnl = user.coins - m.coins_at_join if m.coins_at_join is not None else None
        item = {
            "group": group,
            "membership": m,
            "member_count": member_count,
            "pnl": pnl,
            "is_owner": group.owner_id == user.id
        }
        if m.status == "member":
            active.append(item)
        elif m.status == "invited":
            invited.append(item)

    return render_template("groups.html", active=active, invites=invited, current_user=user)


@groups_bp.route("/groups/create", methods=["POST"])
def create_group():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    name = request.form.get("name", "").strip()

    if not name:
        return redirect(url_for("groups.groups"))

    group = Group(name=name, owner_id=user.id)
    db.session.add(group)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return render_template("groups.html", active=[], invites=[], current_user=user, error="A group with that name already exists")

    membership = GroupMembership(group_id=group.id, user_id=user.id, status="member", coins_at_join=user.coins)
    db.session.add(membership)
    db.session.add(GroupActivityLog(group_id=group.id, user_id=user.id, action="created"))
    db.session.commit()

    return redirect(url_for("groups.group_detail", group_id=group.id))


@groups_bp.route("/groups/<int:group_id>")
def group_detail(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)

    if not group:
        return redirect(url_for("groups.groups"))

    ctx = _get_group_detail_context(group, user)
    if not ctx["membership"] and not user.is_admin:
        return redirect(url_for("groups.groups"))

    return render_template("group_detail.html", **ctx)


@groups_bp.route("/groups/<int:group_id>/accept", methods=["POST"])
def accept_invite(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    membership = GroupMembership.query.filter_by(group_id=group_id, user_id=user.id).first()

    if not membership:
        return redirect(url_for("groups.groups"))

    member_count = GroupMembership.query.filter_by(group_id=group_id, status="member").count()
    if member_count >= 10:
        return render_template("groups.html", active=[], invites=[], current_user=user, error="Group is full.")

    membership.status = "member"
    membership.joined_at = datetime.utcnow()
    membership.coins_at_join = user.coins
    db.session.add(GroupActivityLog(group_id=group_id, user_id=user.id, action="joined"))
    db.session.commit()

    return redirect(url_for("groups.group_detail", group_id=group_id))


@groups_bp.route("/groups/<int:group_id>/invite", methods=["POST"])
def invite(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)

    if group.owner_id != user.id:
        return redirect(url_for("groups.group_detail", group_id=group_id))

    member_count = GroupMembership.query.filter_by(group_id=group_id, status="member").count()
    if member_count >= 10:
        ctx = _get_group_detail_context(group, user)
        return render_template("group_detail.html", error="Group is full.", **ctx)

    roll_number = request.form.get("roll_number", "").strip().upper()
    target_user = User.query.filter_by(roll_number=roll_number).first()

    if target_user:
        existing = GroupMembership.query.filter_by(group_id=group_id, user_id=target_user.id).first()
        if not existing:
            db.session.add(GroupMembership(group_id=group_id, user_id=target_user.id, status="invited"))
            db.session.add(GroupActivityLog(group_id=group_id, user_id=target_user.id, action="invited"))
            db.session.commit()
    else:
        confirm = request.form.get("confirm")
        if confirm == "yes":
            existing_pending = PendingInvite.query.filter_by(group_id=group_id, roll_number=roll_number).first()
            if not existing_pending:
                db.session.add(PendingInvite(group_id=group_id, roll_number=roll_number))
                db.session.commit()
        else:
            ctx = _get_group_detail_context(group, user)
            return render_template("group_detail.html", unregistered_roll=roll_number, **ctx)

    return redirect(url_for("groups.group_detail", group_id=group_id))


@groups_bp.route("/groups/<int:group_id>/leave", methods=["POST"])
def leave_group(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)
    membership = GroupMembership.query.filter_by(group_id=group_id, user_id=user.id).first()

    if not membership:
        return redirect(url_for("groups.groups"))

    if group.owner_id == user.id:
        member_count = GroupMembership.query.filter_by(group_id=group_id, status="member").count()
        if member_count > 1:
            ctx = _get_group_detail_context(group, user)
            return render_template("group_detail.html", error="Transfer ownership before leaving.", **ctx)
        else:
            db.session.delete(membership)
            db.session.delete(group)
            db.session.commit()
            return redirect(url_for("groups.groups"))

    db.session.add(GroupActivityLog(group_id=group_id, user_id=user.id, action="left"))
    db.session.delete(membership)
    db.session.commit()
    return redirect(url_for("groups.groups"))


@groups_bp.route("/groups/<int:group_id>/remove/<int:target_id>", methods=["POST"])
def remove_member(group_id, target_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)

    if group.owner_id != user.id:
        return redirect(url_for("groups.group_detail", group_id=group_id))

    membership = GroupMembership.query.filter_by(group_id=group_id, user_id=target_id).first()
    if membership:
        db.session.add(GroupActivityLog(group_id=group_id, user_id=target_id, action="removed"))
        db.session.delete(membership)
        db.session.commit()

    return redirect(url_for("groups.group_detail", group_id=group_id))


@groups_bp.route("/groups/<int:group_id>/transfer", methods=["POST"])
def transfer_ownership(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)

    if group.owner_id != user.id:
        return redirect(url_for("groups.group_detail", group_id=group_id))

    new_owner_id = int(request.form.get("new_owner_id"))
    membership = GroupMembership.query.filter_by(group_id=group_id, user_id=new_owner_id, status='member').first()

    if not membership:
        return redirect(url_for("groups.group_detail", group_id=group_id))

    group.owner_id = new_owner_id
    db.session.add(GroupActivityLog(group_id=group_id, user_id=user.id, action='ownership_transferred'))
    db.session.commit()

    return redirect(url_for("groups.group_detail", group_id=group_id))


@groups_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
def delete_group(group_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, session["user_id"])
    group = db.session.get(Group, group_id)

    if group.owner_id != user.id:
        return redirect(url_for("groups.group_detail", group_id=group_id))

    GroupMembership.query.filter_by(group_id=group_id).delete()
    PendingInvite.query.filter_by(group_id=group_id).delete()
    GroupActivityLog.query.filter_by(group_id=group_id).delete()
    db.session.delete(group)
    db.session.commit()

    return redirect(url_for("groups.groups"))