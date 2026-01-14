# ~/jobeni-sD/app/models.py
from app import db
from flask_login import UserMixin
from datetime import datetime

# جدول المتابعين (Many-to-Many)
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='jobseeker')
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(200), default='https://ui-avatars.com/api/?name=User')
    headline = db.Column(db.String(200))
    bio = db.Column(db.Text)
    location_name = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    telegram_id = db.Column(db.String(50))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_typing_now = db.Column(db.DateTime, default=datetime.utcnow)
    agent_enabled = db.Column(db.Boolean, default=False)
    agent_query = db.Column(db.String(200))
    last_agent_run = db.Column(db.DateTime)

    # العلاقات (Relationships)
    cvs = db.relationship('CV', backref='owner', lazy=True, cascade="all, delete-orphan")
    jobs = db.relationship('Job', back_populates='employer_user', lazy=True, foreign_keys='Job.user_id')
    applications = db.relationship('Application', backref='applicant', lazy=True)
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic')
    followed = db.relationship('User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.commit()

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    body = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class Job(db.Model):
    __tablename__ = 'job'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    salary = db.Column(db.String(50))
    job_type = db.Column(db.String(50))
    category = db.Column(db.String(50), default='عام')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    employer_user = db.relationship('User', back_populates='jobs')
    applications = db.relationship('Application', backref='job_ref', lazy=True, cascade="all, delete-orphan")

class CV(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    extracted_text = db.Column(db.Text)
    profession = db.Column(db.String(100))
    score = db.Column(db.Integer, default=0)
    skills = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    status = db.Column(db.String(20), default='pending')
    match_score = db.Column(db.Integer)
    match_explanation = db.Column(db.Text)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

class InterviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    skill_name = db.Column(db.String(100))
    questions_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InterviewReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    job_title = db.Column(db.String(100))
    score = db.Column(db.String(20))
    full_report = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    likes = db.relationship('PostLike', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade="all, delete-orphan")

class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    user = db.relationship('User', backref='comments_ref')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(100))
    message = db.Column(db.Text)
    link = db.Column(db.String(200))
    category = db.Column(db.String(20), default='info')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
