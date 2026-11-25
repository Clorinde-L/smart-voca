#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 진행 중인 카드 묶음·시험지·결과를 요청 사이에 들고 있는 화면 상태
# 파일 위치: src/smartvoca/web/state.py
"""웹은 요청마다 끊기므로 "지금 몇 번째 카드인지", "무엇을 골랐는지"를 어딘가에 들고 있어야 한다.

PyQt 에서는 화면 위젯이 이 값을 들고 있었다. 웹에서는 서버 메모리의 WebState 하나에 둔다 (ADR-20).
사용자가 1명이고 서버가 내 PC 에만 있으므로 하나면 충분하다.
저장하지 않으므로 서버를 끄면 사라진다 — "도중에 나간 암기·시험은 저장하지 않음"(ADR-12)과 같은 결과다.

이 모듈은 Flask 를 모른다. 그래서 브라우저 없이 규칙(자동 넘김, 제출 조건)만 따로 테스트할 수 있다.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from ..core.cards import CardDeck
from ..core.models import Exam, ExamResult, StartupNotice, Word, WrongEntry, WrongItem


# ── 카드 (S-02) ─────────────────────────────────────────────
class CardMode(Enum):
    DAY = "day"        # 일차 학습: 모두 보면 '시험 보기'가 켜진다
    REVIEW = "review"  # 복습: 하단 버튼 없음, 기록을 바꾸지 않는다 (FR-21)
    WRONG = "wrong"    # 오답 학습: 모두 보면 '오답 시험'이 켜진다


@dataclass
class CardStudy:
    """진행 중인 카드 묶음 하나."""

    mode: CardMode
    title: str
    deck: CardDeck
    day_no: int | None = None                      # 일차 학습·복습의 일차. 오답 학습이면 None
    wrong_info: Mapping[str, WrongEntry] = field(default_factory=dict)
    unlocked: bool = False                         # 시험 버튼이 켜졌는가 (모두 봤거나 이미 암기 완료)

    @classmethod
    def start(
        cls,
        mode: CardMode,
        title: str,
        words: Sequence[Word],
        day_no: int | None = None,
        already_done: bool = False,
        wrong_info: Mapping[str, WrongEntry] | None = None,
    ) -> CardStudy:
        """항상 첫 카드부터 시작한다 (요구사항 명세서 D-03)."""
        return cls(mode, title, CardDeck(words), day_no, wrong_info or {}, already_done)

    @property
    def has_action(self) -> bool:
        """하단에 시험 버튼이 있는 모드인가. 복습에는 없다 (FR-21)."""
        return self.mode is not CardMode.REVIEW

    def unlock_if_seen_all(self) -> bool:
        """카드를 모두 본 '그 순간'에만 True 를 돌려준다.

        부르는 쪽은 이때 한 번만 암기 완료를 저장한다(FR-12). 뒤로 갔다 와도 다시 저장하지 않는다.
        """
        if self.deck.seen_all and not self.unlocked:
            self.unlocked = True
            return True
        return False


# ── 시험 (S-03) ─────────────────────────────────────────────
class ExamMode(Enum):
    DAY = "day"
    WRONG = "wrong"


@dataclass
class ExamRun:
    """응시 중인 시험 하나. 정답 위치(answer_index)는 서버에만 있고 브라우저로 보내지 않는다."""

    mode: ExamMode
    title: str
    exam: Exam
    return_url: str                   # 그만두면 돌아갈 화면
    day_no: int | None = None
    answers: list[int | None] = field(default_factory=list)
    position: int = 0                 # 현재 문제 (0 부터)
    focus_submit: bool = False        # 모두 풀어서 제출 버튼에 초점을 둘 차례인가 (UD-05)

    def __post_init__(self) -> None:
        if not self.answers:
            self.answers = [None] * len(self.exam.questions)

    @property
    def total(self) -> int:
        return len(self.answers)

    @property
    def answered_count(self) -> int:
        return sum(answer is not None for answer in self.answers)

    @property
    def complete(self) -> bool:
        """제출은 모든 문제에 답해야 할 수 있다 (FR-15)."""
        return None not in self.answers

    def unanswered_numbers(self) -> list[int]:
        """답하지 않은 문제 번호 (사용자에게 보여 주므로 1 부터)."""
        return [i + 1 for i, answer in enumerate(self.answers) if answer is None]

    def go_to(self, position: int) -> None:
        if 0 <= position < self.total:
            self.position = position
        self.focus_submit = False

    def choose(self, choice_index: int) -> None:
        """현재 문제의 답을 고르고 다음 문제로 넘어간다 (UD-05).

        0.3초 기다림은 브라우저(app.js)가 한다. 서버에 왔을 때는 이미 기다린 뒤다.
        마지막 문제면 아직 안 푼 첫 문제로 가고, 모두 풀었으면 제출 버튼에 초점을 둔다.
        """
        if not 0 <= choice_index < len(self.exam.questions[self.position].choices):
            raise ValueError("없는 보기입니다")
        self.answers[self.position] = choice_index
        self.focus_submit = False
        if self.position < self.total - 1:
            self.position += 1
            return
        unanswered = self.unanswered_numbers()
        if unanswered:
            self.position = unanswered[0] - 1
        else:
            self.focus_submit = True


# ── 결과 (S-04) ─────────────────────────────────────────────
@dataclass(frozen=True)
class ResultView:
    """결과 화면에 그릴 내용. 기록은 이 값이 만들어지기 전에 이미 저장되어 있다 (FR-26)."""

    title: str
    status: str
    result: ExamResult
    wrong_note: str                       # 틀린 단어 표 제목 뒤에 붙는 설명
    graduated: tuple[str, ...] = ()       # 오답 시험에서 이번에 목록에서 빠진 단어
    next_day: int | None = None           # 일차 시험 뒤 바로 학습할 다음 일차
    is_wrong_exam: bool = False

    @property
    def wrong_items(self) -> tuple[WrongItem, ...]:
        return self.result.wrong_items


def cheer(correct: int, total: int) -> str:
    """점수에 맞춘 한 줄 격려 문구."""
    ratio = correct / total if total else 0
    if ratio == 1:
        return "모두 맞혔습니다. 완벽해요!"
    if ratio >= 0.9:
        return "거의 다 맞혔습니다. 아주 좋아요."
    if ratio >= 0.6:
        return "잘하고 있어요. 틀린 단어만 한 번 더 보면 됩니다."
    return "괜찮아요. 틀린 단어는 오답 학습에서 다시 볼 수 있습니다."


def score_tone(correct: int, total: int) -> str:
    """점수 고리 색: 90% 이상 초록, 60% 이상 남보라, 그 밖 주황 (UI/UX 설계서 §10)."""
    ratio = correct / total if total else 0
    if ratio >= 0.9:
        return "success"
    if ratio >= 0.6:
        return "primary"
    return "warning"


# ── 단어장 불러오기 (DL-01) ──────────────────────────────────
@dataclass(frozen=True)
class PendingImport:
    """검증을 통과해 '바꾸기'를 기다리는 단어장. 확인 페이지와 실제 교체 요청 사이에 들고 있는다."""

    file_name: str
    words: tuple[Word, ...]


# ── 전체 ────────────────────────────────────────────────────
@dataclass
class WebState:
    cards: CardStudy | None = None
    exam: ExamRun | None = None
    result: ResultView | None = None
    pending_import: PendingImport | None = None
    hide_meaning: bool = False                         # 카드 '뜻 가리고 외우기' (UD-04, 저장하지 않음)
    startup_notices: list[StartupNotice] = field(default_factory=list)  # 첫 화면에서 한 번 알린다
