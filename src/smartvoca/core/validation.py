#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 사용자가 입력한 단어·설정값 검사 (VOCA-FR-001, 002, 061)
# 파일 위치: src/smartvoca/core/validation.py
"""입력 검사는 화면이 아니라 여기서 한다. 웹 폼이든 CSV 든 같은 규칙을 쓰기 위함이다."""
from __future__ import annotations

from collections.abc import Mapping

from .models import (
    DAY_SIZE_RANGE,
    EXAM_COUNT_RANGE,
    MAX_MEANING_LENGTH,
    MAX_WORD_LENGTH,
    REVIEW_COUNT_RANGE,
    Direction,
    QuestionFormat,
    Settings,
)


def clean_text(text: str) -> str:
    """앞뒤 공백을 지우고, 안의 줄바꿈·연속 공백은 공백 하나로."""
    return " ".join(text.split())


def check_word_input(word: str, meaning: str) -> list[str]:
    """단어 등록·수정 입력의 문제 목록. 비어 있으면 통과다 (중복 검사는 DB 가 한다)."""
    problems = []
    if not word:
        problems.append("영단어를 입력해 주세요.")
    elif len(word) > MAX_WORD_LENGTH:
        problems.append(f"영단어는 {MAX_WORD_LENGTH}자 이하로 입력해 주세요.")
    if not meaning:
        problems.append("뜻을 입력해 주세요.")
    elif len(meaning) > MAX_MEANING_LENGTH:
        problems.append(f"뜻은 {MAX_MEANING_LENGTH}자 이하로 입력해 주세요.")
    return problems


def _int_in_range(raw: str | None, bounds: tuple[int, int], name: str, problems: list[str]) -> int | None:
    low, high = bounds
    try:
        value = int(str(raw).strip())
    except ValueError:
        problems.append(f"{name}은(는) 숫자로 입력해 주세요.")
        return None
    if not low <= value <= high:
        problems.append(f"{name}은(는) {low}~{high} 사이로 입력해 주세요.")
        return None
    return value


def parse_settings(form: Mapping[str, str], current: Settings) -> tuple[Settings, list[str]]:
    """설정 폼을 읽는다. 문제가 있으면 (현재 설정, 문제 목록)을 돌려준다 (VOCA-FR-061)."""
    problems: list[str] = []
    day_size = _int_in_range(form.get("day_size"), DAY_SIZE_RANGE, "하루 학습량", problems)
    review_count = _int_in_range(form.get("review_count"), REVIEW_COUNT_RANGE, "복습 카드 수", problems)
    exam_count = _int_in_range(form.get("exam_count"), EXAM_COUNT_RANGE, "시험 문제 수", problems)
    direction = parse_direction(form.get("exam_direction"))
    question_format = parse_format(form.get("exam_format"))
    if direction is None:
        problems.append("출제 방향을 골라 주세요.")
    if question_format is None:
        problems.append("출제 형식을 골라 주세요.")
    if problems:
        return current, problems
    return Settings(day_size, review_count, exam_count, direction, question_format), []


def parse_direction(raw: str | None) -> Direction | None:
    try:
        return Direction(raw)
    except ValueError:
        return None


def parse_format(raw: str | None) -> QuestionFormat | None:
    try:
        return QuestionFormat(raw)
    except ValueError:
        return None
