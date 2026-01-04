# ~/jobeni-sD/setup_admin.py
from app import create_app, db
from app.models import User

app = create_app('development')

def make_admin(email):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            user.role = 'admin'
            db.session.commit()
            print(f"✅ SUCCESS: {email} is now an Admin!")
        else:
            print(f"❌ ERROR: User with email {email} not found.")

if __name__ == '__main__':
    email_to_promote = input("Enter user email to promote to admin: ")
    make_admin(email_to_promote)
