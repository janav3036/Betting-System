from flask import Blueprint, render_template, request, redirect,url_for, session
from models import db, Bet, Event, User
import bcrypt

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods = ["POST", "GET"])
def register():
    if request =='POST':
        username = request.form.get('username')
        password = request.form.get('password')

        enc_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        user = User(
            username = username,
            password_hash = enc_password.decode(),
            coins = 1000
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("auth.login"))
    
    return render_template('register.html')

@auth_bp.route('/login', methods = ["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()


        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            session['user_id'] = user.id
            return redirect(url_for('betting.dashboard'))
        
    return render_template('login.html')

@auth_bp.route('/login')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
