from flask import Flask, session
from flask_wtf.csrf import CSRFProtect
from models import db, User
from routes.betting import betting_bp
from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.groups import groups_bp
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only')
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SSL_STRICT'] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
csrf=CSRFProtect(app)

db.init_app(app)

app.jinja_env.globals['enumerate'] = enumerate
app.jinja_env.globals['get_user'] = lambda uid: db.session.get(User, uid)

@app.context_processor
def inject_session_flags():
    return {'new_login': session.pop('new_login', False)}

app.register_blueprint(betting_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(groups_bp)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)