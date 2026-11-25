#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험지 생성·채점·가중 출제 테스트 (FR-14 ~ FR-16, VOCA-FR-021 ~ 025, NFR-04)
# 파일 위치: tests/test_exam.py
from __future__ import annotations

import random
from collections import Counter

import pytest
from conftest import make_words

from smartvoca.core.exam import (
    build_exam,
    grade_exam,
    is_short_answer_correct,
    meaning_parts,
    pick_weighted,
    word_weight,
)
from smartvoca.core.models import Direction, QuestionFormat, Word, WordStat


@pytest.fixture
def words():
    return make_words(40)


@pytest.mark.parametrize("direction", [Direction.EN_KO, Direction.KO_EN])
def test_4지선다는_정답이_하나이고_보기가_서로_다르다(words, direction):
    exam = build_exam(words[:20], words, random.Random(3), direction, QuestionFormat.CHOICE)
    assert len(exam.questions) == 20
    assert {q.word for q in exam.questions} == {w.word for w in words[:20]}
    for q in exam.questions:
        assert len(q.choices) == 4 and len(set(q.choices)) == 4
        assert q.choices[q.answer_index] == q.answer
        if direction is Direction.EN_KO:
            assert q.prompt == q.target.word and q.answer == q.target.meaning
        else:
            assert q.prompt == q.target.meaning and q.answer == q.target.word


def test_한영_보기에_뜻이_같은_다른_단어는_나오지_않는다():
    """뜻이 같은 단어가 보기에 섞이면 정답이 둘이 된다 (ADR-04)."""
    words = [Word(0, "big", "크다", 1), Word(1, "large", "크다", 2)] + [
        Word(i, f"x{i}", f"뜻{i}", i + 1) for i in range(2, 8)
    ]
    for seed in range(30):
        exam = build_exam(words[:1], words, random.Random(seed), Direction.KO_EN, QuestionFormat.CHOICE)
        assert "large" not in exam.questions[0].choices


def test_섞기는_문제마다_방향을_고른다(words):
    exam = build_exam(words, words, random.Random(5), Direction.MIX, QuestionFormat.CHOICE)
    directions = Counter(q.direction for q in exam.questions)
    assert set(directions) == {Direction.EN_KO, Direction.KO_EN}


def test_OX_는_절반쯤_맞는_짝을_보여_주고_정답_번호가_맞다(words):
    exam = build_exam(words, words, random.Random(7), Direction.EN_KO, QuestionFormat.OX)
    matches = 0
    for q in exam.questions:
        assert q.choices == ("O", "X")
        if q.shown == q.answer:
            assert q.answer_index == 0
            matches += 1
        else:
            assert q.answer_index == 1
    assert 10 <= matches <= 30


def test_단답형은_보기가_없다(words):
    exam = build_exam(words[:3], words, random.Random(1), Direction.EN_KO, QuestionFormat.SHORT)
    assert all(q.choices == () and q.answer_index is None for q in exam.questions)


def test_같은_시드면_같은_시험지(words):
    a = build_exam(words, words, random.Random(9), Direction.MIX, QuestionFormat.OX)
    b = build_exam(words, words, random.Random(9), Direction.MIX, QuestionFormat.OX)
    assert a == b


def test_뜻이_4개보다_적으면_4지선다를_만들_수_없다():
    words = make_words(3)
    with pytest.raises(ValueError):
        build_exam(words, words, random.Random(1))


def test_단어가_적어도_단답형은_만들_수_있다():
    words = make_words(1)
    assert len(build_exam(words, words, random.Random(1), question_format=QuestionFormat.SHORT).questions) == 1


# ── 단답형 채점 (ADR-27) ────────────────────────────────────
def test_뜻_조각을_나눈다():
    parts = meaning_parts("[명] 문제, 쟁점; (잡지의) 호 [동] 발행하다, 발급하다")
    assert {"문제", "쟁점", "잡지의호", "호", "발행하다", "발급하다"} <= parts


@pytest.mark.parametrize(
    "given, expected",
    [("문제", True), (" 쟁 점 ", True), ("호", True), ("발행하다", True), ("발행", False), ("", False)],
)
def test_영한_단답형은_뜻_하나만_맞혀도_정답(given, expected):
    word = Word(0, "issue", "[명] 문제, 쟁점; (잡지의) 호 [동] 발행하다, 발급하다", 1)
    exam = build_exam([word], [word], random.Random(1), Direction.EN_KO, QuestionFormat.SHORT)
    assert is_short_answer_correct(exam.questions[0], given) is expected


@pytest.mark.parametrize("given, expected", [("Agenda", True), ("  agenda ", True), ("agend", False)])
def test_한영_단답형은_철자가_같아야_정답(given, expected):
    word = Word(0, "agenda", "[명] 안건", 1)
    exam = build_exam([word], [word], random.Random(1), Direction.KO_EN, QuestionFormat.SHORT)
    assert is_short_answer_correct(exam.questions[0], given) is expected


# ── 채점 ───────────────────────────────────────────────────
def test_채점은_형식별로_맞힌_수와_틀린_문항을_돌려준다(words):
    exam = build_exam(words[:4], words, random.Random(2), Direction.EN_KO, QuestionFormat.CHOICE)
    answers = [q.answer_index for q in exam.questions]
    answers[1] = (answers[1] + 1) % 4
    result = grade_exam(exam, answers)
    assert (result.correct_count, result.total) == (3, 4)
    [wrong] = result.wrong_items
    assert wrong.question is exam.questions[1]
    assert wrong.given == exam.questions[1].choices[answers[1]]


def test_답하지_않은_문제가_있으면_채점하지_않는다(words):
    exam = build_exam(words[:2], words, random.Random(2))
    with pytest.raises(ValueError, match="2번"):
        grade_exam(exam, [0, None])
    short = build_exam(words[:1], words, random.Random(2), question_format=QuestionFormat.SHORT)
    with pytest.raises(ValueError):
        grade_exam(short, ["  "])


# ── 가중 출제 (VOCA-FR-022) ─────────────────────────────────
def test_가중치는_안_본_오래된_자주_틀린_단어가_크다():
    fresh = word_weight(None)
    recent = word_weight(WordStat(test_count=3, wrong_count=0, days_since_test=0))
    old = word_weight(WordStat(test_count=3, wrong_count=0, days_since_test=20))
    often_wrong = word_weight(WordStat(test_count=3, wrong_count=3, days_since_test=0))
    assert recent < old < fresh
    assert recent < often_wrong


def test_가중_출제는_겹치지_않고_문제_수만큼_고른다(words):
    picked = pick_weighted(words, {}, 10, random.Random(1))
    assert len(picked) == 10 and len({w.id for w in picked}) == 10
    assert len(pick_weighted(words, {}, 100, random.Random(1))) == len(words)


def test_가중_출제는_가중치_큰_단어를_더_자주_고른다(words):
    # 앞 20개는 최근에 맞힌 단어, 뒤 20개는 본 적 없는 단어
    stats = {w.id: WordStat(5, 0, 0.0) for w in words[:20]}
    counts = Counter()
    rng = random.Random(4)
    for _ in range(300):
        for word in pick_weighted(words, stats, 10, rng):
            counts["seen" if word.id <= 20 else "fresh"] += 1
    assert counts["fresh"] > counts["seen"] * 2
    assert counts["seen"] > 0  # 가중치가 작아도 뽑힐 수는 있다
