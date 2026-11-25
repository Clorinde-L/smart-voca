#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 모든 계층이 함께 쓰는 자료형, 열거형, 상수
# 파일 위치: src/smartvoca/core/models.py
"""자료형 정의 (프로세스 설계서 §1.3, 데이터 설계서 §3).

2026-11-25 SQLite 전환(ADR-25)으로 파일 기록용 자료형(Progress, DayRecord …)을 없애고
시험 형식·방향(ADR-27), 설정(VOCA-FR-061), 통계(VOCA-FR-031~033) 자료형을 넣었다.
모두 frozen 이다: 기록을 바꾸는 일은 DB 가 하고, 여기 값은 읽은 결과·계산 결과일 뿐이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

CHOICE_COUNT = 4       # 4지선다
GRADUATE_STREAK = 3    # 오답 시험에서 연속으로 이만큼 맞히면 오답 목록에서 뺀다
DEFAULT_USER_ID = 1    # 로그인을 만들기 전까지 모든 기록은 이 사용자 것이다 (ADR-30)

MAX_WORD_LENGTH = 100
MAX_MEANING_LENGTH = 300


@dataclass(frozen=True)
class Word:
    """단어장의 한 줄. index 는 단어장 안의 순번(0 부터), id 는 DB 의 번호."""

    index: int
    word: str
    meaning: str
    id: int = 0


@dataclass(frozen=True)
class DayRange:
    """일차의 단어 순번 범위 [start, end)."""

    day_no: int
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


class DayStatus(Enum):
    # 2026-11-25 잠금(LOCKED) 폐지: 모든 일차를 자유롭게 학습한다 (ADR-21)
    AVAILABLE = "학습 전"
    MEMORIZED = "암기 완료"
    DONE = "완료"


# ── 설정 (VOCA-FR-011, 061) ─────────────────────────────────
class Direction(Enum):
    """출제 방향 (VOCA-FR-023). MIX 는 문제마다 둘 중 하나를 무작위로 고른다."""

    EN_KO = "en_ko"
    KO_EN = "ko_en"
    MIX = "mix"

    @property
    def label(self) -> str:
        return {"en_ko": "영→한", "ko_en": "한→영", "mix": "섞기"}[self.value]


class QuestionFormat(Enum):
    """출제 형식 (VOCA-FR-024)."""

    CHOICE = "choice"
    SHORT = "short"
    OX = "ox"

    @property
    def label(self) -> str:
        return {"choice": "4지선다", "short": "단답형", "ox": "OX"}[self.value]


@dataclass(frozen=True)
class Settings:
    day_size: int = 20                       # 하루 학습량 (일차당 단어 수)
    review_count: int = 4                    # 일차 학습에 섞을 복습 카드 수 (VOCA-FR-013)
    exam_count: int = 20                     # 실력 시험 문제 수 기본값 (VOCA-FR-021)
    exam_direction: Direction = Direction.EN_KO
    exam_format: QuestionFormat = QuestionFormat.CHOICE


# 설정값의 허용 범위 (core/validation.py 가 검사한다)
DAY_SIZE_RANGE = (5, 100)
REVIEW_COUNT_RANGE = (0, 20)
EXAM_COUNT_RANGE = (1, 100)


# ── 암기 ───────────────────────────────────────────────────
class StudyKind(Enum):
    """암기 이력의 종류 (VOCA-FR-013, 014)."""

    NEW = "new"          # 그 일차의 단어
    REVIEW = "review"    # 전날 단어를 섞은 복습 카드
    WRONG = "wrong"      # 자주 틀린 단어를 섞은 카드, 또는 오답 학습

    @property
    def label(self) -> str:
        return {"new": "", "review": "복습", "wrong": "오답"}[self.value]


@dataclass(frozen=True)
class StudyCard:
    word: Word
    kind: StudyKind = StudyKind.NEW


# ── 시험 ───────────────────────────────────────────────────
class ExamKind(Enum):
    DAY = "day"          # 일차 시험: 그 일차 단어 전부
    WRONG = "wrong"      # 오답 시험: 오답 목록 전부
    RANDOM = "random"    # 실력 시험: 문제 수를 정하고 가중 무작위 출제 (VOCA-FR-021, 022)

    @property
    def label(self) -> str:
        return {"day": "일차 시험", "wrong": "오답 시험", "random": "실력 시험"}[self.value]


@dataclass(frozen=True)
class Question:
    """문제 1개. direction 은 MIX 가 아니라 이 문제에 실제로 정해진 방향이다.

    - CHOICE: choices 4개 중 answer_index 가 정답
    - OX: shown 이 prompt 의 짝인지 고른다. choices 는 ("O", "X"), 맞는 짝이면 answer_index 0
    - SHORT: choices 가 비어 있고 answer 를 직접 입력한다
    """

    target: Word
    direction: Direction
    format: QuestionFormat
    prompt: str
    answer: str
    choices: tuple[str, ...] = ()
    answer_index: int | None = None
    shown: str | None = None

    @property
    def word(self) -> str:
        return self.target.word


@dataclass(frozen=True)
class Exam:
    questions: tuple[Question, ...]


Answer = int | str | None   # 보기 번호(CHOICE·OX) 또는 입력한 글(SHORT). 답하지 않았으면 None


@dataclass(frozen=True)
class ItemResult:
    """채점한 문항 1개. given 은 사용자가 고르거나 입력한 것을 글로 옮긴 것이다."""

    question: Question
    given: str
    correct: bool


@dataclass(frozen=True)
class ExamResult:
    items: tuple[ItemResult, ...]

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def correct_count(self) -> int:
        return sum(item.correct for item in self.items)

    @property
    def wrong_items(self) -> tuple[ItemResult, ...]:
        return tuple(item for item in self.items if not item.correct)

    @property
    def correct_word_ids(self) -> tuple[int, ...]:
        return tuple(item.question.target.id for item in self.items if item.correct)

    @property
    def wrong_word_ids(self) -> tuple[int, ...]:
        return tuple(item.question.target.id for item in self.items if not item.correct)


@dataclass(frozen=True)
class WordStat:
    """가중 출제에 쓰는 단어별 시험 이력 요약 (VOCA-FR-022)."""

    test_count: int = 0
    wrong_count: int = 0
    days_since_test: float | None = None   # 시험 본 적 없으면 None


# ── 오답 목록 ───────────────────────────────────────────────
@dataclass(frozen=True)
class WrongRecord:
    wrong_count: int = 0       # 누적 오답 횟수 (목록에서 빠져도 유지)
    streak: int = 0            # 오답 시험 연속 정답 횟수 (0 ~ GRADUATE_STREAK-1)
    in_list: bool = False


@dataclass(frozen=True)
class WrongEntry:
    """오답 목록 1건."""

    word: Word
    wrong_count: int
    streak: int


# ── 단어장 가져오기 ─────────────────────────────────────────
class ImportMode(Enum):
    ADD = "add"           # 있는 단어는 건너뛰고 새 단어만 더한다 (ADR-28)
    REPLACE = "replace"   # 단어와 학습 기록을 모두 지우고 새로 시작한다


@dataclass(frozen=True)
class ValidationIssue:
    """단어장 검증 위반 1건. line_no 는 파일의 줄 번호(헤더가 1), 파일 전체 문제면 None."""

    rule: str
    line_no: int | None
    message: str


@dataclass(frozen=True)
class ParsedWordbook:
    """읽은 CSV. duplicate_lines 는 파일 안에서 앞줄과 겹쳐 버린 줄 번호."""

    entries: tuple[tuple[str, str], ...]
    duplicate_lines: tuple[int, ...] = ()


@dataclass(frozen=True)
class ImportReport:
    added: int
    skipped_existing: int      # 단어장에 이미 있어 건너뛴 수
    skipped_in_file: int       # 파일 안에서 겹쳐 건너뛴 수


# ── 진도·통계 (VOCA-FR-031~033) ─────────────────────────────
@dataclass(frozen=True)
class ProgressSummary:
    current_day: int | None    # 모든 일차를 끝냈으면 None
    total_days: int
    done_days: int
    memorized_days: int        # 암기만 하고 시험이 남은 일차
    wrong_list_size: int
    memorized_words: int       # 암기 이력이 있는 단어 수
    total_words: int


@dataclass(frozen=True)
class TrendPoint:
    """정답률 추이의 한 점: 회차 하나 또는 날짜 하나."""

    label: str
    total: int
    correct: int

    @property
    def ratio(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass(frozen=True)
class FrequentWrong:
    word: str
    meaning: str
    wrong_count: int
    test_count: int


@dataclass(frozen=True)
class LearningStats:
    summary: ProgressSummary
    exam_count: int
    overall_ratio: float | None            # 시험을 본 적 없으면 None
    by_session: tuple[TrendPoint, ...]     # 최근 회차부터가 아니라 오래된 것부터
    by_date: tuple[TrendPoint, ...]
    frequent_wrong: tuple[FrequentWrong, ...]
