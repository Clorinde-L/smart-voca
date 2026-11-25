#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 일차 편성·상태 판정·카드 진행 테스트 (PR-02, PR-03, PR-04)
# 파일 위치: tests/test_schedule_cards.py
from __future__ import annotations

import pytest
from conftest import make_words

from smartvoca.core.cards import CardDeck
from smartvoca.core.models import DayRecord, DayStatus, Progress, WordRecord
from smartvoca.core.schedule import (
    build_days,
    can_take_exam,
    current_day,
    day_status,
    progress_summary,
    reviewable_days,
)


# ── PR-02 일차 편성 (FR-07) ─────────────────────────────────
def test_2000_단어를_100일차로_나눈다():
    days = build_days(2000)
    assert len(days) == 100
    assert (days[0].start, days[0].end) == (0, 20)
    assert (days[99].day_no, days[99].start, days[99].end) == (100, 1980, 2000)


def test_나누어떨어지지_않으면_마지막_일차가_짧다():
    days = build_days(2010)
    assert len(days) == 101
    assert (days[100].start, days[100].end) == (2000, 2010)


def test_모든_단어가_한_일차에만_속한다():
    days = build_days(45)
    assert sum(day.end - day.start for day in days) == 45
    assert all(prev.end == nxt.start for prev, nxt in zip(days, days[1:]))


def test_기본_단어장의_일차에_단어가_겹치지_않는다(default_words):
    seen = set()
    for day in build_days(len(default_words)):
        day_words = {w.word for w in default_words[day.start : day.end]}
        assert len(day_words) == day.end - day.start
        assert len(day_words) == 20 or day.day_no == len(build_days(len(default_words)))  # 마지막 일차만 20개 미만
        assert not seen & day_words
        seen |= day_words
    assert len(seen) == len(default_words)


@pytest.mark.parametrize("word_count, day_size", [(0, 20), (10, 0)])
def test_잘못된_크기는_거부한다(word_count, day_size):
    with pytest.raises(ValueError):
        build_days(word_count, day_size)


# ── PR-03 일차 상태 (FR-08, FR-09, FR-13, FR-20) ─────────────
def test_처음에는_모든_일차가_학습_전이다():
    """잠금 없음 (ADR-21): 앞 일차를 끝내지 않아도 학습할 수 있다."""
    progress = Progress()
    assert day_status(progress, 1) is DayStatus.AVAILABLE
    assert day_status(progress, 50) is DayStatus.AVAILABLE
    assert current_day(progress, 100) == 1


def test_시험을_제출하면_오늘의_학습이_다음_일차로_간다():
    progress = Progress(days={1: DayRecord(memorized=True, tested=True)})
    assert day_status(progress, 1) is DayStatus.DONE
    assert day_status(progress, 2) is DayStatus.AVAILABLE
    assert current_day(progress, 100) == 2


def test_암기만_끝낸_일차는_시험만_남는다():
    progress = Progress(days={1: DayRecord(memorized=True)})
    assert day_status(progress, 1) is DayStatus.MEMORIZED
    assert day_status(progress, 2) is DayStatus.AVAILABLE
    assert current_day(progress, 100) == 1  # 시험을 내야 완료다
    assert can_take_exam(progress, 1)
    assert not can_take_exam(progress, 2)
    assert reviewable_days(progress, 100) == [1]


def test_모든_일차를_끝내면_현재_일차가_없다():
    progress = Progress(days={d: DayRecord(True, True) for d in (1, 2, 3)})
    assert current_day(progress, 3) is None


def test_진도_현황을_집계한다():
    progress = Progress(
        days={1: DayRecord(True, True), 2: DayRecord(True, True), 3: DayRecord(True)},
        words={
            "a": WordRecord(2, 0, True),
            "b": WordRecord(1, 0, False),
            "c": WordRecord(1, 1, True),
        },
    )
    summary = progress_summary(progress, 100)
    assert (summary.current_day, summary.total_days) == (3, 100)
    assert (summary.done_days, summary.wrong_list_size) == (2, 2)


# ── PR-04 카드 진행 (FR-10 ~ FR-12) ─────────────────────────
def test_마지막_카드를_보는_순간_모두_본_것이_된다():
    deck = CardDeck(make_words(20))
    for _ in range(18):
        deck.next()
    assert deck.position == 19 and not deck.seen_all
    deck.next()
    assert deck.position == 20 and deck.seen_all


def test_양_끝에서는_움직이지_않는다():
    deck = CardDeck(make_words(3))
    assert not deck.can_prev and deck.prev() is False
    deck.next()
    deck.next()
    assert not deck.can_next and deck.next() is False
    assert deck.position == 3


def test_카드가_1장이면_바로_모두_본_것이다():
    assert CardDeck(make_words(1)).seen_all


def test_뒤로_가도_모두_본_상태가_유지된다():
    deck = CardDeck(make_words(3))
    deck.next()
    deck.next()
    deck.prev()
    assert deck.seen_all and deck.current.word == "w2"


def test_카드_순서는_받은_순서와_같다():
    words = make_words(3)
    deck = CardDeck(words)
    seen = [deck.current]
    while deck.next():
        seen.append(deck.current)
    assert seen == words and deck.total == 3


def test_빈_단어_목록으로는_만들_수_없다():
    with pytest.raises(ValueError):
        CardDeck([])
