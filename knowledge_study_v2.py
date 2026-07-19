# -*- coding: utf-8 -*-
"""Knowledge Forest daily learning orchestration.

This module is intentionally scoped to Today Study. It keeps the generated
daily task, the appearance queue, review history, timer, and completion state
in the database so refreshes and new logins resume the exact same session.
"""

import csv
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, flash, jsonify, redirect, request, session as flask_session, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from knowledge_study import parse_library_upload
from learning_models import (
    DailyLearningQueueEntry,
    DailyLearningSession,
    DailyLearningTask,
    KnowledgeMemoryState,
    LearningReviewEvent,
)
from models import (
    db,
    DailyCheckin,
    KnowledgePoint,
    KnowledgeReviewProgress,
    UserKnowledgeItem,
    UserKnowledgeLibrary,
)
from spaced_repetition import VALID_RATINGS, schedule_review


knowledge_study_bp = Blueprint("knowledge_study", __name__)
BASE_DAILY_TARGET = 10
MAX_DAILY_TARGET = 50
VALID_STUDY_MODES = {"mixed", "new", "review", "advanced"}
VALID_DIFFICULTIES = {"all", "beginner", "intermediate", "advanced"}
COURSE_NAMES = {
    "electron-microscopy": "冷冻电子显微学",
    "structural-biology": "结构生物学",
    "cell-biology": "细胞生物学",
    "bioinformatics": "生物信息学",
    "neuroscience": "神经科学",
}
RATING_LABELS = {
    "again": "忘记了",
    "hard": "有点模糊",
    "good": "基本掌握",
    "easy": "非常熟悉",
}


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clamp_int(value, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _current_course(course=None):
    if course:
        return course.get("slug", "electron-microscopy"), course.get("name") or course.get("name_en")
    slug = flask_session.get("selected_course") or "electron-microscopy"
    return slug, COURSE_NAMES.get(slug, slug)


def _owned_library(library_id, include_archived=False):
    query = UserKnowledgeLibrary.query.filter_by(id=library_id, user_id=current_user.id)
    if not include_archived:
        query = query.filter_by(is_archived=False)
    return query.first_or_404()


def _is_course_library(library):
    return bool(library and (library.source_filename or "").startswith("__course__:"))


def _available_libraries(user_id, course_slug, course_name):
    course_library = _ensure_course_library(user_id, course_slug, course_name)
    libraries = UserKnowledgeLibrary.query.filter_by(user_id=user_id, is_archived=False).all()
    libraries.sort(key=lambda library: (
        not library.is_active,
        not _is_course_library(library),
        -(library.updated_at.timestamp() if library.updated_at else 0),
    ))
    return libraries, course_library


def _active_library(user_id, course_slug, course_name, requested_id=None):
    libraries, course_library = _available_libraries(user_id, course_slug, course_name)
    if requested_id:
        requested = next((library for library in libraries if library.id == requested_id), None)
        if requested:
            return requested
    return next((library for library in libraries if library.is_active), course_library)


def _ensure_course_library(user_id, course_slug, course_name):
    marker = f"__course__:{course_slug}"
    library = UserKnowledgeLibrary.query.filter_by(user_id=user_id, source_filename=marker).first()
    if not library:
        has_active = UserKnowledgeLibrary.query.filter_by(
            user_id=user_id, is_archived=False, is_active=True
        ).first()
        library = UserKnowledgeLibrary(
            user_id=user_id,
            name=f"{course_name}课程知识库",
            description="由当前课程知识点自动同步",
            source_filename=marker,
            daily_new_count=BASE_DAILY_TARGET,
            review_limit=200,
            is_active=has_active is None,
        )
        db.session.add(library)
        db.session.flush()

    existing_refs = {
        row[0]
        for row in db.session.query(UserKnowledgeItem.source_ref)
        .filter(UserKnowledgeItem.library_id == library.id)
        .all()
    }
    points = KnowledgePoint.query.order_by(KnowledgePoint.id.asc()).all()
    next_position = db.session.query(func.max(UserKnowledgeItem.position)).filter_by(library_id=library.id).scalar() or 0
    for point in points:
        source_ref = f"system:{point.id}"
        if source_ref in existing_refs:
            continue
        next_position += 1
        db.session.add(UserKnowledgeItem(
            library_id=library.id,
            title=point.title,
            content=point.content,
            hint=f"课程分类：{point.category}" if point.category else "先回忆核心概念和适用场景",
            tags=point.category or "生命科学",
            difficulty=point.difficulty,
            position=next_position,
            source_ref=source_ref,
        ))
    db.session.flush()
    if not UserKnowledgeLibrary.query.filter_by(
        user_id=user_id, is_archived=False, is_active=True
    ).first():
        library.is_active = True
        db.session.flush()
    return library


def _learning_pool(
    user_id,
    course_slug,
    course_name,
    requested_library_id=None,
    study_mode_override=None,
    difficulty_override=None,
):
    active_library = _active_library(user_id, course_slug, course_name, requested_library_id)
    query = UserKnowledgeItem.query.filter_by(library_id=active_library.id, is_active=True)
    effective_mode = study_mode_override or active_library.study_mode or "mixed"
    difficulty = difficulty_override or active_library.difficulty_filter or "all"
    if effective_mode == "advanced":
        difficulty = "advanced"
    if difficulty in VALID_DIFFICULTIES - {"all"}:
        query = query.filter_by(difficulty=difficulty)
    items = query.order_by(UserKnowledgeItem.position.asc(), UserKnowledgeItem.id.asc()).all()
    content_filter = (active_library.content_filter or "").strip().lower()
    if content_filter:
        keywords = [word for word in re.split(r"[\s,，;；]+", content_filter) if word]
        items = [
            item for item in items
            if any(word in " ".join((item.title or "", item.content or "", item.tags or "")).lower() for word in keywords)
        ]
    return items, active_library


def _get_or_create_memory(user_id, item_id, course_slug):
    state = KnowledgeMemoryState.query.filter_by(user_id=user_id, item_id=item_id).first()
    if state:
        return state
    legacy = KnowledgeReviewProgress.query.filter_by(user_id=user_id, item_id=item_id).first()
    state = KnowledgeMemoryState(
        user_id=user_id,
        item_id=item_id,
        course_slug=course_slug,
        state=legacy.state if legacy else "new",
        mastery_score=min(100, (legacy.repetitions or 0) * 15) if legacy else 0,
        correct_streak=legacy.repetitions or 0 if legacy else 0,
        interval_days=legacy.interval_days or 0 if legacy else 0,
        next_review_date=legacy.next_review_date if legacy else date.today(),
        is_weak=bool(legacy and legacy.last_rating in {"again", "hard"}),
        last_rating=legacy.last_rating or "" if legacy else "",
        total_reviews=legacy.total_reviews or 0 if legacy else 0,
        lapse_count=legacy.lapses or 0 if legacy else 0,
        last_reviewed_at=legacy.last_reviewed_at if legacy else None,
    )
    db.session.add(state)
    db.session.flush()
    return state


def _memory_map(user_id, items):
    item_ids = [item.id for item in items]
    if not item_ids:
        return {}
    return {
        state.item_id: state
        for state in KnowledgeMemoryState.query.filter(
            KnowledgeMemoryState.user_id == user_id,
            KnowledgeMemoryState.item_id.in_(item_ids),
        ).all()
    }


def _candidate_buckets(items, states):
    today = date.today()
    risk_cutoff = _utcnow() - timedelta(days=7)
    due_today, overdue, forgotten, fuzzy, risk, new_items, stable = [], [], [], [], [], [], []
    for item in items:
        state = states.get(item.id)
        if not state or not state.total_reviews:
            new_items.append(item)
            continue
        if state.next_review_date == today:
            due_today.append(item)
        elif state.next_review_date < today:
            overdue.append(item)
        elif state.last_rating == "again":
            forgotten.append(item)
        elif state.last_rating == "hard" or state.is_weak:
            fuzzy.append(item)
        elif (state.last_reviewed_at and state.last_reviewed_at <= risk_cutoff) or state.mastery_score < 45:
            risk.append(item)
        else:
            stable.append(item)

    def state_key(item):
        state = states[item.id]
        return (state.next_review_date, state.mastery_score, state.last_reviewed_at or datetime.min)

    due_today.sort(key=state_key)
    overdue.sort(key=state_key)
    forgotten.sort(key=lambda item: states[item.id].last_reviewed_at or datetime.min, reverse=True)
    fuzzy.sort(key=lambda item: (states[item.id].mastery_score, states[item.id].last_reviewed_at or datetime.min))
    risk.sort(key=lambda item: (states[item.id].mastery_score, states[item.id].last_reviewed_at or datetime.min))
    stable.sort(key=lambda item: (states[item.id].last_reviewed_at or datetime.min, states[item.id].mastery_score))
    return [
        ("due", due_today),
        ("overdue", overdue),
        ("weak", forgotten),
        ("weak", fuzzy),
        ("risk", risk),
        ("new", new_items),
        ("risk", stable),
    ]


def _select_distinct_items(items, states, target, study_mode="mixed"):
    selected, selected_ids = [], set()
    buckets = _candidate_buckets(items, states)
    if study_mode == "new":
        buckets = [(source_type, bucket) for source_type, bucket in buckets if source_type == "new"]
    elif study_mode == "review":
        buckets = [(source_type, bucket) for source_type, bucket in buckets if source_type != "new"]
    for source_type, bucket in buckets:
        for item in bucket:
            if item.id in selected_ids:
                continue
            selected.append((item, source_type))
            selected_ids.add(item.id)
            if len(selected) >= target:
                return selected
    return selected


def _create_daily_session(user_id, course_slug, course_name, requested_library_id=None):
    items, library = _learning_pool(user_id, course_slug, course_name, requested_library_id)
    states = _memory_map(user_id, items)
    requested_target = _clamp_int(library.daily_new_count, BASE_DAILY_TARGET, 1, MAX_DAILY_TARGET)
    study_mode = library.study_mode if library.study_mode in VALID_STUDY_MODES else "mixed"
    selected = _select_distinct_items(items, states, requested_target, study_mode)
    session = DailyLearningSession(
        user_id=user_id,
        library_id=library.id,
        course_slug=course_slug,
        study_date=date.today(),
        status="not_started",
        base_target=len(selected),
        requested_target=requested_target,
        study_mode=study_mode,
        difficulty_filter=library.difficulty_filter if library.difficulty_filter in VALID_DIFFICULTIES else "all",
        content_filter=(library.content_filter or "")[:200],
    )
    db.session.add(session)
    db.session.flush()
    for order, (item, source_type) in enumerate(selected, start=1):
        _get_or_create_memory(user_id, item.id, course_slug)
        task = DailyLearningTask(
            session_id=session.id,
            item_id=item.id,
            is_base=True,
            source_type=source_type,
            assigned_order=order,
        )
        db.session.add(task)
        db.session.flush()
        db.session.add(DailyLearningQueueEntry(
            session_id=session.id,
            task_id=task.id,
            queue_order=order,
            reason="base",
        ))
    db.session.commit()
    return session


def _discard_unstarted_session(user_id, course_slug):
    session = DailyLearningSession.query.filter_by(
        user_id=user_id,
        course_slug=course_slug,
        study_date=date.today(),
        status="not_started",
    ).first()
    if not session:
        return False
    LearningReviewEvent.query.filter_by(session_id=session.id).delete(synchronize_session=False)
    DailyLearningQueueEntry.query.filter_by(session_id=session.id).delete(synchronize_session=False)
    DailyLearningTask.query.filter_by(session_id=session.id).delete(synchronize_session=False)
    db.session.delete(session)
    db.session.flush()
    return True


def _rebuild_unstarted_session(requested_library_id=None):
    course_slug, course_name = _current_course()
    rebuilt = _discard_unstarted_session(current_user.id, course_slug)
    if rebuilt:
        _create_daily_session(current_user.id, course_slug, course_name, requested_library_id)
    return rebuilt


def _get_or_create_session(user_id, course_slug, course_name, requested_library_id=None):
    session = DailyLearningSession.query.filter_by(
        user_id=user_id,
        course_slug=course_slug,
        study_date=date.today(),
    ).first()
    if session:
        return session
    return _create_daily_session(user_id, course_slug, course_name, requested_library_id)


def _pending_entries(session):
    return DailyLearningQueueEntry.query.filter_by(session_id=session.id, state="pending").order_by(
        DailyLearningQueueEntry.queue_order.asc(), DailyLearningQueueEntry.id.asc()
    ).all()


def _format_duration(seconds):
    seconds = max(0, int(seconds or 0))
    minutes, remainder = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分{remainder:02d}秒"


def _answer_parts(item):
    text = (item.content or "").strip()
    first = text.split("。", 1)[0].strip()
    if first and first != text:
        first += "。"
    return first or text, text


def build_custom_study_context(course=None):
    course_slug, course_name = _current_course(course)
    requested_library_id = request.args.get("library", type=int)
    session = _get_or_create_session(current_user.id, course_slug, course_name, requested_library_id)
    pending = _pending_entries(session)
    if session.status == "completed" and session.continue_active and not pending:
        session.continue_active = False
        db.session.commit()

    is_learning = session.status == "in_progress" or (session.status == "completed" and session.continue_active)
    current_entry = pending[0] if is_learning and pending else None
    base_tasks = DailyLearningTask.query.filter_by(session_id=session.id, is_base=True).order_by(DailyLearningTask.assigned_order).all()
    if not session.library_id and base_tasks:
        session.library_id = base_tasks[0].item.library_id
        session.requested_target = session.base_target
        db.session.commit()
    completed_base = sum(task.first_completed_at is not None for task in base_tasks)
    source_counts = {
        "review": sum(task.source_type in {"due", "overdue", "risk"} for task in base_tasks),
        "weak": sum(task.source_type == "weak" for task in base_tasks),
        "new": sum(task.source_type == "new" for task in base_tasks),
    }
    events = LearningReviewEvent.query.filter_by(session_id=session.id).all()
    positive = sum(event.rating in {"good", "easy"} for event in events)
    mastery_rate = round(positive * 100 / len(events)) if events else 0
    new_completed = sum(task.first_completed_at is not None and task.source_type == "new" for task in base_tasks)
    old_completed = sum(task.first_completed_at is not None and task.source_type in {"due", "overdue", "risk"} for task in base_tasks)
    weak_completed = sum(task.first_completed_at is not None and task.source_type == "weak" for task in base_tasks)
    libraries, course_library = _available_libraries(current_user.id, course_slug, course_name)
    active_library = _active_library(current_user.id, course_slug, course_name, requested_library_id)
    session_library = db.session.get(UserKnowledgeLibrary, session.library_id) if session.library_id else course_library
    library_rows = []
    for library in libraries:
        item_count = library.items.filter_by(is_active=True).count()
        mastered = KnowledgeMemoryState.query.join(UserKnowledgeItem).filter(
            KnowledgeMemoryState.user_id == current_user.id,
            KnowledgeMemoryState.state == "mastered",
            UserKnowledgeItem.library_id == library.id,
        ).count()
        library_rows.append({
            "library": library,
            "item_count": item_count,
            "mastered": mastered,
            "is_course": _is_course_library(library),
        })

    answer, explanation = _answer_parts(current_entry.task.item) if current_entry else ("", "")
    answered_entries = DailyLearningQueueEntry.query.join(DailyLearningTask).filter(
        DailyLearningQueueEntry.session_id == session.id,
        DailyLearningQueueEntry.answered_at.is_not(None),
        DailyLearningTask.is_base.is_(True),
        DailyLearningQueueEntry.reason == "base",
    ).all()
    average_answer_score = round(sum(entry.answer_score or 0 for entry in answered_entries) / len(answered_entries)) if answered_entries else 0
    correct_answers = sum(bool(entry.answer_correct) for entry in answered_entries)
    progress_percent = round(completed_base * 100 / max(1, session.base_target))
    return {
        "session": session,
        "course_slug": course_slug,
        "course_name": course_name,
        "libraries": library_rows,
        "active_library": active_library,
        "session_library": session_library,
        "current_entry": current_entry,
        "current_task": current_entry.task if current_entry else None,
        "answer": answer,
        "explanation": explanation,
        "pending_count": len(pending),
        "queue_summary": {
            "total": session.base_target,
            "requested": session.requested_target,
            "completed": completed_base,
            "percent": progress_percent,
            "review": source_counts["review"],
            "weak": source_counts["weak"],
            "new": source_counts["new"],
            "actual_reviews": session.actual_review_count,
        },
        "result": {
            "new_completed": new_completed,
            "old_completed": old_completed,
            "weak_completed": weak_completed,
            "actual_reviews": session.actual_review_count,
            "mastery_rate": mastery_rate,
            "answered": len(answered_entries),
            "correct_answers": correct_answers,
            "answer_score": average_answer_score,
            "duration": _format_duration(session.elapsed_seconds),
        },
        "is_learning": is_learning,
        "is_complete": session.status == "completed",
        "rating_labels": RATING_LABELS,
    }


@knowledge_study_bp.route("/api/study/session/start", methods=["POST"])
@login_required
def start_session():
    data = request.get_json(silent=True) or {}
    session = DailyLearningSession.query.filter_by(id=data.get("session_id"), user_id=current_user.id).first()
    if not session:
        return jsonify({"ok": False, "message": "今日学习任务不存在"}), 404
    if session.base_target <= 0:
        return jsonify({"ok": False, "message": "当前筛选条件下没有可学习内容，请调整知识库设置"}), 409
    if session.status == "not_started":
        session.status = "in_progress"
        session.started_at = _utcnow()
    session.last_activity_at = _utcnow()
    db.session.commit()
    return jsonify({"ok": True, "status": session.status})


@knowledge_study_bp.route("/api/study/session/time", methods=["POST"])
@login_required
def save_session_time():
    data = request.get_json(silent=True)
    if data is None:
        try:
            data = json.loads(request.get_data(as_text=True) or "{}")
        except json.JSONDecodeError:
            data = {}
    session = DailyLearningSession.query.filter_by(id=data.get("session_id"), user_id=current_user.id).first()
    if not session:
        return jsonify({"ok": False}), 404
    delta = _clamp_int(data.get("seconds"), 0, 0, 120)
    if session.status == "in_progress" or session.continue_active:
        session.elapsed_seconds += delta
        session.last_activity_at = _utcnow()
        db.session.commit()
    return jsonify({"ok": True, "elapsed_seconds": session.elapsed_seconds})


def _insert_repeat_entry(session, task, current_entry, repeat_after, rating):
    pending = _pending_entries(session)
    offset = repeat_after + ((session.actual_review_count + task.id) % (2 if rating == "again" else 3))
    if len(pending) >= offset:
        insert_order = pending[offset - 1].queue_order
        DailyLearningQueueEntry.query.filter(
            DailyLearningQueueEntry.session_id == session.id,
            DailyLearningQueueEntry.queue_order >= insert_order,
        ).update({DailyLearningQueueEntry.queue_order: DailyLearningQueueEntry.queue_order + 1}, synchronize_session=False)
    else:
        insert_order = db.session.query(func.max(DailyLearningQueueEntry.queue_order)).filter_by(session_id=session.id).scalar() or current_entry.queue_order
        insert_order += 1
    db.session.add(DailyLearningQueueEntry(
        session_id=session.id,
        task_id=task.id,
        queue_order=insert_order,
        reason="repeat_again" if rating == "again" else "repeat_hard",
    ))


def _sync_daily_checkin(session):
    if DailyCheckin.query.filter_by(user_id=session.user_id, date=session.study_date).first():
        return False
    base_tasks = DailyLearningTask.query.filter_by(session_id=session.id, is_base=True).order_by(
        DailyLearningTask.assigned_order.asc()
    ).all()
    point = None
    for task in base_tasks:
        source_ref = task.item.source_ref or ""
        if source_ref.startswith("system:"):
            try:
                point = db.session.get(KnowledgePoint, int(source_ref.split(":", 1)[1]))
            except (TypeError, ValueError):
                point = None
        if point:
            break
    point = point or KnowledgePoint.query.order_by(KnowledgePoint.id.asc()).first()
    if not point:
        return False
    answered_entries = DailyLearningQueueEntry.query.join(DailyLearningTask).filter(
        DailyLearningQueueEntry.session_id == session.id,
        DailyLearningTask.is_base.is_(True),
        DailyLearningQueueEntry.reason == "base",
        DailyLearningQueueEntry.answered_at.is_not(None),
    ).all()
    average_score = round(sum(entry.answer_score or 0 for entry in answered_entries) / max(1, len(answered_entries)))
    checkin_score = max(10, min(30, round(10 + average_score * 0.2)))
    difficulty = session.difficulty_filter if session.difficulty_filter in VALID_DIFFICULTIES - {"all"} else "intermediate"
    db.session.add(DailyCheckin(
        user_id=session.user_id,
        knowledge_point_id=point.id,
        difficulty=difficulty,
        score=checkin_score,
        date=session.study_date,
    ))
    return True


def _answer_terms(text):
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    latin = set(re.findall(r"[a-z0-9][a-z0-9_-]+", normalized))
    cjk_terms = set()
    for segment in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(segment) == 1:
            cjk_terms.add(segment)
        else:
            cjk_terms.update(segment[index:index + 2] for index in range(len(segment) - 1))
    return latin | cjk_terms


def _evaluate_answer(submitted, reference):
    submitted_text = (submitted or "").strip()
    reference_text = (reference or "").strip()
    if not submitted_text:
        return 0, False
    submitted_terms = _answer_terms(submitted_text)
    reference_terms = _answer_terms(reference_text)
    if not submitted_terms or not reference_terms:
        score = 100 if submitted_text.lower() == reference_text.lower() else 35
        return score, score >= 55
    overlap = len(submitted_terms & reference_terms)
    precision = overlap / max(1, len(submitted_terms))
    recall = overlap / max(1, len(reference_terms))
    score = round(70 * precision + 30 * min(1, recall * 3))
    compact_submitted = re.sub(r"\W+", "", submitted_text.lower())
    compact_reference = re.sub(r"\W+", "", reference_text.lower())
    if len(compact_submitted) >= 4 and compact_submitted in compact_reference:
        score = max(score, 75)
    score = max(0, min(100, score))
    return score, score >= 55


@knowledge_study_bp.route("/api/study/answer", methods=["POST"])
@login_required
def submit_answer():
    data = request.get_json(silent=True) or {}
    submitted = (data.get("answer") or "").strip()
    if not submitted:
        return jsonify({"ok": False, "message": "请先写下你的回答；不会时也可以填写“暂时不会”"}), 400
    if len(submitted) > 4000:
        return jsonify({"ok": False, "message": "回答不能超过 4000 个字符"}), 400
    entry = DailyLearningQueueEntry.query.join(DailyLearningSession).filter(
        DailyLearningQueueEntry.id == data.get("entry_id"),
        DailyLearningQueueEntry.state == "pending",
        DailyLearningSession.user_id == current_user.id,
        DailyLearningSession.study_date == date.today(),
    ).first()
    if not entry:
        return jsonify({"ok": False, "message": "当前学习卡片不存在或已完成"}), 404
    session = entry.session
    if not (session.status == "in_progress" or session.continue_active):
        return jsonify({"ok": False, "message": "请先开始或继续今日学习"}), 409
    pending = _pending_entries(session)
    if not pending or pending[0].id != entry.id:
        return jsonify({"ok": False, "message": "学习队列已更新，请刷新页面"}), 409
    answer, explanation = _answer_parts(entry.task.item)
    score, correct = _evaluate_answer(submitted, explanation or answer)
    entry.submitted_answer = submitted
    entry.answer_score = score
    entry.answer_correct = correct
    entry.answered_at = _utcnow()
    entry.shown_at = entry.shown_at or _utcnow()
    session.last_activity_at = _utcnow()
    db.session.commit()
    if score >= 80:
        recommended_rating = "easy"
        feedback = "回答与知识点高度匹配，可以尝试延长复习间隔。"
    elif score >= 55:
        recommended_rating = "good"
        feedback = "已覆盖主要信息，请对照标准答案补充细节。"
    elif score >= 25:
        recommended_rating = "hard"
        feedback = "回答涉及部分要点，建议标记为“有点模糊”。"
    else:
        recommended_rating = "again"
        feedback = "与标准答案重合较少，建议稍后再次学习。"
    return jsonify({
        "ok": True,
        "score": score,
        "correct": correct,
        "feedback": feedback,
        "recommended_rating": recommended_rating,
        "answer": answer,
        "explanation": explanation,
    })


@knowledge_study_bp.route("/api/study/review", methods=["POST"])
@login_required
def review_item():
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating not in VALID_RATINGS:
        return jsonify({"ok": False, "message": "无效的掌握度反馈"}), 400
    entry = DailyLearningQueueEntry.query.join(DailyLearningSession).filter(
        DailyLearningQueueEntry.id == data.get("entry_id"),
        DailyLearningQueueEntry.state == "pending",
        DailyLearningSession.user_id == current_user.id,
        DailyLearningSession.study_date == date.today(),
    ).first()
    if not entry:
        return jsonify({"ok": False, "message": "当前学习卡片不存在或已完成"}), 404
    session = entry.session
    if not (session.status == "in_progress" or session.continue_active):
        return jsonify({"ok": False, "message": "请先开始或继续今日学习"}), 409
    current = _pending_entries(session)
    if not current or current[0].id != entry.id:
        return jsonify({"ok": False, "message": "学习队列已更新，请刷新页面"}), 409
    if not entry.answered_at:
        return jsonify({"ok": False, "message": "请先提交回答并对照标准答案"}), 409

    state = _get_or_create_memory(current_user.id, entry.task.item_id, session.course_slug)
    previous_mastery = state.mastery_score
    previous_interval = state.interval_days
    decision = schedule_review(
        rating=rating,
        total_reviews=state.total_reviews,
        interval_days=state.interval_days,
        interval_stage=state.interval_stage,
        mastery_score=state.mastery_score,
        correct_streak=state.correct_streak,
    )
    state.state = decision.state
    state.mastery_score = decision.mastery_score
    state.correct_streak = decision.correct_streak
    state.interval_stage = decision.interval_stage
    state.interval_days = decision.interval_days
    state.next_review_date = decision.next_review_date
    state.is_weak = decision.is_weak
    state.last_rating = rating
    state.total_reviews += 1
    state.lapse_count += 1 if rating == "again" else 0
    state.last_reviewed_at = _utcnow()

    entry.state = "completed"
    entry.rating = rating
    entry.completed_at = _utcnow()
    if not entry.shown_at:
        entry.shown_at = _utcnow()
    session.actual_review_count += 1
    session.elapsed_seconds += _clamp_int(data.get("elapsed_seconds"), 0, 0, 120)
    session.last_activity_at = _utcnow()
    if not entry.task.first_completed_at:
        entry.task.first_completed_at = _utcnow()

    db.session.add(LearningReviewEvent(
        session_id=session.id,
        user_id=current_user.id,
        item_id=entry.task.item_id,
        queue_entry_id=entry.id,
        rating=rating,
        previous_mastery=previous_mastery,
        mastery_after=decision.mastery_score,
        previous_interval=previous_interval,
        next_interval=decision.interval_days,
        is_repeat=entry.reason.startswith("repeat_"),
    ))
    db.session.flush()
    if decision.repeat_after:
        _insert_repeat_entry(session, entry.task, entry, decision.repeat_after, rating)

    completed_base = DailyLearningTask.query.filter(
        DailyLearningTask.session_id == session.id,
        DailyLearningTask.is_base.is_(True),
        DailyLearningTask.first_completed_at.is_not(None),
    ).count()
    session.base_completed_count = completed_base
    checked_in = False
    pending_after_review = _pending_entries(session)
    if completed_base >= session.base_target and session.status != "completed" and not pending_after_review:
        session.status = "completed"
        session.base_completed_at = _utcnow()
        session.continue_active = False
        checked_in = _sync_daily_checkin(session)
    elif session.status == "completed" and session.continue_active and not pending_after_review:
        session.continue_active = False
    db.session.commit()
    return jsonify({
        "ok": True,
        "base_completed": session.base_completed_count,
        "base_target": session.base_target,
        "actual_reviews": session.actual_review_count,
        "session_status": session.status,
        "checked_in": checked_in,
        "repeat_inserted": bool(decision.repeat_after),
        "next_review_date": decision.next_review_date.isoformat(),
    })


def _append_queue_entry(session, task, reason):
    order = db.session.query(func.max(DailyLearningQueueEntry.queue_order)).filter_by(session_id=session.id).scalar() or 0
    entry = DailyLearningQueueEntry(
        session_id=session.id,
        task_id=task.id,
        queue_order=order + 1,
        reason=reason,
    )
    db.session.add(entry)
    return entry


def _continue_candidates(session, mode):
    course_name = COURSE_NAMES.get(session.course_slug, session.course_slug)
    items, _ = _learning_pool(
        current_user.id,
        session.course_slug,
        course_name,
        requested_library_id=session.library_id,
        study_mode_override="mixed",
        difficulty_override="advanced" if mode == "advanced" else session.difficulty_filter,
    )
    states = _memory_map(current_user.id, items)
    pending_item_ids = {
        entry.task.item_id
        for entry in _pending_entries(session)
    }
    task_by_item = {task.item_id: task for task in DailyLearningTask.query.filter_by(session_id=session.id).all()}
    today_events = LearningReviewEvent.query.filter_by(session_id=session.id).order_by(LearningReviewEvent.reviewed_at.desc()).all()
    forgotten_ids = [event.item_id for event in today_events if event.rating == "again"]
    fuzzy_ids = [event.item_id for event in today_events if event.rating == "hard"]
    item_map = {item.id: item for item in items}
    ordered = []

    def add(item):
        if item and item.id not in {candidate.id for candidate in ordered} and item.id not in pending_item_ids:
            ordered.append(item)

    old_items = [item for item in items if states.get(item.id) and states[item.id].total_reviews]
    old_items.sort(key=lambda item: (states[item.id].next_review_date, states[item.id].mastery_score))
    new_items = [item for item in items if not states.get(item.id) or not states[item.id].total_reviews]
    weak_items = [item for item in old_items if states[item.id].is_weak]

    if mode == "advanced":
        for item in weak_items:
            add(item)
        for item in new_items:
            add(item)
        for item in old_items:
            add(item)
        return ordered, task_by_item
    if mode != "new":
        for item in old_items:
            if states[item.id].next_review_date <= date.today():
                add(item)
        for item_id in forgotten_ids:
            add(item_map.get(item_id))
        for item_id in fuzzy_ids:
            add(item_map.get(item_id))
        for item in weak_items:
            add(item)
    if mode != "review":
        for item in new_items:
            add(item)
    if mode == "mixed":
        for item in old_items:
            add(item)
    return ordered, task_by_item


@knowledge_study_bp.route("/api/study/continue", methods=["POST"])
@login_required
def continue_learning():
    data = request.get_json(silent=True) or {}
    session = DailyLearningSession.query.filter_by(id=data.get("session_id"), user_id=current_user.id).first()
    if not session or session.status != "completed":
        return jsonify({"ok": False, "message": "请先完成今日基础任务"}), 409
    mode = data.get("mode", "mixed")
    if mode not in {"mixed", "review", "new", "advanced"}:
        mode = "mixed"
    count = _clamp_int(data.get("count"), 5, 1, 50)
    pending = _pending_entries(session)
    needed = max(0, count - len(pending))
    candidates, task_by_item = _continue_candidates(session, mode)
    added = 0
    for item in candidates:
        if added >= needed:
            break
        task = task_by_item.get(item.id)
        state = _get_or_create_memory(current_user.id, item.id, session.course_slug)
        if not task:
            task = DailyLearningTask(
                session_id=session.id,
                item_id=item.id,
                is_base=False,
                source_type="new" if not state.total_reviews else ("weak" if state.is_weak else "review"),
                assigned_order=session.base_target + len(task_by_item) + 1,
            )
            db.session.add(task)
            db.session.flush()
            task_by_item[item.id] = task
        _append_queue_entry(session, task, f"extra_{mode}")
        added += 1
    if not pending and not added:
        return jsonify({"ok": False, "message": "当前没有符合条件的知识点"}), 409
    session.continue_active = True
    session.last_activity_at = _utcnow()
    db.session.commit()
    return jsonify({"ok": True, "added": added, "pending": len(pending) + added})


@knowledge_study_bp.route("/study/library/create", methods=["POST"])
@login_required
def create_library():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("请输入知识库名称", "error")
        return redirect(url_for("study"))
    duplicate = UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, name=name, is_archived=False).first()
    if duplicate:
        flash("你已经有同名知识库", "info")
        return redirect(url_for("study", library=duplicate.id))
    for existing_library in UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_archived=False).all():
        existing_library.is_active = False
    library = UserKnowledgeLibrary(
        user_id=current_user.id,
        name=name[:120],
        description=(request.form.get("description") or "").strip(),
        daily_new_count=BASE_DAILY_TARGET,
        is_active=True,
    )
    db.session.add(library)
    db.session.flush()
    rebuilt = _rebuild_unstarted_session(library.id)
    if not rebuilt:
        db.session.commit()
    flash("知识库已创建并设为当前；请添加或上传知识内容", "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/upload", methods=["POST"])
