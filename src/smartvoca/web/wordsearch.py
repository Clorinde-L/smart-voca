#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 단어 목록 화면(S-07)의 검색 규칙
# 파일 위치: src/smartvoca/web/wordsearch.py
"""PyQt 의 WordFilterProxy 가 하던 일을 순수 함수로 옮겼다 (UD-06, FR-29)."""
from __future__ import annotations

from collections.abc import Sequence

from ..core.models import DAY_SIZE, Word


def day_of(word: Word) -> int:
    """단어가 속한 일차. 일차 편성(FR-07)과 같은 규칙이다."""
    return word.index // DAY_SIZE + 1


def filter_words(words: Sequence[Word], query: str) -> list[Word]:
    """검색어가 영단어나 뜻에 들어 있는 단어. 숫자만 넣으면 그 일차의 단어.

    대소문자는 가리지 않는다. 앞뒤 공백과 '일차' 글자는 무시한다 ('12일차' = '12').
    """
    query = query.strip().lower()
    if not query:
        return list(words)
    day_query = query.removesuffix("일차").strip()
    if day_query.isdigit():
        return [word for word in words if day_of(word) == int(day_query)]
    return [word for word in words if query in word.word.lower() or query in word.meaning.lower()]
