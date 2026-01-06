# ~/jobeni-sD/app/models.py
from app import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='jobseeker')
    full_name = db.Column(db.String(100))
    telegram_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # حقول الوكيل الذكي
    agent_enabled = db.Column(db.Boolean, default=False)
    agent_query = db.Column(db.String(100))
    last_agent_run = db.Column(db.DateTime)

    # العلاقات
    cvs = db.relationship('CV', backref='owner', lazy=True, cascade="all, delete-orphan")
    jobs = db.relationship('Job', backref='employer_ref', lazy=True)
    applications = db.relationship('Application', backref='applicant', lazy=True)
    interview_sessions = db.relationship('InterviewSession', backref='user', lazy=True, cascade="all, delete-orphan")
    interview_reports = db.relationship('InterviewReport', backref='user', lazy=True, cascade="all, delete-orphan")

    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='author', lazy=True, primaryjoin="User.id==Message.sender_id")
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True, primaryjoin="User.id==Message.recipient_id")

class InterviewReport(db.Model):
    __tablename__ = 'interview_report'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_title = db.Column(db.String(200))
    full_report = db.Column(db.Text)
    score = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    __tablename__ = 'job'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='عام')
    salary = db.Column(db.String(50))
    job_type = db.Column(db.String(50), default='دوام كامل')
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    applications = db.relationship('Application', backref='job', lazy=True, cascade="all, delete-orphan")             

class CV(db.Model):
    __tablename__ = 'cv'
    id = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String(200), nullable=False)
    extracted_text = db.Column(db.Text)
    profession = db.Column(db.String(100))
    skills = db.Column(db.JSON)
    feedback = db.Column(db.Text)
    score = db.Column(db.Integer, default=0)
    optimized_text = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # هذه العلاقة ضرورية لمنع خطأ 500 عند الحذف
    linked_applications = db.relationship('Application', backref='associated_cv', lazy=True, cascade="all, delete-orphan")

class Application(db.Model):
    __tablename__ = 'application'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    cv_id = db.Column(db.Integer, db.ForeignKey('cv.id'))
    match_score = db.Column(db.Integer, default=0)
    match_explanation = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)
    recipient_id = db.Column(db.Integer, nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=True)
    body = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class InterviewSession(db.Model):
    __tablename__ = 'interview_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    skill_name = db.Column(db.String(100), nullable=False)
    questions_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
