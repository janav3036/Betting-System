from flask import Blueprint, render_template, request, redirect,url_for, session
from models import db, Bet, Event, User, PendingInvite, GroupMembership
import bcrypt

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods = ["GET","POST"])
def register():

    if request.method =='POST':
        username = request.form.get('username')
        password = request.form.get('password')
        roll_number = request.form.get('roll_number')

        enc_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        
        if User.query.filter_by(roll_number=roll_number).first():
            return render_template('register.html', error = "Roll number already registered")
        
        user = User(
            username = username,
            roll_number = roll_number,
            password_hash = enc_password.decode(),
            coins = 1000
        )

        db.session.add(user)
        db.session.commit()

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
    
    return render_template('register.html')

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
    bets = Bet.query.filter_by(user_id = user.id).all()

    bet_data = []
    total_pnl = 0
    wins = 0
    losses = 0
    
    for bet in bets:
        event = Event.query.get(bet.event_id)
        if event.status == 'Resolved':
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

    return render_template(
        'profile.html',
        current_user = user,
        bet_data = bet_data,
        wins = wins,
        losses = losses,
        win_rate = win_rate,
        total_pnl = round(total_pnl,2)
    )
    
