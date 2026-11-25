#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 웹 화면 상태 규칙 테스트: 카드 잠금 해제, 시험 자동 넘김·제출 조건, 단어 검색
# 파일 위치: tests/test_web_state.py
from __future__ import annotations

import pytest
from conftest import make_words

from smartvoca.core.models import Exam, Question
from smartvoca.web.state import CardMode, CardStudy, ExamMode, ExamRun, cheer, score_tone
from smartvoca.web.wordsearch import day_of, filter_words


def make_run(count: int) -> ExamRun:
    questions = tuple(Question(f"w{i}", ("가", "나", "다", "라"), 0) for i in range(count))
    return ExamRun(ExamMode.DAY, "시험", Exam(questions), "/cards", day_no=1)


# ── 카드 ────────────────────────────────────────────────────
def test_카드를_모두_본_순간에만_한_번_잠금이_풀린다():
    study = CardStudy.start(CardMode.DAY, "1일차 학습", make_words(3), day_no=1)
    assert not study.unlock_if_seen_all()
    study.deck.next()
    assert not study.unlock_if_seen_all()
    study.deck.next()
    assert study.unlock_if_seen_all()          # 이때 한 번 암기 완료를 저장한다
    study.deck.prev()
    assert not study.unlock_if_seen_all()      # 다시 저장하지 않는다
    assert study.unlocked


def test_이미_암기한_일차는_처음부터_잠금이_풀려_있다():
    study = CardStudy.start(CardMode.DAY, "1일차 학습", make_words(3), 1, already_done=True)
    assert study.unlocked
    assert not study.unlock_if_seen_all()


def test_복습에는_시험_버튼이_없다():
    assert not CardStudy.start(CardMode.REVIEW, "복습", make_words(2), 1).has_action
    assert CardStudy.start(CardMode.WRONG, "오답", make_words(2)).has_action


# ── 시험 ────────────────────────────────────────────────────
def test_답을_고르면_다음_문제로_간다():
    run = make_run(3)
    run.choose(2)
    assert run.answers == [2, None, None]
    assert run.position == 1
    assert not run.complete


def test_마지막_문제에_답하면_안_푼_첫_문제로_간다():
    run = make_run(4)
    run.go_to(3)
    run.choose(0)
    assert run.position == 0
    assert run.unanswered_numbers() == [1, 2, 3]


def test_모두_풀면_제출_버튼에_초점을_둔다():
    run = make_run(2)
    run.choose(1)
    run.choose(1)
    assert run.complete
    assert run.focus_submit
    assert run.position == 1      # 마지막 문제에 머문다
    run.go_to(0)
    assert not run.focus_submit   # 직접 옮겨 가면 초점 표시는 풀린다


def test_돌아가_답을_고칠_수_있다():
    run = make_run(3)
    run.choose(1)
    run.go_to(0)
    run.choose(3)
    assert run.answers[0] == 3


def test_없는_보기나_범위_밖_이동은_무시하거나_거절한다():
    run = make_run(2)
    with pytest.raises(ValueError):
        run.choose(4)
    run.go_to(9)
    assert run.position == 0


# ── 결과 문구 ───────────────────────────────────────────────
@pytest.mark.parametrize(
    ("correct", "tone"), [(20, "success"), (18, "success"), (17, "primary"), (12, "primary"), (11, "warning")]
)
def test_점수_고리_색은_정답률을_따른다(correct, tone):
    assert score_tone(correct, 20) == tone


def test_격려_문구():
    assert cheer(20, 20).startswith("모두 맞혔습니다")
    assert cheer(0, 20).startswith("괜찮아요")


# ── 단어 검색 (FR-29) ───────────────────────────────────────
def test_단어가_속한_일차():
    words = make_words(45)
    assert [day_of(words[i]) for i in (0, 19, 20, 44)] == [1, 1, 2, 3]


def test_영단어나_뜻으로_찾고_대소문자를_가리지_않는다():
    words = make_words(45)
    assert [w.word for w in filter_words(words, " W4 ")] == ["w4", "w40", "w41", "w42", "w43", "w44", "w45"]
    assert [w.word for w in filter_words(words, "뜻12")] == ["w12"]


def test_숫자나_N일차로_찾으면_그_일차_단어():
    words = make_words(45)
    assert len(filter_words(words, "2")) == 20
    assert filter_words(words, "3일차") == words[40:]
    assert filter_words(words, "99") == []


def test_빈_검색어는_전체():
    words = make_words(5)
    assert filter_words(words, "   ") == words
