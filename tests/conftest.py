#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 테스트 공용 도우미와 픽스처
# 파일 위치: tests/conftest.py
from __future__ import annotations

from pathlib import Path

import pytest

from smartvoca.core.models import Exam, ExamResult, Word, WrongItem
from smartvoca.storage.wordbook_csv import read_wordbook_csv

DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "toeic_words_2000.csv"


def make_words(count: int) -> list[Word]:
    """w1, w2, … 와 '뜻1', '뜻2', … 로 된 단어 목록."""
    return [Word(index=i, word=f"w{i + 1}", meaning=f"뜻{i + 1}") for i in range(count)]


def make_result(correct: list[str] = (), wrong: list[str] = ()) -> ExamResult:
    """맞힌 단어·틀린 단어 이름만으로 채점 결과를 만든다."""
    return ExamResult(
        total=len(correct) + len(wrong),
        correct_count=len(correct),
        correct_words=tuple(correct),
        wrong_items=tuple(WrongItem(word, "정답", "오답") for word in wrong),
    )


def answers_with_wrong(exam: Exam, wrong_words: set[str]) -> list[int]:
    """wrong_words 에 든 단어만 틀리고 나머지는 맞히는 답안."""
    return [
        (q.answer_index + 1) % len(q.choices) if q.word in wrong_words else q.answer_index
        for q in exam.questions
    ]


def write_csv(path: Path, lines: list[str], encoding: str = "utf-8-sig") -> Path:
    path.write_text("\n".join(lines) + "\n", encoding=encoding)
    return path


@pytest.fixture(scope="session")
def default_words() -> list[Word]:
    words, issues = read_wordbook_csv(DEFAULT_CSV)
    assert issues == []
    return words
