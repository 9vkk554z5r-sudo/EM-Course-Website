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
    openalex_id = db.Column(db.String(50), unique=True, index=True, nullable=True)
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

    __table_args__ = (
        db.UniqueConstraint("source_id", "target_id", name="unique_citation_edge"),
    )


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
    correction_count = db.Column(db.Integer, default=0)
    last_corrected_at = db.Column(db.DateTime, nullable=True)
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
    category = db.Column(db.String(100), default='general')
    flowchart_steps = db.Column(db.Text, default='')  # JSON list
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
    endpoint = db.Column(db.String(500), default="")
    model_name = db.Column(db.String(100), default="")
    deployment = db.Column(db.String(200), default="")
    api_style = db.Column(db.String(30), default="auto")
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


class UserKnowledgeLibrary(db.Model):
    __tablename__ = "user_knowledge_libraries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    source_filename = db.Column(db.String(255), default="")
    daily_new_count = db.Column(db.Integer, default=5)
    review_limit = db.Column(db.Integer, default=50)
    study_mode = db.Column(db.String(20), default="mixed", nullable=False)
    difficulty_filter = db.Column(db.String(20), default="all", nullable=False)
    content_filter = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref="knowledge_libraries")
    items = db.relationship("UserKnowledgeItem", backref="library", lazy="dynamic", cascade="all, delete-orphan")


class UserKnowledgeItem(db.Model):
    __tablename__ = "user_knowledge_items"

    id = db.Column(db.Integer, primary_key=True)
    library_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_libraries.id"), nullable=False, index=True)
    title = db.Column(db.String(240), nullable=False)
    content = db.Column(db.Text, nullable=False)
    hint = db.Column(db.Text, default="")
    tags = db.Column(db.String(500), default="")
    difficulty = db.Column(db.String(20), default="intermediate")
    position = db.Column(db.Integer, default=0)
    source_ref = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class KnowledgeReviewProgress(db.Model):
    __tablename__ = "knowledge_review_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_items.id"), nullable=False, index=True)
    state = db.Column(db.String(20), default="new", nullable=False)
    repetitions = db.Column(db.Integer, default=0)
    interval_days = db.Column(db.Integer, default=0)
    ease_factor = db.Column(db.Float, default=2.3)
    next_review_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    last_reviewed_at = db.Column(db.DateTime)
    lapses = db.Column(db.Integer, default=0)
    total_reviews = db.Column(db.Integer, default=0)
    last_rating = db.Column(db.String(20), default="")

    item = db.relationship("UserKnowledgeItem", backref="review_progress")
    user = db.relationship("User", backref="knowledge_review_progress")

    __table_args__ = (db.UniqueConstraint("user_id", "item_id", name="unique_user_knowledge_progress"),)


class DailyKnowledgeTask(db.Model):
    __tablename__ = "daily_knowledge_tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_items.id"), nullable=False, index=True)
    study_date = db.Column(db.Date, nullable=False, index=True)
    position = db.Column(db.Integer, default=0)
    queue_type = db.Column(db.String(20), default="new")
    state = db.Column(db.String(20), default="pending", nullable=False)
    attempts = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    item = db.relationship("UserKnowledgeItem", backref="daily_tasks")

    __table_args__ = (db.UniqueConstraint("user_id", "item_id", "study_date", name="unique_daily_knowledge_task"),)


class KnowledgeReviewLog(db.Model):
    __tablename__ = "knowledge_review_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_items.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("daily_knowledge_tasks.id"), nullable=True)
    rating = db.Column(db.String(20), nullable=False)
    previous_interval = db.Column(db.Integer, default=0)
    next_interval = db.Column(db.Integer, default=0)
    reviewed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    item = db.relationship("UserKnowledgeItem", backref="review_logs")
    task = db.relationship("DailyKnowledgeTask", backref="review_logs")


class KnowledgeFile(db.Model):
    __tablename__ = "knowledge_files"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="knowledge_files")


class ReadingListFile(db.Model):
    __tablename__ = "reading_list_files"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    theme = db.Column(db.String(200), default="")
    file_type = db.Column(db.String(20), default="txt")
    week_order = db.Column(db.Integer, default=0, nullable=False, index=True)
    is_open = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = db.relationship("User", backref="reading_list_files", foreign_keys=[uploaded_by])
    items = db.relationship(
        "ReadingListItem",
        backref="reading_list",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ReadingListItem.item_order",
    )


class ReadingListItem(db.Model):
    __tablename__ = "reading_list_items"

    id = db.Column(db.Integer, primary_key=True)
    reading_list_id = db.Column(
        db.Integer, db.ForeignKey("reading_list_files.id"), nullable=False, index=True
    )
    title = db.Column(db.String(600), nullable=False)
    authors = db.Column(db.String(500), default="")
    journal = db.Column(db.String(300), default="")
    year = db.Column(db.Integer)
    doi = db.Column(db.String(200), default="")
    url = db.Column(db.String(500), default="")
    item_order = db.Column(db.Integer, default=0, index=True)

    selections = db.relationship(
        "ReadingSelection",
        backref="item",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("ix_reading_item_list_order", "reading_list_id", "item_order"),
    )


class ReadingSelection(db.Model):
    __tablename__ = "reading_selections"

    id = db.Column(db.Integer, primary_key=True)
    reading_list_item_id = db.Column(
        db.Integer, db.ForeignKey("reading_list_items.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    week_label = db.Column(db.String(20), nullable=False, index=True)
    selected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ppt_filename = db.Column(db.String(255), default="")
    ppt_path = db.Column(db.String(500), default="")
    ppt_uploaded_at = db.Column(db.DateTime)
    teacher_feedback = db.Column(db.Text, default="")
    teacher_feedback_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="reading_selections")
    scores = db.relationship(
        "ReadingScore",
        backref="selection",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("reading_list_item_id", "week_label", name="uq_reading_item_week"),
        db.UniqueConstraint("user_id", "week_label", name="uq_reading_user_week"),
    )


class ReadingScore(db.Model):
    __tablename__ = "reading_scores"

    id = db.Column(db.Integer, primary_key=True)
    selection_id = db.Column(
        db.Integer, db.ForeignKey("reading_selections.id"), nullable=False, index=True
    )
    rater_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content_understanding = db.Column(db.Integer, nullable=False)
    preparation_attitude = db.Column(db.Integer, nullable=False)
    clarity_focus = db.Column(db.Integer, nullable=False)
    inspiration_creativity = db.Column(db.Integer, nullable=False)
    audience_engagement = db.Column(db.Integer, nullable=False)
    question_answering = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    rater = db.relationship("User", backref="reading_scores")

    __table_args__ = (
        db.UniqueConstraint("selection_id", "rater_id", name="uq_reading_score_rater"),
    )


class FinalReview(db.Model):
    __tablename__ = "final_reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    score = db.Column(db.Integer)
    feedback = db.Column(db.Text, default="")
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="final_reviews")

    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_final_review_user"),
    )

