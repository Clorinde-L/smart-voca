#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 암기 카드 묶음의 진행 상태 관리 (PR-04)
# 파일 위치: src/smartvoca/core/cards.py
"""일차 학습·복습·오답 학습이 함께 쓰는 카드 묶음.

CardDeck 은 학습 기록을 모른다. "모두 봤을 때 무엇을 할지"는 부르는 화면이 정한다.
저장되지 않으므로 화면을 나갔다 오면 첫 카드부터 다시 시작한다 (요구사항 명세서 D-03).
"""
from __future__ import annotations

from collections.abc import Sequence

from .models import StudyCard


class CardDeck:
    """2026-11-25 카드 한 장이 Word 에서 StudyCard(단어 + 복습·오답 표시)로 바뀌었다 (VOCA-FR-013)."""

    def __init__(self, cards: Sequence[StudyCard]):
        if not cards:
            raise ValueError("카드로 볼 단어가 없습니다")
        self._words = tuple(cards)
        self._position = 0
        self._seen = {0}  # 첫 카드는 만들자마자 본 것으로 친다

    @property
    def current(self) -> StudyCard:
        return self._words[self._position]

    @property
    def position(self) -> int:
        """현재 위치 (1 부터)."""
        return self._position + 1

    @property
    def total(self) -> int:
        return len(self._words)

    @property
    def can_next(self) -> bool:
        return self._position < len(self._words) - 1

    @property
    def can_prev(self) -> bool:
        return self._position > 0

    @property
    def cards(self) -> tuple[StudyCard, ...]:
        return self._words

    @property
    def seen_all(self) -> bool:
        """모든 카드를 한 번 이상 봤는가. 한 번 참이 되면 뒤로 가도 참이다 (FR-12)."""
        return len(self._seen) == len(self._words)

    def next(self) -> bool:
        if not self.can_next:
            return False
        self._position += 1
        self._seen.add(self._position)
        return True

    def prev(self) -> bool:
        if not self.can_prev:
            return False
        self._position -= 1
        self._seen.add(self._position)
        return True
