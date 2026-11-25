#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 화면 상태 규칙 테스트: 카드 완료, 시험 자동 넘김·단답형, 브라우저별 상태, 검색
# 파일 위치: tests/test_web_state.py
from __future__ import annotations

import random

import pytest
from conftest import make_words

from smartvoca.core.exam import build_exam
from smartvoca.core.models import Direction, ExamKind, QuestionFormat, StudyCard
from smartvoca.web.state import CardMode, CardStudy, ExamRun, StateStore, cheer, score_tone
from smartvoca.web.wordsearch import filter_words

WORDS = make_words(30)


def make_run(count: int, fmt: QuestionFormat = QuestionFormat.CHOICE) -> ExamRun:
    exam = build_exam(WORDS[:count], WORDS, random.Random(1), Direction.EN_KO, fmt)
    return ExamRun(ExamKind.DAY, "시험", exam, Direction.EN_KO, fmt, "/days/1", 1)


def test_카드를_모두_본_순간에만_한_번_완료된다():
    study = CardStudy.start(CardMode.DAY, "1일차", [StudyCard(w) for w in WORDS[:3]], 1)
    assert not study.finish_if_seen_all() and not study.unlocked
    study.deck.next()
    study.deck.next()
    assert study.finish_if_seen_all() and study.unlocked
    study.deck.prev()
    assert not study.finish_if_seen_all()  # 다시 저장하지 않는다


def test_이미_암기한_일차는_처음부터_시험이_켜져_있다():
    study = CardStudy.start(CardMode.DAY, "1일차", [StudyCard(w) for w in WORDS[:3]], 1, already_done=True)
    assert study.unlocked


def test_답을_고르면_다음_문제로_가고_마지막이면_안_푼_첫_문제로():
    run = make_run(3)
    run.choose(0)
    assert run.position == 1
    run.go_to(2)
    run.choose(1)
    assert run.position == 1 and not run.complete
    run.choose(2)  # 2번 문제를 풀면 3번으로 넘어간다
    assert run.complete and run.position == 2 and not run.focus_submit
    run.choose(0)  # 마지막 문제에서 모두 풀었으면 제출 버튼에 초점
    assert run.focus_submit and run.unanswered_numbers() == []


def test_단답형은_글로_답하고_비우면_답하지_않은_것이다():
    run = make_run(2, QuestionFormat.SHORT)
    run.write("  뜻  하나 ")
    assert run.answers[0] == "뜻 하나" and run.position == 1
    run.go_to(0)
    run.write("   ")
    assert run.answers[0] is None
    with pytest.raises(ValueError):
        run.choose(0)


def test_없는_보기는_거절하고_범위_밖_이동은_무시한다():
    run = make_run(2)
    with pytest.raises(ValueError):
        run.choose(9)
    run.go_to(5)
    assert run.position == 0
    with pytest.raises(ValueError):
        run.write("글")


def test_브라우저마다_상태가_따로이고_오래된_것부터_지운다():
    store = StateStore(max_states=2)
    a, b = store.get("a"), store.get("b")
    assert a is not b and store.get("a") is a
    store.get("c")  # b 가 가장 오래 안 쓰였다
    assert len(store) == 2 and store.get("a") is a
    assert store.get("b") is not b


@pytest.mark.parametrize("correct, tone", [(20, "success"), (18, "success"), (12, "primary"), (5, "warning")])
def test_점수_고리_색은_정답률을_따른다(correct, tone):
    assert score_tone(correct, 20) == tone


def test_격려_문구():
    assert "완벽" in cheer(20, 20)
    assert cheer(0, 0)


def test_검색은_영단어_뜻_일차로_찾는다():
    assert [w.word for w in filter_words(WORDS, "W1", 10)][:2] == ["w1", "w10"]
    assert [w.word for w in filter_words(WORDS, "뜻25", 10)] == ["w25"]
    assert [w.word for w in filter_words(WORDS, "2일차", 10)] == [f"w{i}" for i in range(11, 21)]
    assert len(filter_words(WORDS, "  ", 10)) == 30
