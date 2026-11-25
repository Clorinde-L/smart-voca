#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 모든 계층이 함께 쓰는 자료형, 열거형, 상수
# 파일 위치: src/smartvoca/core/models.py
"""자료형 정의 (프로세스 설계서 §1.3, 데이터 설계서 §3.2).

값 객체는 frozen 으로 만들어 실수로 바뀌지 않게 하고,
학습 기록(Progress, DayRecord, WordRecord)만 바뀔 수 있게 둔다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

DAY_SIZE = 20          # 일차당 단어 수 (기획서 v1.3: 고정)
CHOICE_COUNT = 4       # 4지선다
GRADUATE_STREAK = 3    # 오답 시험에서 연속으로 이만큼 맞히면 오답 목록에서 뺀다


@dataclass(frozen=True)
class Word:
    """단어장의 한 줄. index 는 단어장 내 순번(0 부터)."""

    index: int
    word: str
    meaning: str


@dataclass(frozen=True)
class DayRange:
    """일차의 단어 순번 범위 [start, end)."""

    day_no: int
    start: int
    end: int


class DayStatus(Enum):
    # 2026-11-25 잠금(LOCKED) 폐지: 모든 일차를 자유롭게 학습한다 (ADR-21)
    AVAILABLE = "학습 전"
    MEMORIZED = "암기 완료"
    DONE = "완료"


@dataclass
class DayRecord:
    memorized: bool = False
    tested: bool = False


@dataclass
class WordRecord:
    wrong_count: int = 0       # 누적 오답 횟수 (목록에서 빠져도 유지)
    streak: int = 0            # 오답 시험 연속 정답 횟수 (0 ~ GRADUATE_STREAK-1)
    in_wrong_list: bool = False


@dataclass
class Progress:
    """학습 기록 전체. days 의 키는 일차 번호, words 의 키는 영단어."""

    days: dict[int, DayRecord] = field(default_factory=dict)
    words: dict[str, WordRecord] = field(default_factory=dict)


@dataclass(frozen=True)
class ProgressSummary:
    current_day: int | None    # 모든 일차를 끝냈으면 None
    total_days: int
    done_days: int
    wrong_list_size: int


@dataclass(frozen=True)
class ValidationIssue:
    """단어장 검증 위반 1건. line_no 는 파일의 줄 번호(헤더가 1), 파일 전체 문제면 None."""

    rule: str
    line_no: int | None
    message: str


@dataclass(frozen=True)
class Question:
    word: str
    choices: tuple[str, ...]
    answer_index: int


@dataclass(frozen=True)
class Exam:
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class WrongItem:
    word: str
    correct_meaning: str
    chosen_meaning: str


@dataclass(frozen=True)
class ExamResult:
    total: int
    correct_count: int
    correct_words: tuple[str, ...]
    wrong_items: tuple[WrongItem, ...]


@dataclass(frozen=True)
class WrongEntry:
    """오답 목록 1건."""

    word: str
    wrong_count: int
    streak: int


class LoadStatus(Enum):
    OK = "ok"
    NEW = "new"
    CORRUPT = "corrupt"


@dataclass(frozen=True)
class LoadResult:
    progress: Progress
    status: LoadStatus
    backup_path: Path | None = None


class WordbookSource(Enum):
    DEFAULT = "default"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ActiveWordbook:
    """시작할 때 고른 단어장. words 가 비어 있으면 기본 단어장도 읽지 못한 것이다."""

    words: tuple[Word, ...]
    source: WordbookSource
    issues: tuple[ValidationIssue, ...] = ()
    invalid_backup_path: Path | None = None


class NoticeKind(Enum):
    PROGRESS_CORRUPT = "progress_corrupt"
    WORDBOOK_INVALID = "wordbook_invalid"


@dataclass(frozen=True)
class StartupNotice:
    """시작할 때 사용자에게 알릴 일 (UI/UX 설계서 DL-04)."""

    kind: NoticeKind
    backup_path: Path | None
