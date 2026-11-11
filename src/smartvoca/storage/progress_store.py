#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 학습 기록(progress.json) 저장·복원·손상 처리 (PR-10, PR-11)
# 파일 위치: src/smartvoca/storage/progress_store.py
"""학습 기록 저장소.

형식은 데이터 설계서 §4.4 를 따른다. JSON 객체의 키는 문자열만 되므로
일차 번호는 저장할 때 문자열로, 읽을 때 정수로 바꾼다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..core.models import (
    GRADUATE_STREAK,
    DayRecord,
    LoadResult,
    LoadStatus,
    Progress,
    WordRecord,
)
from .fileutil import atomic_write_text, move_aside

SCHEMA_VERSION = 1
PROGRESS_FILENAME = "progress.json"


class _CorruptProgress(Exception):
    """기록 파일의 내용이 형식에 맞지 않음."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise _CorruptProgress(reason)


def _is_int(value: object) -> bool:
    # bool 은 int 의 하위 타입이라 True 가 1 로 통과하지 않게 따로 걸러 낸다
    return isinstance(value, int) and not isinstance(value, bool)


def _progress_to_dict(progress: Progress) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "days": {
            str(day_no): {"memorized": record.memorized, "tested": record.tested}
            for day_no, record in sorted(progress.days.items())
        },
        "words": {
            word: {
                "wrong_count": record.wrong_count,
                "streak": record.streak,
                "in_wrong_list": record.in_wrong_list,
            }
            for word, record in progress.words.items()
        },
    }


def _progress_from_dict(data: object) -> Progress:
    """형식을 검사하며 Progress 로 바꾼다. 어긋나면 손상으로 본다 (데이터 설계서 §5.6)."""
    _require(isinstance(data, dict), "최상위가 객체가 아님")
    _require(data.get("schema_version") == SCHEMA_VERSION, "지원하지 않는 schema_version")
    raw_days, raw_words = data.get("days"), data.get("words")
    _require(isinstance(raw_days, dict), "days 가 객체가 아님")
    _require(isinstance(raw_words, dict), "words 가 객체가 아님")

    days = {}
    for key, value in raw_days.items():
        _require(key.isdecimal() and int(key) >= 1, f"일차 키가 올바르지 않음: {key}")
        _require(isinstance(value, dict), f"{key}일차 기록이 객체가 아님")
        memorized, tested = value.get("memorized"), value.get("tested")
        _require(isinstance(memorized, bool), f"{key}일차 memorized 가 불리언이 아님")
        _require(isinstance(tested, bool), f"{key}일차 tested 가 불리언이 아님")
        days[int(key)] = DayRecord(memorized=memorized, tested=tested)

    words = {}
    for word, value in raw_words.items():
        _require(bool(word), "단어 키가 비어 있음")
        _require(isinstance(value, dict), f"{word} 기록이 객체가 아님")
        wrong_count, streak = value.get("wrong_count"), value.get("streak")
        in_wrong_list = value.get("in_wrong_list")
        _require(_is_int(wrong_count) and wrong_count >= 1, f"{word} wrong_count 범위 오류")
        _require(
            _is_int(streak) and 0 <= streak < GRADUATE_STREAK, f"{word} streak 범위 오류"
        )
        _require(isinstance(in_wrong_list, bool), f"{word} in_wrong_list 가 불리언이 아님")
        words[word] = WordRecord(
            wrong_count=wrong_count, streak=streak, in_wrong_list=in_wrong_list
        )
    return Progress(days=days, words=words)


class ProgressStore:
    """base_dir 아래의 progress.json 을 읽고 쓴다. 경로를 받아서 쓰므로 테스트는 임시 폴더를 넘긴다."""

    def __init__(self, base_dir: Path):
        self._path = Path(base_dir) / PROGRESS_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def save(self, progress: Progress) -> None:
        """기록 전체를 안전하게 쓴다 (FR-26, NFR-06). 디스크 오류는 OSError 로 올라간다."""
        text = json.dumps(_progress_to_dict(progress), ensure_ascii=False, indent=2)
        atomic_write_text(self._path, text + "\n", "utf-8")

    def load(self) -> LoadResult:
        """기록을 읽는다. 없으면 NEW, 읽을 수 없으면 파일을 보존하고 CORRUPT (FR-27, FR-28)."""
        if not self._path.exists():
            return LoadResult(Progress(), LoadStatus.NEW)
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            progress = _progress_from_dict(data)
        except (json.JSONDecodeError, UnicodeDecodeError, _CorruptProgress):
            backup_path = move_aside(self._path, "corrupt")
            return LoadResult(Progress(), LoadStatus.CORRUPT, backup_path)
        return LoadResult(progress, LoadStatus.OK)
