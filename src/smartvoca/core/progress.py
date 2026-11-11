#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 학습 기록을 바꾸는 규칙: 암기 완료, 시험 결과 반영, 오답 목록, 정합화
# 파일 위치: src/smartvoca/core/progress.py
"""학습 기록 변경 규칙 (PR-04, PR-07, PR-08, PR-09, PR-11, PR-12).

이 모듈의 함수는 기록을 바꾸기만 하고 저장하지 않는다.
저장은 부른 쪽(AppSession)이 한다 — 그래야 이 규칙들을 파일 없이 테스트할 수 있다.
"""
from __future__ import annotations

from collections.abc import Sequence

from .models import (
    GRADUATE_STREAK,
    DayRecord,
    ExamResult,
    Progress,
    Word,
    WordRecord,
    WrongEntry,
)
from .schedule import can_take_exam


def new_progress() -> Progress:
    """빈 학습 기록 (1일차만 열린 초기 상태)."""
    return Progress()


def mark_memorized(progress: Progress, day_no: int) -> None:
    """일차를 암기 완료로 기록한다 (FR-12)."""
    progress.days.setdefault(day_no, DayRecord()).memorized = True


def apply_day_exam_result(progress: Progress, day_no: int, result: ExamResult) -> None:
    """일차 시험 결과를 반영한다 (FR-17, FR-18, FR-19).

    틀린 단어만 기록을 바꾼다. 맞힌 단어의 연속 정답 횟수는 건드리지 않는다 —
    연속 정답은 오답 시험에서만 센다 (요구사항 명세서 D-05).
    """
    if not can_take_exam(progress, day_no):
        raise ValueError(f"{day_no}일차는 아직 시험을 볼 수 없습니다")
    for item in result.wrong_items:
        record = progress.words.setdefault(item.word, WordRecord())
        record.wrong_count += 1
        record.streak = 0
        record.in_wrong_list = True
    # 점수와 관계없이 완료 처리한다. 재시험이면 이미 True 다.
    progress.days.setdefault(day_no, DayRecord()).tested = True


def apply_wrong_exam_result(progress: Progress, result: ExamResult) -> list[str]:
    """오답 시험 결과를 반영하고, 이번에 오답 목록에서 빠진 단어를 돌려준다 (FR-25)."""
    graduated = []
    for word in result.correct_words:
        record = progress.words.get(word)
        if record is None or not record.in_wrong_list:
            continue  # 오답 목록에 없는 단어는 연속 정답을 세지 않는다
        record.streak += 1
        if record.streak >= GRADUATE_STREAK:
            record.in_wrong_list = False
            record.streak = 0
            graduated.append(word)  # 누적 오답 횟수는 그대로 둔다 (D-06)
    for item in result.wrong_items:
        record = progress.words.setdefault(item.word, WordRecord())
        record.wrong_count += 1
        record.streak = 0
        record.in_wrong_list = True
    return graduated


def sorted_wrong_list(progress: Progress, wordbook: Sequence[Word]) -> list[WrongEntry]:
    """오답 목록을 오답 횟수 내림차순, 같으면 단어장 순서로 돌려준다 (FR-22)."""
    entries = []
    for word in wordbook:  # 단어장 순서로 훑으므로 정렬 뒤에도 같은 횟수끼리는 단어장 순서다
        record = progress.words.get(word.word)
        if record is not None and record.in_wrong_list:
            entries.append(WrongEntry(word.word, record.wrong_count, record.streak))
    entries.sort(key=lambda entry: -entry.wrong_count)  # sort 는 안정 정렬
    return entries


def reconcile_progress(
    progress: Progress, wordbook: Sequence[Word], total_days: int
) -> Progress:
    """기록을 현재 단어장에 맞춘다. 맞지 않는 항목만 버리거나 고친다 (데이터 설계서 §5.5)."""
    known_words = {word.word for word in wordbook}
    days = {}
    for day_no, record in progress.days.items():
        if not 1 <= day_no <= total_days:
            continue
        days[day_no] = DayRecord(
            memorized=record.memorized or record.tested,  # 시험을 봤으면 암기도 끝난 것
            tested=record.tested,
        )
    words = {}
    for word, record in progress.words.items():
        if word not in known_words:
            continue
        words[word] = WordRecord(
            wrong_count=record.wrong_count,
            streak=record.streak if record.in_wrong_list else 0,
            in_wrong_list=record.in_wrong_list,
        )
    return Progress(days=days, words=words)
