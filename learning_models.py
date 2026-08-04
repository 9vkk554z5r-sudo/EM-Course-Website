# -*- coding: utf-8 -*-
"""Database models scoped to Knowledge Forest -> Today Study."""

from datetime import date, datetime, timezone

from models import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DailyLearningSession(db.Model):
    __tablename__ = "daily_learning_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    course_slug = db.Column(db.String(80), nullable=False, index=True)
    study_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    status = db.Column(db.String(20), nullable=False, default="not_started")
    base_target = db.Column(db.Integer, nullable=False, default=10)
    base_completed_count = db.Column(db.Integer, nullable=False, default=0)
    actual_review_count = db.Column(db.Integer, nullable=False, default=0)
    continue_active = db.Column(db.Boolean, nullable=False, default=False)
    elapsed_seconds = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime)
    base_completed_at = db.Column(db.DateTime)
    requested_target = db.Column(db.Integer, nullable=False, default=0)
    study_mode = db.Column(db.String(20), nullable=False, default="mixed")
    difficulty_filter = db.Column(db.String(20), nullable=False, default="all")
    content_filter = db.Column(db.String(200), nullable=False, default="")
    library_id = db.Column(db.Integer, db.ForeignKey('uploaded_literatures.id'), nullable=True, default=None)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "course_slug", "study_date", name="unique_daily_learning_session"),
    )


class DailyLearningTask(db.Model):
    """One distinct knowledge point assigned on a study date."""
    __tablename__ = "daily_learning_tasks"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("daily_learning_sessions.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_items.id"), nullable=False, index=True)
    is_base = db.Column(db.Boolean, nullable=False, default=True)
    source_type = db.Column(db.String(24), nullable=False, default="new")
    assigned_order = db.Column(db.Integer, nullable=False, default=0)
    first_completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    session = db.relationship("DailyLearningSession", backref="tasks")
    item = db.relationship("UserKnowledgeItem", backref="learning_tasks")

    __table_args__ = (
        db.UniqueConstraint("session_id", "item_id", name="unique_session_learning_item"),
    )


class DailyLearningQueueEntry(db.Model):
    """One persisted appearance of a knowledge point in the current queue."""
    __tablename__ = "daily_learning_queue_entries"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("daily_learning_sessions.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("daily_learning_tasks.id"), nullable=False, index=True)
    queue_order = db.Column(db.Integer, nullable=False, default=0, index=True)
    state = db.Column(db.String(20), nullable=False, default="pending")
    reason = db.Column(db.String(30), nullable=False, default="base")
    rating = db.Column(db.String(20), default="")
    shown_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    answered_at = db.Column(db.DateTime)
    submitted_answer = db.Column(db.Text, default="")
    answer_score = db.Column(db.Integer, default=0)
    answer_correct = db.Column(db.Boolean, default=False)

    session = db.relationship("DailyLearningSession", backref="queue_entries")
    task = db.relationship("DailyLearningTask", backref="queue_entries")


class KnowledgeMemoryState(db.Model):
    """Long-term schedule and mastery state for one user and knowledge item."""
    __tablename__ = "knowledge_memory_states"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_items.id"), nullable=False, index=True)
    course_slug = db.Column(db.String(80), nullable=False, index=True)
    state = db.Column(db.String(20), nullable=False, default="new")
    mastery_score = db.Column(db.Integer, nullable=False, default=0)
    correct_streak = db.Column(db.Integer, nullable=False, default=0)
    interval_stage = db.Column(db.Integer, nullable=False, default=0)
    interval_days = db.Column(db.Integer, nullable=False, default=0)
    next_review_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    is_weak = db.Column(db.Boolean, nullable=False, default=False)
    last_rating = db.Column(db.String(20), default="")
    total_reviews = db.Column(db.Integer, nullable=False, default=0)
    lapse_count = db.Column(db.Integer, nullable=False, default=0)
    last_reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    answered_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    item = db.relationship("UserKnowledgeItem", backref="memory_states")

    __table_args__ = (
        db.UniqueConstraint("user_id", "item_id", name="unique_user_item_memory_state"),
    )


class LearningReviewEvent(db.Model):
    __tablename__ = "learning_review_events"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("daily_learning_sessions.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("user_knowledge_items.id"), nullable=False, index=True)
    queue_entry_id = db.Column(db.Integer, db.ForeignKey("daily_learning_queue_entries.id"), nullable=False)
    rating = db.Column(db.String(20), nullable=False)
    previous_mastery = db.Column(db.Integer, nullable=False, default=0)
    mastery_after = db.Column(db.Integer, nullable=False, default=0)
    previous_interval = db.Column(db.Integer, nullable=False, default=0)
    next_interval = db.Column(db.Integer, nullable=False, default=0)
    is_repeat = db.Column(db.Boolean, nullable=False, default=False)
    reviewed_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    session = db.relationship("DailyLearningSession", backref="review_events")
    item = db.relationship("UserKnowledgeItem", backref="learning_review_events")
    queue_entry = db.relationship("DailyLearningQueueEntry", backref="review_event", uselist=False)
