#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 단어 관리 화면(S-07)의 검색 규칙 (FR-29, VOCA-FR-004)
# 파일 위치: src/smartvoca/web/wordsearch.py
"""PyQt 의 WordFilterProxy 가 하던 일을 순수 함수로 옮겼다 (UD-06)."""
from __future__ import annotations

from collections.abc import Sequence

from ..core.models import Word
from ..core.schedule import day_of


def filter_words(words: Sequence[Word], query: str, day_size: int) -> list[Word]:
    """검색어가 영단어나 뜻에 들어 있는 단어. 숫자만 넣으면 그 일차의 단어.

    대소문자는 가리지 않는다. 앞뒤 공백과 '일차' 글자는 무시한다 ('12일차' = '12').
    """
    query = query.strip().lower()
    if not query:
        return list(words)
    day_query = query.removesuffix("일차").strip()
    if day_query.isdigit():
        return [word for word in words if day_of(word.index, day_size) == int(day_query)]
    return [word for word in words if query in word.word.lower() or query in word.meaning.lower()]
