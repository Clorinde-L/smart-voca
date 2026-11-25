#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 일차 편성과 일차 상태 판정·진도 집계 (PR-02, PR-03)
# 파일 위치: src/smartvoca/core/schedule.py
"""진도 로직.

일차는 저장하지 않고 단어 수와 하루 학습량에서 매번 계산한다 (VOCA-FR-011).
2026-11-25 일차 상태도 저장하지 않고 단어 단위 이력에서 계산한다 (ADR-26).
- 암기 완료: 그 일차의 모든 단어에 암기 이력이 있다
- 완료: 그 일차의 모든 단어가 일차 시험에 나온 적이 있다
그래서 하루 학습량을 바꾸거나 단어를 더하고 지워도 "외운 단어는 외운 것"으로 남는다.
"""
from __future__ import annotations

from collections.abc import Sequence, Set

from .models import DayRange, DayStatus, Word


def build_days(word_count: int, day_size: int) -> list[DayRange]:
    """단어를 순서대로 day_size 개씩 나눈다. 마지막 일차는 남은 단어로 구성한다.

    단어가 하나도 없으면 일차도 없다 (단어를 모두 지운 경우).
    """
    if word_count < 0:
        raise ValueError("단어 수는 0 이상이어야 합니다")
    if day_size < 1:
        raise ValueError("하루 학습량은 1 이상이어야 합니다")
    return [
        DayRange(start // day_size + 1, start, min(start + day_size, word_count))
        for start in range(0, word_count, day_size)
    ]


def day_of(index: int, day_size: int) -> int:
    """단어장 순번(0 부터)이 속한 일차."""
    return index // day_size + 1


def day_status(day_words: Sequence[Word], studied_ids: Set[int], tested_ids: Set[int]) -> DayStatus:
    """일차 상태. 그 일차 단어의 이력만으로 정한다 (FR-08, ADR-21, ADR-26)."""
    ids = [word.id for word in day_words]
    if ids and all(word_id in tested_ids for word_id in ids):
        return DayStatus.DONE
    if ids and all(word_id in studied_ids for word_id in ids):
        return DayStatus.MEMORIZED
    return DayStatus.AVAILABLE


def all_day_statuses(
    words: Sequence[Word], days: Sequence[DayRange], studied_ids: Set[int], tested_ids: Set[int]
) -> list[DayStatus]:
    return [day_status(words[day.start : day.end], studied_ids, tested_ids) for day in days]


def current_day(statuses: Sequence[DayStatus]) -> int | None:
    """완료하지 않은 가장 작은 일차 (메인의 '오늘의 학습' 추천). 모두 완료했으면 None."""
    for day_no, status in enumerate(statuses, start=1):
        if status is not DayStatus.DONE:
            return day_no
    return None


def can_take_exam(status: DayStatus) -> bool:
    """암기 완료 이상인 일차만 일차 시험을 볼 수 있다 (FR-13)."""
    return status in (DayStatus.MEMORIZED, DayStatus.DONE)
