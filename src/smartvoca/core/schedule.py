#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 일차 편성과 일차 상태 판정·진도 집계 (PR-02, PR-03)
# 파일 위치: src/smartvoca/core/schedule.py
"""진도 로직.

일차는 저장하지 않고 단어 수에서 매번 계산한다.
"현재 일차"도 저장하지 않고 일차 기록에서 계산한다 — 따로 저장하면 서로 어긋날 수 있기 때문이다.
"""
from __future__ import annotations

from .models import DAY_SIZE, DayRange, DayRecord, DayStatus, Progress, ProgressSummary

_EMPTY_DAY = DayRecord()


def build_days(word_count: int, day_size: int = DAY_SIZE) -> list[DayRange]:
    """단어를 순서대로 day_size 개씩 나눈다. 마지막 일차는 남은 단어로 구성한다 (FR-07)."""
    if word_count < 1:
        raise ValueError("단어 수는 1 이상이어야 합니다")
    if day_size < 1:
        raise ValueError("일차당 단어 수는 1 이상이어야 합니다")
    days = []
    for start in range(0, word_count, day_size):
        day_no = start // day_size + 1
        days.append(DayRange(day_no, start, min(start + day_size, word_count)))
    return days


def _record(progress: Progress, day_no: int) -> DayRecord:
    # 기록이 없는 일차는 암기·시험 모두 하지 않은 것으로 본다
    return progress.days.get(day_no, _EMPTY_DAY)


def day_status(progress: Progress, day_no: int) -> DayStatus:
    """일차 상태. 날짜가 아니라 완료 여부로만 정한다 (FR-08)."""
    record = _record(progress, day_no)
    if record.tested:
        return DayStatus.DONE
    if record.memorized:
        return DayStatus.MEMORIZED
    if day_no == 1 or _record(progress, day_no - 1).tested:
        return DayStatus.AVAILABLE
    return DayStatus.LOCKED


def current_day(progress: Progress, total_days: int) -> int | None:
    """완료하지 않은 가장 작은 일차. 모두 완료했으면 None."""
    for day_no in range(1, total_days + 1):
        if not _record(progress, day_no).tested:
            return day_no
    return None


def can_take_exam(progress: Progress, day_no: int) -> bool:
    """암기 완료 이상인 일차만 시험을 볼 수 있다 (FR-13)."""
    return day_status(progress, day_no) in (DayStatus.MEMORIZED, DayStatus.DONE)


def reviewable_days(progress: Progress, total_days: int) -> list[int]:
    """복습·재시험 대상: 암기 완료 이상인 일차 (FR-20)."""
    return [d for d in range(1, total_days + 1) if can_take_exam(progress, d)]


def progress_summary(progress: Progress, total_days: int) -> ProgressSummary:
    """메인 화면에 보여 줄 진도 현황 (FR-09)."""
    done_days = sum(
        1 for d in range(1, total_days + 1) if _record(progress, d).tested
    )
    wrong_list_size = sum(1 for r in progress.words.values() if r.in_wrong_list)
    return ProgressSummary(
        current_day=current_day(progress, total_days),
        total_days=total_days,
        done_days=done_days,
        wrong_list_size=wrong_list_size,
    )
