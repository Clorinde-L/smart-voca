#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 오답 목록 규칙 테스트 (FR-17, FR-25, 요구사항 명세서 D-05, D-06)
# 파일 위치: tests/test_progress.py
# 2026-11-25 기록이 SQLite 로 옮겨 가면서(ADR-25) 일차 기록 테스트는 test_schedule_cards 의 계산 테스트로 옮김
from __future__ import annotations

from conftest import make_words

from smartvoca.core.models import (
    Direction,
    ExamKind,
    ExamResult,
    ItemResult,
    Question,
    QuestionFormat,
    WrongRecord,
)
from smartvoca.core.progress import apply_exam_to_wrong_records

WORDS = make_words(5)


def result(correct=(), wrong=()) -> ExamResult:
    """맞힌·틀린 단어 번호만으로 채점 결과를 만든다."""

    def item(word_id: int, ok: bool) -> ItemResult:
        word = WORDS[word_id - 1]
        question = Question(word, Direction.EN_KO, QuestionFormat.CHOICE, word.word, word.meaning)
        return ItemResult(question, "답", ok)

    return ExamResult(tuple([item(i, True) for i in correct] + [item(i, False) for i in wrong]))


def test_틀린_단어는_오답_횟수가_늘고_목록에_오른다():
    changed, graduated = apply_exam_to_wrong_records({}, result(correct=[1], wrong=[2]), ExamKind.DAY)
    assert changed == {2: WrongRecord(1, 0, True)}  # 맞힌 단어는 바뀌지 않는다
    assert graduated == []


def test_이미_목록에_있는_단어를_또_틀리면_횟수만_는다():
    records = {2: WrongRecord(1, 2, True)}
    changed, _ = apply_exam_to_wrong_records(records, result(wrong=[2]), ExamKind.RANDOM)
    assert changed[2] == WrongRecord(2, 0, True)


def test_일차_시험에서_맞힌_것은_연속_정답으로_세지_않는다():
    records = {1: WrongRecord(1, 0, True)}
    changed, _ = apply_exam_to_wrong_records(records, result(correct=[1]), ExamKind.DAY)
    assert changed == {}


def test_오답_시험에서_3번_연속_맞히면_목록에서_빠지고_누적은_유지된다():
    records = {1: WrongRecord(4, 0, True)}
    for expected_streak in (1, 2):
        changed, graduated = apply_exam_to_wrong_records(records, result(correct=[1]), ExamKind.WRONG)
        assert changed[1] == WrongRecord(4, expected_streak, True) and graduated == []
        records = changed
    changed, graduated = apply_exam_to_wrong_records(records, result(correct=[1]), ExamKind.WRONG)
    assert changed[1] == WrongRecord(4, 0, False)
    assert graduated == [1]


def test_오답_시험에서_틀리면_연속_정답이_0_으로():
    records = {1: WrongRecord(1, 2, True)}
    changed, _ = apply_exam_to_wrong_records(records, result(wrong=[1]), ExamKind.WRONG)
    assert changed[1] == WrongRecord(2, 0, True)


def test_목록에서_빠진_단어를_다시_틀리면_다시_오른다():
    records = {1: WrongRecord(3, 0, False)}
    changed, _ = apply_exam_to_wrong_records(records, result(wrong=[1]), ExamKind.DAY)
    assert changed[1] == WrongRecord(4, 0, True)
