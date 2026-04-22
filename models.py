from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(50), unique = True, nullable = False)
    password_hash = db.Column(db.String(50), nullable = False)
    coins = db.Column(db.Integer, default = 1000)
    created_at = db.Column(db.DateTime, default = datetime.utcnow)

    is_admin = db.Column(db.Boolean, default = False)
    roll_number = db.Column(db.String(20), unique = True, nullable = False)

class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)

    prev_yes_odds = db.Column(db.Float, default = 0)
    prev_no_odds = db.Column(db.Float, default = 0)
    
    created_at = db.Column(db.DateTime, default = datetime.utcnow)

    status = db.Column(db.String(20), default="open")
    result = db.Column(db.String(3), nullable=True)

class Bet(db.Model):
    __tablename__ = "bets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"))

    side = db.Column(db.String(3))
    amount = db.Column(db.Integer)
    odds_at_time = db.Column(db.Float)

    timestamp = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'event_id', name='unique_user_event'),
    )

class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable = False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default = datetime.utcnow)

class GroupMembership(db.Model):
    __tablename__ = "group_memberships"

    id = db.Column(db.Integer, primary_key = True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False) #"invited" or "member"
    joined_at = db.Column(db.DateTime, default = datetime.utcnow)
    coins_at_join = db.Column(db.Integer, nullable=True)

class PendingInvite(db.Model): 
    __tablename__ = "pending_invites"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    roll_number = db.Column(db.String(20), nullable=False)
    invited_at = db.Column(db.DateTime, default = datetime.utcnow)

class GroupActivityLog(db.Model):
    __tablename__ = "group_activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    