from flask import Blueprint, render_template, request, redirect,url_for, session
from models import db, Bet, Event, User, PendingInvite, GroupMembership, Group,GroupActivityLog, Nomination
from sqlalchemy.exc import IntegrityError
import bcrypt
import csv
import os

auth_bp = Blueprint("auth", __name__)

def load_students():
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'students.csv')
    students = []
    try:
        with open(path, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                students.append({
                    'name': row['name'].strip(),
                    'roll_number': row['roll_number'].strip().upper()
                })
    except FileNotFoundError:
        pass
    return students

@auth_bp.route("/register", methods = ["GET","POST"])
def register():

    if request.method =='POST':
        username = request.form.get('username')
        password = request.form.get('password')
        roll_number = request.form.get('roll_number').strip().upper()

        valid_rolls = {s['roll_number'] for s in load_students()}
        if roll_number not in valid_rolls:
            return render_template(
                'register.html',
                error="Roll Number not found in Student List.",
                students = load_students()
            )

        enc_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        
        if User.query.filter_by(roll_number=roll_number).first():
            return render_template('register.html', error = "Roll number already registered", students=load_students())
        
        user = User(
            username = username,
            roll_number = roll_number,
            password_hash = enc_password.decode(),
            coins = 1000
        )
        try:

            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return render_template('register.html',
                                   error="Roll number already registered. ",
                                   students=load_students)
        pending = PendingInvite.query.filter_by(roll_number=roll_number).all()
        for invite in pending:
            membership = GroupMembership(
                group_id = invite.group_id,
                user_id = user.id,
                status="invited",
                coins_at_join = None

            )
            db.session.add(membership)
            db.session.delete(invite)
        db.session.commit()

        print('User created')

        return redirect(url_for("auth.login"))
    
    return render_template('register.html', students=load_students())

@auth_bp.route('/login', methods = ["GET","POST"])
def login():
    error=None
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()


        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            session['user_id'] = user.id
            return redirect(url_for('betting.dashboard'))
        
        error='Invalid username or password'
    return render_template('login.html', error=error)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    if user.is_admin:
        return render_template('admin_profile.html', current_user=user)
    bets = Bet.query.filter_by(user_id = user.id).all()

    bet_data = []
    total_pnl = 0
    wins = 0
    losses = 0
    
    for bet in bets:
        event = Event.query.get(bet.event_id)
        if event.status == 'resolved':
            if bet.side == event.result:
                pl = round((bet.amount * bet.odds_at_time) - bet.amount, 2)
                outcome = "Win"
                wins+=1
            else: 
                pl = -bet.amount
                outcome = "Loss"
                losses += 1
            total_pnl += pl
        else:
            pl = None
            outcome = "Pending"

        bet_data.append({
            "event_title": event.title,
            "side": bet.side,
            "amount": bet.amount,
            "odds": bet.odds_at_time,
            "outcome": outcome,
            "pnl": pl
        })

    resolved = wins+losses
    win_rate = round(wins/resolved,1) if resolved>0 else 0

    all_users = User.query.filter_by(is_admin=False).order_by(User.coins.desc()).all()
    rank = next((i + 1 for i, u in enumerate(all_users) if u.id == user.id), None)

    return render_template(
        'profile.html',
        current_user = user,
        bet_data = bet_data,
        wins = wins,
        losses = losses,
        win_rate = win_rate,
        total_pnl = round(total_pnl,2)
    )


@auth_bp.route('/my_bets')
def my_bets():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if user.is_admin:
        return redirect(url_for('betting.dashboard'))
    bets = Bet.query.filter_by(user_id=user.id).all()

    bet_data = []
    for bet in bets:
        event = Event.query.get(bet.event_id)
        if event.status == 'resolved':
            if bet.side == event.result:
                pl = round((bet.amount * bet.odds_at_time) - bet.amount, 2)
                outcome = "Win"
            else:
                pl = -bet.amount
                outcome = "Loss"
        else:
            pl = None
            outcome = "Pending"

        bet_data.append({
            "event_title": event.title,
            "side": bet.side,
            "amount": bet.amount,
            "odds": bet.odds_at_time,
            "outcome": outcome,
            "pnl": pl
        })

    return render_template('my_bets.html', current_user=user, bet_data=bet_data)


@auth_bp.route('/directory')
def directory():
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    
    current_user = db.session.get(User, session['user_id'])
    students = load_students()

    entries =[]
    for s in students:
        registered_user = User.query.filter_by(roll_number=s['roll_number'], is_admin=False).first()
        entries.append({
            'name': s['name'],
            'roll_number': s['roll_number'],
            'registered': registered_user is not None,
            'user_id': registered_user.id if registered_user else None
        })
    return render_template('directory.html', entries=entries, current_user=current_user)   

@auth_bp.route('/delete_account', methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    owned_groups = Group.query.filter_by(owner_id=user_id).all()
    for group in owned_groups:
        other_members = GroupMembership.query.filter_by(
            group_id=group.id, status="member"
        ).filter(GroupMembership.user_id != user_id).first()
        if other_members:
            return f"You own group '{group.name}'. Transfer ownership before deleting your account.", 400
        GroupMembership.query.filter_by(group_id=group.id).delete()
        GroupActivityLog.query.filter_by(group_id=group.id).delete()
        PendingInvite.query.filter_by(group_id=group.id).delete()
        db.session.delete(group)

    Bet.query.filter_by(user_id=user_id).delete()
    GroupMembership.query.filter_by(user_id=user_id).delete()
    GroupActivityLog.query.filter_by(user_id=user_id).delete()
    Nomination.query.filter_by(nominator_id=user_id).delete()

    db.session.delete(user)
    db.session.commit()
    session.clear()

    return redirect(url_for('auth.login'))

@auth_bp.route('/user/<int:user_id>')
def user_profile(user_id):
    if "user_id" not in session:
        return redirect(url_for('auth.login'))
    
    current_user = db.session.get(User, session['user_id'])
    viewed_user = db.session.get(User, user_id)

    if viewed_user is None or viewed_user.is_admin:
        return redirect(url_for('betting.dashboard'))
    
    bets = Bet.query.filter_by(user_id=viewed_user.id).all()
    wins=losses=0
    total_pnl=0

    for bet in bets:
        event = Event.query.get(bet.event_id)
        if event.status == 'resolved':
            if bet.side == event.result:
                total_pnl += round((bet.amount * bet.odds_at_time) - bet.amount, 2)
                wins+=1
            else:
                total_pnl -= bet.amount
                losses+=1

    resolved = wins+losses
    win_rate = round(wins/resolved, 1) if resolved>1 else 0
    all_users = User.query.filter_by(is_admin=False).order_by(User.coins.desc()).all()
    rank = next((i + 1 for i, u in enumerate(all_users) if u.id == viewed_user.id), None)

    return render_template(
        'user_profile.html',
        current_user=current_user,
        viewed_user=viewed_user,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        total_pnl=round(total_pnl, 2),
        total_bets=len(bets),
        rank=rank
    )
