#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험지 생성과 채점 테스트 (PR-05, PR-06)
# 파일 위치: tests/test_exam.py
from __future__ import annotations

import random

import pytest
from conftest import answers_with_wrong, make_words

from smartvoca.core.exam import build_exam, grade_exam
from smartvoca.core.models import Word


# ── PR-05 시험지 생성 (FR-14) ───────────────────────────────
def test_일차_단어가_한_번씩_출제된다(default_words):
    targets = default_words[:20]
    exam = build_exam(targets, default_words, random.Random(1))
    assert len(exam.questions) == 20
    assert sorted(q.word for q in exam.questions) == sorted(w.word for w in targets)


def test_문제마다_정답이_하나이고_보기가_서로_다르다(default_words):
    meaning_of = {w.word: w.meaning for w in default_words}
    # 뜻이 같은 단어가 섞인 기본 단어장 전체로 여러 시드를 돌려 본다
    for seed in range(5):
        exam = build_exam(default_words, default_words, random.Random(seed))
        for question in exam.questions:
            assert len(question.choices) == 4
            assert len(set(question.choices)) == 4
            assert question.choices[question.answer_index] == meaning_of[question.word]
            assert question.choices.count(meaning_of[question.word]) == 1


def test_같은_시드는_같은_시험지를_만든다(default_words):
    targets = default_words[:20]
    first = build_exam(targets, default_words, random.Random(7))
    second = build_exam(targets, default_words, random.Random(7))
    assert first == second


def test_다른_시드는_문제_순서가_달라진다(default_words):
    targets = default_words[:20]
    orders = {
        tuple(q.word for q in build_exam(targets, default_words, random.Random(s)).questions)
        for s in range(5)
    }
    assert len(orders) > 1


def test_출제_대상_목록의_순서를_바꾸지_않는다(default_words):
    targets = list(default_words[:20])
    build_exam(targets, default_words, random.Random(1))
    assert targets == list(default_words[:20])


def test_뜻이_같은_단어가_있어도_보기가_겹치지_않는다():
    wordbook = [
        Word(0, "begin", "시작하다"),
        Word(1, "start", "시작하다"),
        Word(2, "c", "뜻3"),
        Word(3, "d", "뜻4"),
        Word(4, "e", "뜻5"),
    ]
    for seed in range(30):
        question = build_exam(wordbook[:1], wordbook, random.Random(seed)).questions[0]
        assert len(set(question.choices)) == 4
        assert question.choices.count("시작하다") == 1


def test_오답_단어가_1개여도_출제된다(default_words):
    exam = build_exam(default_words[5:6], default_words, random.Random(3))
    assert len(exam.questions) == 1
    assert len(exam.questions[0].choices) == 4


def test_출제할_단어가_없으면_거부한다(default_words):
    with pytest.raises(ValueError):
        build_exam([], default_words, random.Random(1))


def test_서로_다른_뜻이_4개_미만이면_거부한다():
    wordbook = make_words(3)
    with pytest.raises(ValueError):
        build_exam(wordbook, wordbook, random.Random(1))


# ── PR-06 채점 (FR-15, FR-16) ───────────────────────────────
def test_3개를_틀리면_17_대_20_이다(default_words):
    exam = build_exam(default_words[:20], default_words, random.Random(1))
    wrong_words = {q.word for q in exam.questions[:3]}
    result = grade_exam(exam, answers_with_wrong(exam, wrong_words))
    assert (result.correct_count, result.total) == (17, 20)
    assert {item.word for item in result.wrong_items} == wrong_words
    assert len(result.correct_words) == 17
    first = result.wrong_items[0]
    question = exam.questions[0]
    assert first.correct_meaning == question.choices[question.answer_index]
    assert first.chosen_meaning != first.correct_meaning


def test_모두_맞히면_틀린_문제가_없다(default_words):
    exam = build_exam(default_words[:20], default_words, random.Random(1))
    result = grade_exam(exam, [q.answer_index for q in exam.questions])
    assert result.correct_count == 20 and result.wrong_items == ()


def test_답하지_않은_문제가_있으면_채점하지_않는다(default_words):
    exam = build_exam(default_words[:20], default_words, random.Random(1))
    answers = [q.answer_index for q in exam.questions]
    answers[18] = None
    with pytest.raises(ValueError):
        grade_exam(exam, answers)


def test_답의_수가_다르거나_범위를_벗어나면_거부한다(default_words):
    exam = build_exam(default_words[:20], default_words, random.Random(1))
    with pytest.raises(ValueError):
        grade_exam(exam, [0] * 19)
    with pytest.raises(ValueError):
        grade_exam(exam, [4] + [0] * 19)
