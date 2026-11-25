#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 테스트 공용 도우미와 픽스처
# 파일 위치: tests/conftest.py
# 2026-11-25 SQLite 전환(ADR-25)에 맞춰 세션 픽스처·시각 고정·답안 도우미를 바꿈
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from smartvoca.core.models import Exam, QuestionFormat, Word
from smartvoca.session import AppSession

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "toeic_words.csv"
# 기본 단어장 규모. 단어장을 바꾸면 여기만 고친다 (20개씩 나누면 106일차, 마지막 일차는 9개)
DEFAULT_WORD_COUNT = 2109
DEFAULT_DAY_COUNT = 106


def make_words(count: int) -> list[Word]:
    """w1, w2, … 와 '뜻1', '뜻2', … 로 된 단어 목록. id 는 1 부터."""
    return [Word(index=i, word=f"w{i + 1}", meaning=f"뜻{i + 1}", id=i + 1) for i in range(count)]


def write_csv(path: Path, lines: list[str], encoding: str = "utf-8-sig") -> Path:
    path.write_text("\n".join(lines) + "\n", encoding=encoding)
    return path


def small_csv(path: Path, count: int) -> Path:
    return write_csv(path, ["영단어,뜻", *[f"w{i + 1},뜻{i + 1}" for i in range(count)]])


class Clock:
    """테스트용 시계. advance 로 시간을 흘린다."""

    def __init__(self, start: datetime = datetime(2026, 11, 25, 9, 0, 0)):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def right_answers(exam: Exam, wrong_words: set[str] = frozenset()) -> list:
    """wrong_words 에 든 단어만 틀리고 나머지는 맞히는 답안 (형식별로)."""
    answers = []
    for question in exam.questions:
        wrong = question.word in wrong_words
        if question.format is QuestionFormat.SHORT:
            answers.append("틀린답xyz" if wrong else question.answer)
        else:
            index = question.answer_index
            answers.append((index + 1) % len(question.choices) if wrong else index)
    return answers


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def session(tmp_path, clock) -> AppSession:
    """기본 단어장 2,109개로 시작한 세션."""
    return AppSession.open(tmp_path / "voca.db", DEFAULT_CSV, random.Random(1), clock)


@pytest.fixture
def small_session(tmp_path, clock) -> AppSession:
    """단어 45개(20·20·5 → 3일차)로 시작한 세션."""
    csv_path = small_csv(tmp_path / "small.csv", 45)
    return AppSession.open(tmp_path / "small.db", csv_path, random.Random(1), clock)
