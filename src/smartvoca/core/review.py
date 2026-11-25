#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 일차 학습에 섞을 복습 카드 고르기 (VOCA-FR-013)
# 파일 위치: src/smartvoca/core/review.py
"""그날의 카드 뒤에 "전날 외운 단어 일부"와 "자주 틀린 단어"를 덧붙인다.

반은 전날(N-1 일차) 단어에서 무작위로, 나머지는 오답 목록의 앞쪽(많이 틀린 순)에서 고른다.
한쪽이 모자라면 다른 쪽에서 채운다. 1일차는 전날이 없으므로 오답에서만 고른다.
그날의 단어와 겹치는 단어는 넣지 않는다 — 같은 카드를 두 번 보게 되기 때문이다.
"""
from __future__ import annotations

import random
from collections.abc import Sequence

from .models import StudyCard, StudyKind, Word


def pick_review_cards(
    today_words: Sequence[Word],
    previous_day_words: Sequence[Word],
    frequent_wrong_words: Sequence[Word],
    count: int,
    rng: random.Random,
) -> list[StudyCard]:
    if count <= 0:
        return []
    taken = {word.id for word in today_words}

    def fresh(words: Sequence[Word]) -> list[Word]:
        return [word for word in words if word.id not in taken]

    previous = fresh(previous_day_words)
    rng.shuffle(previous)
    wrong = fresh(frequent_wrong_words)  # 이미 많이 틀린 순으로 정렬되어 온다

    want_previous = (count + 1) // 2 if previous else 0
    cards: list[StudyCard] = []

    def take(words: list[Word], kind: StudyKind, limit: int) -> None:
        for word in words:
            if len(cards) >= limit:
                return
            if word.id not in taken:
                taken.add(word.id)
                cards.append(StudyCard(word, kind))

    take(previous, StudyKind.REVIEW, want_previous)
    take(wrong, StudyKind.WRONG, count)
    take(previous, StudyKind.REVIEW, count)  # 오답이 모자라면 전날 단어로 채운다
    return cards