@login_required
def upload_library():
    upload = request.files.get("knowledge_file")
    if not upload or not upload.filename:
        flash("请选择要上传的知识库文件", "error")
        return redirect(url_for("study"))
    try:
        filename, items = parse_library_upload(upload)
    except (ValueError, json.JSONDecodeError, csv.Error) as exc:
        flash(str(exc), "error")
        return redirect(url_for("study"))
    library_id = request.form.get("library_id", type=int)
    library = _owned_library(library_id) if library_id else None
    if library and _is_course_library(library):
        return jsonify({"ok": False, "message": "课程知识库不可直接修改"}), 403
    created_new = library is None
    if created_new:
        proposed_name = (request.form.get("library_name") or Path(filename).stem or "我的知识库").strip()
        for existing_library in UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_archived=False).all():
            existing_library.is_active = False
        library = UserKnowledgeLibrary(
            user_id=current_user.id,
            name=proposed_name[:120],
            source_filename=filename,
            daily_new_count=BASE_DAILY_TARGET,
            is_active=True,
        )
        db.session.add(library)
        db.session.flush()
    start_position = db.session.query(func.max(UserKnowledgeItem.position)).filter_by(library_id=library.id).scalar() or 0
    for offset, item_data in enumerate(items, start=1):
        db.session.add(UserKnowledgeItem(
            library_id=library.id,
            title=item_data["title"],
            content=item_data["content"],
            hint=item_data["hint"],
            tags=item_data["tags"],
            difficulty=item_data["difficulty"],
            position=start_position + offset,
            source_ref=f"{filename}:{offset}",
        ))
    library.source_filename = filename
    db.session.flush()
    rebuilt = library.is_active and _rebuild_unstarted_session(library.id)
    if not rebuilt:
        db.session.commit()
    flash(f"已导入 {len(items)} 条知识内容；{'今日未开始任务已更新' if rebuilt else '已开始的今日任务保持不变'}", "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/item", methods=["POST"])
