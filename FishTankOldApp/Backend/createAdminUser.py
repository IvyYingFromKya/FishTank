from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    hashed_pw = generate_password_hash('admin')
    admin = User(username='admin', password_hash=hashed_pw)
    db.session.add(admin)
    db.session.commit()
    print("Admin user created.")
