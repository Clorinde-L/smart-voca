#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 일차 편성·일차 상태·카드 묶음·복습 카드 테스트 (FR-07, FR-08, FR-11, FR-12, VOCA-FR-011, 013)
# 파일 위치: tests/test_schedule_cards.py
from __future__ import annotations

import random

import pytest
from conftest import make_words

from smartvoca.core.cards import CardDeck
from smartvoca.core.models import DayStatus, StudyCard, StudyKind
from smartvoca.core.review import pick_review_cards
from smartvoca.core.schedule import all_day_statuses, build_days, can_take_exam, current_day, day_of, day_status


# ── 일차 편성 (VOCA-FR-011) ─────────────────────────────────
@pytest.mark.parametrize("count, size, expected_days, last_size", [(2000, 20, 100, 20), (2010, 20, 101, 10), (45, 10, 5, 5)])
def test_하루_학습량대로_나누고_마지막_일차는_남은_단어(count, size, expected_days, last_size):
    days = build_days(count, size)
    assert len(days) == expected_days
    assert days[-1].size == last_size
    assert sum(day.size for day in days) == count
    assert days[0].start == 0 and days[1].start == size


def test_단어가_없으면_일차도_없다():
    assert build_days(0, 20) == []
    with pytest.raises(ValueError):
        build_days(10, 0)


def test_순번이_속한_일차():
    assert day_of(0, 20) == 1 and day_of(19, 20) == 1 and day_of(20, 20) == 2


# ── 일차 상태 (ADR-26) ──────────────────────────────────────
def test_일차_상태는_단어_이력으로_정한다():
    words = make_words(4)
    assert day_status(words, set(), set()) is DayStatus.AVAILABLE
    assert day_status(words, {1, 2, 3}, set()) is DayStatus.AVAILABLE      # 한 단어라도 안 봤으면
    assert day_status(words, {1, 2, 3, 4}, set()) is DayStatus.MEMORIZED
    assert day_status(words, {1, 2, 3, 4}, {1, 2, 3, 4}) is DayStatus.DONE
    assert day_status([], {1}, {1}) is DayStatus.AVAILABLE


def test_현재_일차는_안_끝낸_가장_앞_일차():
    words = make_words(60)
    days = build_days(60, 20)
    tested = {w.id for w in words[20:40]}  # 2일차만 끝냄 (잠금 없음, ADR-21)
    statuses = all_day_statuses(words, days, tested, tested)
    assert statuses == [DayStatus.AVAILABLE, DayStatus.DONE, DayStatus.AVAILABLE]
    assert current_day(statuses) == 1
    assert current_day([DayStatus.DONE, DayStatus.DONE]) is None
    assert can_take_exam(DayStatus.MEMORIZED) and not can_take_exam(DayStatus.AVAILABLE)


# ── 카드 묶음 (FR-11, FR-12) ────────────────────────────────
def test_모든_카드를_한_번씩_봐야_다_본_것이다():
    deck = CardDeck([StudyCard(w) for w in make_words(3)])
    assert not deck.can_prev and not deck.seen_all
    deck.next()
    deck.next()
    assert deck.seen_all and not deck.can_next
    deck.prev()
    assert deck.seen_all  # 뒤로 가도 그대로
    assert deck.current.word.word == "w2"


def test_빈_카드_묶음은_만들_수_없다():
    with pytest.raises(ValueError):
        CardDeck([])


# ── 복습 카드 (VOCA-FR-013) ─────────────────────────────────
def test_복습_카드는_전날_단어와_자주_틀린_단어를_반씩_섞는다():
    words = make_words(60)
    today, previous, wrong = words[20:40], words[:20], [words[45], words[46], words[47]]
    cards = pick_review_cards(today, previous, wrong, 4, random.Random(1))
    kinds = [card.kind for card in cards]
    assert kinds.count(StudyKind.REVIEW) == 2 and kinds.count(StudyKind.WRONG) == 2
    assert [c.word for c in cards if c.kind is StudyKind.WRONG] == wrong[:2]  # 많이 틀린 순서 그대로
    assert all(c.word in previous for c in cards if c.kind is StudyKind.REVIEW)


def test_한쪽이_모자라면_다른_쪽으로_채우고_그날_단어와_겹치지_않는다():
    words = make_words(40)
    today, previous = words[20:40], words[:20]
    cards = pick_review_cards(today, previous, [words[25]], 5, random.Random(1))  # 오답은 오늘 단어뿐
    assert len(cards) == 5 and all(c.kind is StudyKind.REVIEW for c in cards)
    first_day = pick_review_cards(words[:20], [], [words[30], words[31]], 4, random.Random(1))
    assert [c.word for c in first_day] == [words[30], words[31]]  # 1일차는 전날이 없다
    assert pick_review_cards(today, previous, [], 0, random.Random(1)) == []
