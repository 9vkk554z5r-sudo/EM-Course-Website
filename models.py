# -*- coding: utf-8 -*-
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, date

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    subscriptions = db.relationship("LiteratureSubscription", backref="user", lazy="dynamic")
    checkins = db.relationship("DailyCheckin", backref="user", lazy="dynamic")
    uploads = db.relationship("UploadedLiterature", backref="uploader", lazy="dynamic")
    rewards = db.relationship("AttendanceReward", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class ProtocolVideo(db.Model):
    __tablename__ = "protocol_videos"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(100), default="general")
    video_url = db.Column(db.String(500), default="")
    video_path = db.Column(db.String(500), default="")
    thumbnail = db.Column(db.String(500), default="")
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    difficulty = db.Column(db.String(20), default="intermediate")
    duration_minutes = db.Column(db.Integer, default=0)

    uploader = db.relationship("User", backref="uploaded_videos", lazy=True, foreign_keys=[uploaded_by])


class UploadedLiterature(db.Model):
    __tablename__ = "uploaded_literatures"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(500), default="")
    authors = db.Column(db.String(500), default="")
    journal = db.Column(db.String(300), default="")
    year = db.Column(db.Integer)
    doi = db.Column(db.String(200), default="")
    url = db.Column(db.String(500), default="")
    abstract = db.Column(db.Text, default="")
    citation_count = db.Column(db.Integer, default=0)
    keywords = db.Column(db.String(500), default="")
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default="pending")  # pending, processing, completed


class LiteratureItem(db.Model):
    __tablename__ = "literature_items"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    authors = db.Column(db.String(500), default="")
    journal = db.Column(db.String(300), default="")
    year = db.Column(db.Integer)
    doi = db.Column(db.String(200), unique=True)
    abstract = db.Column(db.Text, default="")
    url = db.Column(db.String(500), default="")
    topic = db.Column(db.String(200), default="")
    fetched_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    citation_count = db.Column(db.Integer, default=0)


class CitationLink(db.Model):
    __tablename__ = "citation_links"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("literature_items.id"), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey("literature_items.id"), nullable=False)
    relationship = db.Column(db.String(100), default="cites")
    weight = db.Column(db.Float, default=1.0)

    source = db.relationship("LiteratureItem", foreign_keys=[source_id], backref="cited_by")
    target = db.relationship("LiteratureItem", foreign_keys=[target_id], backref="cites")


class LiteratureSubscription(db.Model):
    __tablename__ = "literature_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic = db.Column(db.String(200), nullable=False)
    keywords = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    active = db.Column(db.Boolean, default=True)


class KnowledgePoint(db.Model):
    __tablename__ = "knowledge_points"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(100), default="general")
    day_of_week = db.Column(db.Integer)
    source = db.Column(db.String(50), default="system")  # system or admin
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DailyCheckin(db.Model):
    __tablename__ = "daily_checkins"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    knowledge_point_id = db.Column(db.Integer, db.ForeignKey("knowledge_points.id"), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    date = db.Column(db.Date, nullable=False)

    knowledge_point = db.relationship("KnowledgePoint")

    __table_args__ = (db.UniqueConstraint("user_id", "date", name="unique_daily_checkin"),)



class Quiz(db.Model):
    __tablename__ = "quizzes"
    id = db.Column(db.Integer, primary_key=True)
    knowledge_point_id = db.Column(db.Integer, db.ForeignKey("knowledge_points.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)  # JSON: [{"label":"A","text":"..."}, ...]
    correct_answer = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    knowledge_point = db.relationship("KnowledgePoint", backref="quizzes")


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    checkin_id = db.Column(db.Integer, db.ForeignKey("daily_checkins.id"), nullable=True)
    answer = db.Column(db.String(10), nullable=False)
    correct = db.Column(db.Boolean, nullable=False)
    attempted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="quiz_attempts")
    quiz = db.relationship("Quiz", backref="attempts")


class ProtocolCollection(db.Model):
    __tablename__ = "protocol_collections"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    paper_title = db.Column(db.String(500), default="")
    paper_doi = db.Column(db.String(200), default="")
    methods_summary = db.Column(db.Text, default="")
    protocol_links = db.Column(db.Text, default="")  # JSON list
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="protocols")


class PresentationTemplate(db.Model):
    __tablename__ = "presentation_templates"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    criteria = db.Column(db.Text, default="")  # JSON grading criteria
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    uploader = db.relationship("User", backref="uploaded_templates")


class AgentLog(db.Model):
    __tablename__ = "agent_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    skill = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    input_data = db.Column(db.Text, default="")
    output_data = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="success")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))



class ApiKey(db.Model):
    __tablename__ = "api_keys"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    provider = db.Column(db.String(50), default="openai")
    key_name = db.Column(db.String(100), default="default")
    encrypted_key = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="api_keys")


class LiteraturePlanet(db.Model):
    __tablename__ = "literature_planets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(200), default="")
    description = db.Column(db.Text, default="")
    color = db.Column(db.String(20), default="#3b82f6")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="planets")
    papers = db.relationship("PlanetPaper", backref="planet", lazy="dynamic", cascade="all, delete-orphan")


class PlanetPaper(db.Model):
    __tablename__ = "planet_papers"
    id = db.Column(db.Integer, primary_key=True)
    planet_id = db.Column(db.Integer, db.ForeignKey("literature_planets.id"), nullable=False)
    title = db.Column(db.String(500), default="")
    authors = db.Column(db.String(500), default="")
    journal = db.Column(db.String(300), default="")
    year = db.Column(db.Integer)
    doi = db.Column(db.String(200), default="")
    url = db.Column(db.String(500), default="")
    abstract = db.Column(db.Text, default="")
    user_notes = db.Column(db.Text, default="")
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class AttendanceReward(db.Model):
    __tablename__ = "attendance_rewards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    period = db.Column(db.String(10), nullable=False)  # weekly, monthly
    period_key = db.Column(db.String(20), nullable=False)  # e.g. "2026-W26" or "2026-06"
    checkin_days = db.Column(db.Integer, default=0)
    total_days = db.Column(db.Integer, default=0)
    reward_type = db.Column(db.String(50), default="tree")
    reward_data = db.Column(db.Text, default="{}")
    earned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", "period", "period_key", name="unique_reward"),)


class ChatHistory(db.Model):
    __tablename__ = "chat_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user or assistant
    message = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(100), default="general")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="chat_history")


class LiteratureCategory(db.Model):
    __tablename__ = "literature_categories"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("literature_categories.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="lit_categories", foreign_keys=[user_id])
    parent = db.relationship("LiteratureCategory", remote_side=[id], backref="children")


class BookmarkedLiterature(db.Model):
    __tablename__ = "bookmarked_literature"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("literature_categories.id"), nullable=True)
    title = db.Column(db.String(500), default="")
    authors = db.Column(db.String(500), default="")
    journal = db.Column(db.String(300), default="")
    year = db.Column(db.Integer)
    doi = db.Column(db.String(200), default="")
    url = db.Column(db.String(500), default="")
    abstract = db.Column(db.Text, default="")
    citation_count = db.Column(db.Integer, default=0)
    source = db.Column(db.String(50), default="")  # search, weekly, planet, citation
    notes = db.Column(db.Text, default="")
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="bookmarked_literature")
    category = db.relationship("LiteratureCategory", backref="papers")


class UserStudyPlan(db.Model):
    __tablename__ = "user_study_plans"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic = db.Column(db.String(200), default="general")
    daily_count = db.Column(db.Integer, default=3)
    difficulty = db.Column(db.String(20), default="beginner")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="study_plans")