@login_required
def add_library_item(library_id):
    library = _owned_library(library_id)
    if _is_course_library(library):
        return jsonify({"ok": False}), 403
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    if not title or not content:
        flash("标题和内容都不能为空", "error")
        return redirect(url_for("study", library=library.id))
    position = (db.session.query(func.max(UserKnowledgeItem.position)).filter_by(library_id=library.id).scalar() or 0) + 1
    db.session.add(UserKnowledgeItem(
        library_id=library.id,
        title=title[:240],
        content=content,
        hint=(request.form.get("hint") or "").strip(),
        tags=(request.form.get("tags") or "").strip()[:500],
        difficulty=request.form.get("difficulty") if request.form.get("difficulty") in {"beginner", "intermediate", "advanced"} else "intermediate",
        position=position,
    ))
    db.session.flush()
    rebuilt = library.is_active and _rebuild_unstarted_session(library.id)
    if not rebuilt:
        db.session.commit()
    flash("知识条目已保存；" + ("今日未开始任务已更新" if rebuilt else "已开始的今日任务保持不变"), "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/activate", methods=["POST"])
@login_required
def activate_library(library_id):
    library = _owned_library(library_id)
    for row in UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_archived=False).all():
        row.is_active = row.id == library.id
    db.session.flush()
    rebuilt = _rebuild_unstarted_session(library.id)
    if not rebuilt:
        db.session.commit()
    flash(
        f"已切换到“{library.name}”；" + ("今日未开始任务已重新生成" if rebuilt else "已开始的今日任务保持不变，明日生效"),
        "success",
    )
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/settings", methods=["POST"])
@login_required
def update_library_settings(library_id):
    library = _owned_library(library_id)
    if not _is_course_library(library):
        library.description = (request.form.get("description") or library.description or "").strip()
    library.daily_new_count = _clamp_int(request.form.get("daily_count"), library.daily_new_count or BASE_DAILY_TARGET, 1, MAX_DAILY_TARGET)
    study_mode = request.form.get("study_mode") or "mixed"
    difficulty_filter = request.form.get("difficulty_filter") or "all"
    library.study_mode = study_mode if study_mode in VALID_STUDY_MODES else "mixed"
    library.difficulty_filter = difficulty_filter if difficulty_filter in VALID_DIFFICULTIES else "all"
    library.content_filter = (request.form.get("content_filter") or "").strip()[:200]
    db.session.flush()
    rebuilt = library.is_active and _rebuild_unstarted_session(library.id)
    if not rebuilt:
        db.session.commit()
    flash(
        "学习计划已更新；" + ("今日尚未开始，任务已按新设置生成" if rebuilt else "当前任务已开始，设置将在明日生效"),
        "success",
    )
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/archive", methods=["POST"])
@login_required
def archive_library(library_id):
    library = _owned_library(library_id)
    if _is_course_library(library):
        return jsonify({"ok": False}), 403
    library.is_archived = True
    library.is_active = False
    course_slug, course_name = _current_course()
    libraries, course_library = _available_libraries(current_user.id, course_slug, course_name)
    replacement = next((row for row in libraries if row.id != library.id), course_library)
    if replacement:
        replacement.is_active = True
    db.session.flush()
    rebuilt = _rebuild_unstarted_session(replacement.id if replacement else None)
    if not rebuilt:
        db.session.commit()
    flash("知识库已归档，历史学习记录仍然保留", "success")
    return redirect(url_for("study"))
