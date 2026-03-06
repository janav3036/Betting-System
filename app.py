from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Event, Bet

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

db.init_app(app)

@app.route("/")
def dashboard():
    events = Event.query.all()
    return render_template('dashboard.html', events = events)

if __name__ == "___main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)