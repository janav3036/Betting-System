from flask import Flask
from models import db
from routes.betting import betting_bp
from routes.admin import admin_bp
from routes.auth import auth_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

db.init_app(app)

app.register_blueprint(betting_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)