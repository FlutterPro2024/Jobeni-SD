# ~/jobeni-sD/app/models.py
from app import db
from flask_login import UserMixin
from datetime import datetime
from flask import url_for
import uuid

# جدول المتابعين (Many-to-Many Relationship)
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
    role = db.Column(db.String(20), default='jobseeker') # jobseeker, employer, scholarship_seeker
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(200))
    cover_photo = db.Column(db.String(200))
    headline = db.Column(db.String(200))
    bio = db.Column(db.Text)

    # الموقع الجغرافي
    location_name = db.Column(db.String(100))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    # بيانات التليجرام والواتساب
    telegram_id = db.Column(db.String(50))
    whatsapp_number = db.Column(db.String(20))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_typing_now = db.Column(db.DateTime, default=datetime.utcnow)

    # إعدادات الوكيل الذكي (The Autonomous Agent Goals)
    agent_enabled = db.Column(db.Boolean, default=False)      # هل الرادار مفعل؟
    agent_active = db.Column(db.Boolean, default=True)        # هل الوكيل يعمل حالياً؟
    agent_query = db.Column(db.String(200))                   # تخصص البحث
    agent_work_type = db.Column(db.String(20), default='both') # 'remote', 'onsite', 'both'
    agent_target_score = db.Column(db.Integer, default=75)     # الحد الأدنى للمطابقة
    agent_city_focus = db.Column(db.String(100), nullable=True) # التركيز الجغرافي
    last_agent_run = db.Column(db.DateTime)

    # حقول الشهادات والتوثيق
    last_evaluation = db.Column(db.Text)
    qr_code_key = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4())[:8])

    # العلاقات (Relationships)
    cvs = db.relationship('CV', backref='owner', lazy=True, cascade="all, delete-orphan")
    jobs = db.relationship('Job', back_populates='employer_user', lazy=True, foreign_keys='Job.user_id')
    applications = db.relationship('Application', backref='applicant', lazy=True)
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    agent_memories = db.relationship('AgentMemory', backref='user', lazy=True, cascade="all, delete-orphan")

    # علاقة الإشعارات
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic', foreign_keys='Notification.user_id')
    quiz_results = db.relationship('QuizResult', backref='user', lazy=True)

    # علاقة المتابعة
    followed = db.relationship('User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    def get_avatar(self):
        try:
            if self.avatar:
                if self.avatar.startswith('http'):
                    return self.avatar
                return url_for('static', filename='uploads/' + self.avatar)
        except Exception:
            pass
        return f"https://ui-avatars.com/api/?name={self.username}&background=random&color=fff"

    def get_cover(self):
        if self.cover_photo:
            if self.cover_photo.startswith('http'):
                return self.cover_photo
            return url_for('static', filename='uploads/' + self.cover_photo)
        return "https://via.placeholder.com/800x250/0d6efd/ffffff?text=Jobeni+SD"

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.commit()

class Scholarship(db.Model):
    """موديل المنح الدراسية المكتشفة بواسطة الرادار"""
    __tablename__ = 'scholarship'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    university = db.Column(db.String(200))
    country = db.Column(db.String(100))
    field_of_study = db.Column(db.String(200))
    level = db.Column(db.String(50)) # Bachelors, Masters, PhD
    funding_type = db.Column(db.String(50)) # Full, Partial
    deadline = db.Column(db.DateTime)
    official_link = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # علاقة الذاكرة (Memory Relationship)
    memories = db.relationship('AgentMemory', backref='scholarship_ref', lazy=True)

class AgentMemory(db.Model):
    """ذاكرة الوكيل الذكي: لتذكر التفضيلات والقرارات السابقة"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=True)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'), nullable=True) # ربط المنحة
    job_title = db.Column(db.String(200))
    action = db.Column(db.String(50)) # 'sent', 'ignored', 'scholarship_found', 'clicked'
    score = db.Column(db.Integer) # تعديل ليكون متناسق مع الكود في agent_worker
    feedback_notes = db.Column(db.Text)
    action_url = db.Column(db.String(500)) # لتخزين الرابط المباشر
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemConfig(db.Model):
    """إعدادات النظام (حل مشكلة الملفات في Vercel)"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.Text)
    extra_value = db.Column(db.String(50))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    body = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(300), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=True)

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
    questions = db.relationship('JobQuestion', backref='job', lazy=True, cascade="all, delete-orphan")

class JobQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=True)
    option_d = db.Column(db.String(200), nullable=True)
    correct_answer = db.Column(db.String(10), nullable=False)
    points = db.Column(db.Integer, default=10)

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    total_possible = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class CV(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    extracted_text = db.Column(db.Text)
    profession = db.Column(db.String(100))
    score = db.Column(db.Integer, default=0)
    skills = db.Column(db.JSON)
    radar_labels = db.Column(db.JSON)
    radar_scores = db.Column(db.JSON)
    course_recommendations = db.Column(db.Text)
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
    quiz_score = db.Column(db.Integer, nullable=True)

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
    image_file = db.Column(db.String(100), nullable=True)
    video_file = db.Column(db.String(100), nullable=True)
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
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'))
    replies = db.relationship(
        'Comment', backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic', cascade="all, delete-orphan"
    )
    user = db.relationship('User', backref='comments_ref')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # المستلم
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # من أحدث الفعل
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True) # المنشور المرتبط
    title = db.Column(db.String(100))
    message = db.Column(db.Text)
    link = db.Column(db.String(200))
    category = db.Column(db.String(20), default='info') # like, comment, follow, info
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='notifications_sent')
