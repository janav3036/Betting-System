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

class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key = True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default = 'open') 
    result = db.Column(db.String(10), nullable = True)
    created_at = db.Column(db.DateTime, default = datetime.utcnow)

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