# -*- coding: utf-8 -*-
"""Replaceable spaced-repetition policy for Knowledge Forest daily study.

The public function intentionally depends only on primitive state so a future
SM-2 or FSRS implementation can replace this module without changing routes,
templates, or database orchestration.
"""

from dataclasses import dataclass
from datetime import date, timedelta


INTERVAL_STAGES = (1, 3, 7, 15, 30, 60, 120)
VALID_RATINGS = ("again", "hard", "good", "easy")


@dataclass(frozen=True)
class ReviewDecision:
    rating: str
    interval_days: int
    interval_stage: int
    next_review_date: date
    mastery_score: int
    correct_streak: int
    state: str
    is_weak: bool
    repeat_after: int | None


def _bounded(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(value)))


def _stage_for_interval(interval_days):
    stage = 0
    for index, interval in enumerate(INTERVAL_STAGES):
        if interval <= max(0, interval_days or 0):
            stage = index
    return stage


def schedule_review(
    *,
    rating,
    total_reviews=0,
    interval_days=0,
    interval_stage=0,
    mastery_score=0,
    correct_streak=0,
    today=None,
):
    """Return the next memory state for one answer.

    `repeat_after` is a same-day queue hint. The persisted next review date is
    still tomorrow or later, keeping within-day repetition separate from the
    long-term schedule.
    """
    if rating not in VALID_RATINGS:
        raise ValueError("unsupported review rating")
    today = today or date.today()
    first_review = not total_reviews
    stage = max(0, min(len(INTERVAL_STAGES) - 1, interval_stage or _stage_for_interval(interval_days)))
    mastery = _bounded(mastery_score)
    streak = max(0, int(correct_streak or 0))

    if rating == "again":
        next_interval = 1
        next_stage = 0
        mastery = _bounded(mastery - (25 if total_reviews else 15))
        streak = 0
        state = "learning"
        weak = True
        repeat_after = 2
    elif rating == "hard":
        next_interval = 2 if first_review else max(1, min(3, interval_days or 2))
        next_stage = 0 if next_interval <= 1 else 1
        mastery = _bounded(mastery + (3 if first_review else -3))
        streak = max(0, streak - 1)
        state = "learning"
        weak = True
        repeat_after = 4
    elif rating == "good":
        if first_review:
            next_stage = 1
            next_interval = 3
        else:
            next_stage = min(len(INTERVAL_STAGES) - 1, stage + 1)
            next_interval = INTERVAL_STAGES[next_stage]
        mastery = _bounded(mastery + 12)
        streak += 1
        state = "review"
        weak = mastery < 55
        repeat_after = None
    else:
        if first_review:
            next_stage = 2
            next_interval = 7
        else:
            next_stage = min(len(INTERVAL_STAGES) - 1, stage + 2)
            next_interval = INTERVAL_STAGES[next_stage]
        mastery = _bounded(mastery + 20)
        streak += 1
        state = "mastered" if mastery >= 85 and streak >= 3 else "review"
        weak = False
        repeat_after = None

    return ReviewDecision(
        rating=rating,
        interval_days=next_interval,
        interval_stage=next_stage,
        next_review_date=today + timedelta(days=next_interval),
        mastery_score=mastery,
        correct_streak=streak,
        state=state,
        is_weak=weak,
        repeat_after=repeat_after,
    )
