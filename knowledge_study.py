# -*- coding: utf-8 -*-
"""Private knowledge libraries and daily spaced-review queues."""

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.utils import secure_filename

from models import (
    db,
    DailyCheckin,
    DailyKnowledgeTask,
    KnowledgePoint,
    KnowledgeReviewLog,
    KnowledgeReviewProgress,
    UserKnowledgeItem,
    UserKnowledgeLibrary,
)


knowledge_study_bp = Blueprint("knowledge_study", __name__)
ALLOWED_LIBRARY_EXTENSIONS = {".csv", ".json", ".txt", ".md"}
MAX_LIBRARY_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ITEMS = 1000
RATING_LABELS = {"again": "忘记", "hard": "模糊", "good": "认识", "easy": "掌握"}


def _utcnow():
    return datetime.now(timezone.utc)


def _clamp_int(value, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _owned_library(library_id, include_archived=False):
    query = UserKnowledgeLibrary.query.filter_by(id=library_id, user_id=current_user.id)
    if not include_archived:
        query = query.filter_by(is_archived=False)
    return query.first_or_404()


def _decode_upload(raw):
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文件编码无法识别，请保存为 UTF-8 后重试")


def _normalise_item(raw, index):
    if not isinstance(raw, dict):
        raw = {"title": str(raw), "content": str(raw)}

    def first_value(*keys):
        for key in keys:
            value = raw.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    title = first_value("title", "name", "term", "front", "question", "知识点", "标题", "问题")
    content = first_value("content", "answer", "back", "definition", "explanation", "内容", "答案", "解释")
    hint = first_value("hint", "提示")
    tags = first_value("tags", "tag", "标签")
    difficulty = first_value("difficulty", "难度") or "intermediate"
    if difficulty not in {"beginner", "intermediate", "advanced"}:
        difficulty = "intermediate"
    if not title and content:
        title = content[:60]
    if not content and title:
        content = title
    if not title or not content:
        return None
    return {
        "title": title[:240],
        "content": content,
        "hint": hint,
        "tags": tags[:500],
        "difficulty": difficulty,
        "position": index,
    }


def parse_library_upload(file_storage):
    filename = secure_filename(file_storage.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_LIBRARY_EXTENSIONS:
        raise ValueError("仅支持 CSV、JSON、TXT 和 Markdown 文件")
    raw = file_storage.read(MAX_LIBRARY_BYTES + 1)
    if len(raw) > MAX_LIBRARY_BYTES:
        raise ValueError("文件不能超过 2 MB")
    if not raw:
        raise ValueError("上传文件为空")
    text = _decode_upload(raw)
    records = []

    if suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict):
            payload = payload.get("items", payload.get("knowledge", [payload]))
        if not isinstance(payload, list):
            raise ValueError("JSON 顶层应为数组，或包含 items 数组")
        records = payload
    elif suffix == ".csv":
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV 需要包含标题行")
        records = list(reader)
    else:
        blocks = [block.strip() for block in text.replace("\r\n", "\n").split("\n\n") if block.strip()]
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            if len(lines) == 1 and "\t" in lines[0]:
                title, content = lines[0].split("\t", 1)
            elif len(lines) == 1 and "::" in lines[0]:
                title, content = lines[0].split("::", 1)
            else:
                title = lines[0].lstrip("# ").strip()
                content = "\n".join(lines[1:]).strip() or title
            records.append({"title": title, "content": content})

    items = []
    for index, raw_item in enumerate(records[:MAX_IMPORT_ITEMS], start=1):
        item = _normalise_item(raw_item, index)
        if item:
            items.append(item)
    if not items:
        raise ValueError("没有识别到有效知识条目")
    return filename, items


def _library_item_count(library_id):
    return UserKnowledgeItem.query.filter_by(library_id=library_id, is_active=True).count()


def _ensure_progress(user_id, item_id):
    progress = KnowledgeReviewProgress.query.filter_by(user_id=user_id, item_id=item_id).first()
    if not progress:
        progress = KnowledgeReviewProgress(
            user_id=user_id,
            item_id=item_id,
            state="new",
            next_review_date=date.today(),
        )
        db.session.add(progress)
        db.session.flush()
    return progress


def ensure_daily_queue(user_id, library):
    """Build an idempotent queue: due reviews, new cards, then daily reinforcement."""
    today = date.today()
    existing = (
        DailyKnowledgeTask.query.join(UserKnowledgeItem)
        .filter(
            DailyKnowledgeTask.user_id == user_id,
            DailyKnowledgeTask.study_date == today,
            UserKnowledgeItem.library_id == library.id,
        )
        .order_by(DailyKnowledgeTask.position.asc(), DailyKnowledgeTask.id.asc())
        .all()
    )
    scheduled_ids = {task.item_id for task in existing}
    existing_new = sum(task.queue_type == "new" for task in existing)
    existing_review = sum(task.queue_type in {"review", "relearn"} for task in existing)
    next_position = max((task.position for task in existing), default=0) + 1

    due_progress = (
        KnowledgeReviewProgress.query.join(UserKnowledgeItem)
        .filter(
            KnowledgeReviewProgress.user_id == user_id,
            KnowledgeReviewProgress.next_review_date <= today,
            UserKnowledgeItem.library_id == library.id,
            UserKnowledgeItem.is_active.is_(True),
            ~UserKnowledgeItem.id.in_(scheduled_ids or {-1}),
        )
        .order_by(
            KnowledgeReviewProgress.next_review_date.asc(),
            KnowledgeReviewProgress.lapses.desc(),
            KnowledgeReviewProgress.last_reviewed_at.asc(),
        )
        .limit(max(0, library.review_limit - existing_review))
        .all()
    )
    for progress in due_progress:
        db.session.add(DailyKnowledgeTask(
            user_id=user_id,
            item_id=progress.item_id,
            study_date=today,
            position=next_position,
            queue_type="review" if progress.total_reviews else "new",
        ))
        scheduled_ids.add(progress.item_id)
        next_position += 1

    progress_ids = {
        row[0]
        for row in db.session.query(KnowledgeReviewProgress.item_id)
        .filter(KnowledgeReviewProgress.user_id == user_id)
        .all()
    }
    new_limit = max(0, library.daily_new_count - existing_new)
    if new_limit:
        new_items = (
            UserKnowledgeItem.query.filter(
                UserKnowledgeItem.library_id == library.id,
                UserKnowledgeItem.is_active.is_(True),
                ~UserKnowledgeItem.id.in_(progress_ids or {-1}),
                ~UserKnowledgeItem.id.in_(scheduled_ids or {-1}),
            )
            .order_by(UserKnowledgeItem.position.asc(), UserKnowledgeItem.id.asc())
            .limit(new_limit)
            .all()
        )
        for item in new_items:
            _ensure_progress(user_id, item.id)
            db.session.add(DailyKnowledgeTask(
                user_id=user_id,
                item_id=item.id,
                study_date=today,
                position=next_position,
                queue_type="new",
            ))
            scheduled_ids.add(item.id)
            next_position += 1

    current_total = DailyKnowledgeTask.query.join(UserKnowledgeItem).filter(
        DailyKnowledgeTask.user_id == user_id,
        DailyKnowledgeTask.study_date == today,
        UserKnowledgeItem.library_id == library.id,
    ).count()
    reinforcement_needed = max(0, library.daily_new_count - current_total)
    if reinforcement_needed:
        reinforcement = (
            KnowledgeReviewProgress.query.join(UserKnowledgeItem)
            .filter(
                KnowledgeReviewProgress.user_id == user_id,
                UserKnowledgeItem.library_id == library.id,
                UserKnowledgeItem.is_active.is_(True),
                ~UserKnowledgeItem.id.in_(scheduled_ids or {-1}),
            )
            .order_by(KnowledgeReviewProgress.last_reviewed_at.asc(), KnowledgeReviewProgress.next_review_date.asc())
            .limit(reinforcement_needed)
            .all()
        )
        for progress in reinforcement:
            db.session.add(DailyKnowledgeTask(
                user_id=user_id,
                item_id=progress.item_id,
                study_date=today,
                position=next_position,
                queue_type="reinforcement",
            ))
            next_position += 1

    db.session.commit()
    return (
        DailyKnowledgeTask.query.join(UserKnowledgeItem)
        .filter(
            DailyKnowledgeTask.user_id == user_id,
            DailyKnowledgeTask.study_date == today,
            UserKnowledgeItem.library_id == library.id,
        )
        .order_by(DailyKnowledgeTask.position.asc(), DailyKnowledgeTask.id.asc())
        .all()
    )


def build_custom_study_context():
    libraries = (
        UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_archived=False)
        .order_by(UserKnowledgeLibrary.is_active.desc(), UserKnowledgeLibrary.updated_at.desc())
        .all()
    )
    requested_id = request.args.get("library", type=int)
    active_library = None
    if requested_id:
        active_library = next((lib for lib in libraries if lib.id == requested_id), None)
    if not active_library:
        active_library = next((lib for lib in libraries if lib.is_active), libraries[0] if libraries else None)

    library_rows = []
    for library in libraries:
        item_count = _library_item_count(library.id)
        mastered = (
            KnowledgeReviewProgress.query.join(UserKnowledgeItem)
            .filter(
                KnowledgeReviewProgress.user_id == current_user.id,
                KnowledgeReviewProgress.state == "mastered",
                UserKnowledgeItem.library_id == library.id,
            )
            .count()
        )
        library_rows.append({"library": library, "item_count": item_count, "mastered": mastered})

    tasks = ensure_daily_queue(current_user.id, active_library) if active_library else []
    pending = [task for task in tasks if task.state == "pending"]
    completed = len(tasks) - len(pending)
    total = len(tasks)
    progress_percent = int(completed * 100 / total) if total else 0
    queue_summary = {
        "total": total,
        "pending": len(pending),
        "completed": completed,
        "percent": progress_percent,
        "new": sum(task.queue_type == "new" for task in tasks),
        "review": sum(task.queue_type in {"review", "relearn"} for task in tasks),
        "reinforcement": sum(task.queue_type == "reinforcement" for task in tasks),
    }

    learned_count = mastered_count = due_count = 0
    if active_library:
        base_progress = KnowledgeReviewProgress.query.join(UserKnowledgeItem).filter(
            KnowledgeReviewProgress.user_id == current_user.id,
            UserKnowledgeItem.library_id == active_library.id,
        )
        learned_count = base_progress.count()
        mastered_count = base_progress.filter(KnowledgeReviewProgress.state == "mastered").count()
        due_count = base_progress.filter(KnowledgeReviewProgress.next_review_date <= date.today()).count()

    return {
        "libraries": library_rows,
        "active_library": active_library,
        "daily_tasks": tasks,
        "pending_tasks": pending,
        "current_task": pending[0] if pending else None,
        "queue_summary": queue_summary,
        "learned_count": learned_count,
        "mastered_count": mastered_count,
        "due_count": due_count,
        "rating_labels": RATING_LABELS,
    }


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
    has_active = UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_active=True, is_archived=False).first()
    library = UserKnowledgeLibrary(
        user_id=current_user.id,
        name=name[:120],
        description=(request.form.get("description") or "").strip(),
        daily_new_count=_clamp_int(request.form.get("daily_new_count"), 5, 1, 50),
        is_active=has_active is None,
    )
    db.session.add(library)
    db.session.commit()
    flash("知识库已创建，可以上传文件或手动添加内容", "success")
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
    if not library:
        proposed_name = (request.form.get("library_name") or Path(filename).stem or "我的知识库").strip()
        has_active = UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_active=True, is_archived=False).first()
        library = UserKnowledgeLibrary(
            user_id=current_user.id,
            name=proposed_name[:120],
            source_filename=filename,
            daily_new_count=_clamp_int(request.form.get("daily_new_count"), 5, 1, 50),
            is_active=has_active is None,
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
    db.session.commit()
    flash(f"已导入 {len(items)} 条知识内容", "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/item", methods=["POST"])
@login_required
def add_library_item(library_id):
    library = _owned_library(library_id)
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
    db.session.commit()
    flash("知识条目已加入今日学习体系", "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/activate", methods=["POST"])
@login_required
def activate_library(library_id):
    library = _owned_library(library_id)
    UserKnowledgeLibrary.query.filter_by(user_id=current_user.id, is_archived=False).update({"is_active": False})
    library.is_active = True
    db.session.commit()
    flash(f"已切换到“{library.name}”", "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/settings", methods=["POST"])
@login_required
def update_library_settings(library_id):
    library = _owned_library(library_id)
    library.daily_new_count = _clamp_int(request.form.get("daily_new_count"), library.daily_new_count, 1, 50)
    library.review_limit = _clamp_int(request.form.get("review_limit"), library.review_limit, 5, 200)
    library.description = (request.form.get("description") or library.description or "").strip()
    db.session.commit()
    flash("每日学习计划已更新", "success")
    return redirect(url_for("study", library=library.id))


@knowledge_study_bp.route("/study/library/<int:library_id>/archive", methods=["POST"])
@login_required
def archive_library(library_id):
    library = _owned_library(library_id)
    was_active = library.is_active
    library.is_archived = True
    library.is_active = False
    if was_active:
        replacement = UserKnowledgeLibrary.query.filter(
            UserKnowledgeLibrary.user_id == current_user.id,
            UserKnowledgeLibrary.id != library.id,
            UserKnowledgeLibrary.is_archived.is_(False),
        ).order_by(UserKnowledgeLibrary.updated_at.desc()).first()
        if replacement:
            replacement.is_active = True
    db.session.commit()
    flash("知识库已归档，学习记录仍然保留", "success")
    return redirect(url_for("study"))


def _sync_daily_checkin(user_id, library):
    pending = DailyKnowledgeTask.query.join(UserKnowledgeItem).filter(
        DailyKnowledgeTask.user_id == user_id,
        DailyKnowledgeTask.study_date == date.today(),
        DailyKnowledgeTask.state == "pending",
        UserKnowledgeItem.library_id == library.id,
    ).count()
    total = DailyKnowledgeTask.query.join(UserKnowledgeItem).filter(
        DailyKnowledgeTask.user_id == user_id,
        DailyKnowledgeTask.study_date == date.today(),
        UserKnowledgeItem.library_id == library.id,
    ).count()
    if pending or not total or DailyCheckin.query.filter_by(user_id=user_id, date=date.today()).first():
        return False
    source = f"user-library:{library.id}"
    point = KnowledgePoint.query.filter_by(source=source).first()
    if not point:
        point = KnowledgePoint(
            title=f"知识库学习：{library.name}",
            content=f"完成个人知识库“{library.name}”的今日复习任务。",
            difficulty="intermediate",
            category="personal",
            source=source,
        )
        db.session.add(point)
        db.session.flush()
    db.session.add(DailyCheckin(
        user_id=user_id,
        knowledge_point_id=point.id,
        difficulty="intermediate",
        score=min(50, 10 + total * 2),
        date=date.today(),
    ))
    return True


@knowledge_study_bp.route("/api/study/review", methods=["POST"])
@login_required
def review_item():
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    rating = data.get("rating")
    if rating not in RATING_LABELS:
        return jsonify({"ok": False, "message": "无效的记忆反馈"}), 400
    task = DailyKnowledgeTask.query.filter_by(id=task_id, user_id=current_user.id, study_date=date.today()).first()
    if not task:
        return jsonify({"ok": False, "message": "今日任务不存在"}), 404
    if task.state == "completed":
        return jsonify({"ok": False, "message": "这条内容已经完成"}), 409

    progress = _ensure_progress(current_user.id, task.item_id)
    previous_interval = progress.interval_days or 0
    progress.total_reviews = (progress.total_reviews or 0) + 1
    progress.last_reviewed_at = _utcnow()
    progress.last_rating = rating
    task.attempts = (task.attempts or 0) + 1

    if rating == "again":
        progress.repetitions = 0
        progress.interval_days = 0
        progress.ease_factor = max(1.3, (progress.ease_factor or 2.3) - 0.2)
        progress.next_review_date = date.today()
        progress.lapses = (progress.lapses or 0) + 1
        progress.state = "learning"
        max_position = db.session.query(func.max(DailyKnowledgeTask.position)).filter_by(
            user_id=current_user.id, study_date=date.today()
        ).scalar() or task.position
        task.position = max_position + 1
        task.queue_type = "relearn"
    else:
        repetitions = (progress.repetitions or 0) + 1
        progress.repetitions = repetitions
        ease = progress.ease_factor or 2.3
        if rating == "hard":
            interval = 1
            progress.ease_factor = max(1.3, ease - 0.12)
            progress.state = "learning"
        elif rating == "good":
            interval = 3 if previous_interval <= 1 else max(3, round(previous_interval * ease))
            progress.state = "review"
        else:
            interval = 7 if previous_interval <= 3 else max(7, round(previous_interval * ease * 1.3))
            progress.ease_factor = min(3.2, ease + 0.15)
            progress.state = "mastered" if repetitions >= 4 or interval >= 30 else "review"
        progress.interval_days = interval
        progress.next_review_date = date.today() + timedelta(days=interval)
        task.state = "completed"
        task.completed_at = _utcnow()

    db.session.add(KnowledgeReviewLog(
        user_id=current_user.id,
        item_id=task.item_id,
        task_id=task.id,
        rating=rating,
        previous_interval=previous_interval,
        next_interval=progress.interval_days,
    ))
    library = task.item.library
    checked_in = _sync_daily_checkin(current_user.id, library)
    db.session.commit()

    remaining = DailyKnowledgeTask.query.join(UserKnowledgeItem).filter(
        DailyKnowledgeTask.user_id == current_user.id,
        DailyKnowledgeTask.study_date == date.today(),
        DailyKnowledgeTask.state == "pending",
        UserKnowledgeItem.library_id == library.id,
    ).count()
    return jsonify({
        "ok": True,
        "remaining": remaining,
        "checked_in": checked_in,
        "next_review_date": progress.next_review_date.isoformat(),
        "next_interval": progress.interval_days,
    })
