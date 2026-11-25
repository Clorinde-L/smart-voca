#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 화면이 쓰는 유일한 창구: 로직 호출 순서와 저장 시점을 한곳에서 관리
# 파일 위치: src/smartvoca/session.py
"""응용 계층 (시스템 구조 §4.2, ADR-05).

"채점 → 이력 저장 → 오답 목록 반영" 같은 순서를 화면마다 쓰면 빠뜨리기 쉽다.
그 순서를 여기에 모아 두고, 화면은 메서드 하나만 부르게 한다.
기록을 바꾸는 메서드는 한 DB 트랜잭션 안에서 끝낸다 — 중간에 실패하면 아무것도 남지 않는다.

2026-11-25 저장소를 JSON 파일에서 SQLite 로 바꿨다 (ADR-25). 메서드마다 연결을 새로 연다:
서버(gunicorn)는 요청을 여러 스레드에서 받을 수 있고, SQLite 연결은 스레드끼리 나눠 쓰면 안 된다.
"""
from __future__ import annotations

import random
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .core import exam as exam_logic
from .core import progress as progress_logic
from .core import review, schedule
from .core.models import (
    DEFAULT_USER_ID,
    Answer,
    DayRange,
    DayStatus,
    Direction,
    Exam,
    ExamKind,
    ExamResult,
    ImportMode,
    ImportReport,
    LearningStats,
    ParsedWordbook,
    ProgressSummary,
    QuestionFormat,
    Settings,
    StudyCard,
    StudyKind,
    ValidationIssue,
    Word,
    WrongEntry,
)
from .core.validation import check_word_input, clean_text
from .storage import db, repository, wordbook_csv


class WordInputError(Exception):
    """단어 등록·수정 입력이 규칙에 맞지 않음. problems 를 그대로 사용자에게 보여 준다."""

    def __init__(self, problems: Sequence[str]):
        self.problems = tuple(problems)
        super().__init__(" ".join(problems))


@dataclass(frozen=True)
class SubmitOutcome:
    result: ExamResult
    graduated: tuple[str, ...]      # 이번 오답 시험으로 오답 목록에서 빠진 단어


@dataclass(frozen=True)
class _Progress:
    """한 번 읽은 진도 계산 재료. 메서드 하나 안에서만 쓴다."""

    words: list[Word]
    settings: Settings
    days: list[DayRange]
    statuses: list[DayStatus]
    studied_ids: set[int]


class AppSession:
    def __init__(
        self,
        db_path: Path,
        user_id: int = DEFAULT_USER_ID,
        rng: random.Random | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self._db_path = Path(db_path)
        self._user_id = user_id
        self._rng = rng or random.Random()
        self._clock = clock or datetime.now

    @classmethod
    def open(
        cls,
        db_path: Path,
        default_csv_path: Path | None,
        rng: random.Random | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> AppSession:
        """DB 를 준비하고 세션을 만든다. 테이블이 없으면 만들고, 처음이면 기본 단어장을 넣는다 (NFR-003)."""
        session = cls(db_path, rng=rng, clock=clock)
        db.init_db(session._db_path, default_csv_path, session._now())
        return session

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    def _tx(self):
        return db.transaction(self._db_path)

    def _read_progress(self, conn: sqlite3.Connection) -> _Progress:
        words = repository.list_words(conn)
        settings = repository.get_settings(conn, self._user_id)
        days = schedule.build_days(len(words), settings.day_size)
        studied = repository.studied_word_ids(conn, self._user_id)
        tested = repository.day_tested_word_ids(conn, self._user_id)
        statuses = schedule.all_day_statuses(words, days, studied, tested)
        return _Progress(words, settings, days, statuses, studied)

    # ── 조회 ────────────────────────────────────────────────
    def words(self) -> list[Word]:
        with self._tx() as conn:
            return repository.list_words(conn)

    def settings(self) -> Settings:
        with self._tx() as conn:
            return repository.get_settings(conn, self._user_id)

    def days(self) -> list[tuple[DayRange, DayStatus, list[Word]]]:
        """일차마다 (범위, 상태, 단어들)."""
        with self._tx() as conn:
            p = self._read_progress(conn)
        return [(day, status, p.words[day.start : day.end]) for day, status in zip(p.days, p.statuses)]

    def day(self, day_no: int) -> tuple[DayStatus, list[Word]] | None:
        """한 일차의 상태와 단어. 없는 일차면 None."""
        with self._tx() as conn:
            p = self._read_progress(conn)
        if not 1 <= day_no <= len(p.days):
            return None
        day = p.days[day_no - 1]
        return p.statuses[day_no - 1], p.words[day.start : day.end]

    def summary(self) -> ProgressSummary:
        with self._tx() as conn:
            p = self._read_progress(conn)
            wrong_size = len(repository.wrong_list_rows(conn, self._user_id))
        return self._summarize(p, wrong_size)

    @staticmethod
    def _summarize(p: _Progress, wrong_size: int) -> ProgressSummary:
        known_ids = {word.id for word in p.words}
        return ProgressSummary(
            current_day=schedule.current_day(p.statuses),
            total_days=len(p.days),
            done_days=sum(status is DayStatus.DONE for status in p.statuses),
            memorized_days=sum(status is DayStatus.MEMORIZED for status in p.statuses),
            wrong_list_size=wrong_size,
            memorized_words=len(p.studied_ids & known_ids),
            total_words=len(p.words),
        )

    def wrong_list(self) -> list[WrongEntry]:
        with self._tx() as conn:
            return self._wrong_list(conn)

    def _wrong_list(self, conn: sqlite3.Connection) -> list[WrongEntry]:
        word_of = {word.id: word for word in repository.list_words(conn)}
        return [
            WrongEntry(word_of[word_id], wrong_count, streak)
            for word_id, wrong_count, streak in repository.wrong_list_rows(conn, self._user_id)
            if word_id in word_of
        ]

    def wrong_words(self) -> list[Word]:
        """오답 목록 순서대로의 단어 (오답 카드·오답 시험의 대상)."""
        return [entry.word for entry in self.wrong_list()]

    # ── 암기 (VOCA-FR-011 ~ 014) ────────────────────────────
    def day_cards(self, day_no: int) -> list[StudyCard]:
        """그 일차의 카드 + 복습 카드(전날 단어 일부, 자주 틀린 단어) (VOCA-FR-013)."""
        with self._tx() as conn:
            p = self._read_progress(conn)
            if not 1 <= day_no <= len(p.days):
                raise ValueError(f"{day_no}일차는 없습니다")
            wrong = [entry.word for entry in self._wrong_list(conn)]
        day = p.days[day_no - 1]
        today = p.words[day.start : day.end]
        previous = []
        if day_no > 1:
            prev = p.days[day_no - 2]
            # "전날 외운 단어"이므로 전날 단어 중 암기 이력이 있는 것만 섞는다
            previous = [word for word in p.words[prev.start : prev.end] if word.id in p.studied_ids]
        extra = review.pick_review_cards(today, previous, wrong, p.settings.review_count, self._rng)
        return [StudyCard(word, StudyKind.NEW) for word in today] + extra

    def complete_memorize(self, day_no: int | None, cards: Sequence[StudyCard]) -> None:
        """카드를 모두 봤을 때 부른다. 본 카드마다 암기 이력을 남긴다 (FR-12, VOCA-FR-014).

        일차 학습이면 day_no 를, 오답 학습이면 None 을 준다.
        """
        if not cards:
            return
        with self._tx() as conn:
            repository.log_study(conn, self._user_id, cards, day_no, self._now())

    # ── 시험 (VOCA-FR-021 ~ 026) ────────────────────────────
    def build_exam(
        self,
        kind: ExamKind,
        direction: Direction,
        question_format: QuestionFormat,
        day_no: int | None = None,
        count: int | None = None,
    ) -> Exam:
        """시험지를 만든다. 일차 시험은 그 일차 단어 전부, 오답 시험은 오답 목록 전부,
        실력 시험은 외운 단어(없으면 전체)에서 count 개를 가중 무작위로 고른다."""
        with self._tx() as conn:
            p = self._read_progress(conn)
            if kind is ExamKind.DAY:
                if day_no is None or not 1 <= day_no <= len(p.days):
                    raise ValueError(f"{day_no}일차는 없습니다")
                if not schedule.can_take_exam(p.statuses[day_no - 1]):
                    raise ValueError(f"{day_no}일차는 카드를 모두 본 뒤에 시험을 볼 수 있습니다")
                day = p.days[day_no - 1]
                targets = p.words[day.start : day.end]
            elif kind is ExamKind.WRONG:
                targets = [entry.word for entry in self._wrong_list(conn)]
                if not targets:
                    raise ValueError("오답 목록이 비어 있습니다")
            else:
                pool = [word for word in p.words if word.id in p.studied_ids] or p.words
                if not pool:
                    raise ValueError("단어장에 단어가 없습니다")
                stats = repository.word_stats(conn, self._user_id, self._now())
                targets = exam_logic.pick_weighted(pool, stats, count or p.settings.exam_count, self._rng)
        return exam_logic.build_exam(targets, p.words, self._rng, direction, question_format)

    def submit_exam(
        self,
        kind: ExamKind,
        exam: Exam,
        answers: Sequence[Answer],
        direction: Direction,
        question_format: QuestionFormat,
        day_no: int | None = None,
    ) -> SubmitOutcome:
        """채점 → 문항 이력 저장 → 오답 목록 반영을 한 트랜잭션으로 (FR-16 ~ FR-19, FR-25, VOCA-FR-026)."""
        result = exam_logic.grade_exam(exam, answers)
        with self._tx() as conn:
            repository.save_exam(
                conn, self._user_id, kind, day_no, direction, question_format, result, self._now()
            )
            ids = set(result.correct_word_ids) | set(result.wrong_word_ids)
            records = repository.wrong_records(conn, self._user_id, ids)
            changed, graduated_ids = progress_logic.apply_exam_to_wrong_records(records, result, kind)
            # 시험 도중 지운 단어는 오답 기록을 남기지 않는다 (외래 키가 없는 단어)
            existing = {word.id for word in repository.list_words(conn)}
            repository.save_wrong_records(
                conn, self._user_id, {i: r for i, r in changed.items() if i in existing}
            )
        word_of = {item.question.target.id: item.question.word for item in result.items}
        return SubmitOutcome(result, tuple(word_of[i] for i in graduated_ids))

    # ── 단어 등록·수정·삭제 (VOCA-FR-001, 002) ──────────────
    def get_word(self, word_id: int) -> Word | None:
        return next((word for word in self.words() if word.id == word_id), None)

    def add_word(self, word: str, meaning: str) -> Word:
        word, meaning = clean_text(word), clean_text(meaning)
        problems = check_word_input(word, meaning)
        if problems:
            raise WordInputError(problems)
        try:
            with self._tx() as conn:
                word_id = repository.add_word(conn, word, meaning, self._now())
        except repository.DuplicateWordError:
            raise WordInputError([f'"{word}" 은(는) 이미 등록된 단어입니다.']) from None
        return self.get_word(word_id)

    def update_word(self, word_id: int, word: str, meaning: str) -> None:
        word, meaning = clean_text(word), clean_text(meaning)
        problems = check_word_input(word, meaning)
        if problems:
            raise WordInputError(problems)
        try:
            with self._tx() as conn:
                repository.update_word(conn, word_id, word, meaning, self._now())
        except repository.DuplicateWordError:
            raise WordInputError([f'"{word}" 은(는) 이미 등록된 단어입니다.']) from None
        except repository.WordNotFoundError:
            raise LookupError(word_id) from None

    def delete_word(self, word_id: int) -> None:
        try:
            with self._tx() as conn:
                repository.delete_word(conn, word_id)
        except repository.WordNotFoundError:
            raise LookupError(word_id) from None

    # ── CSV 가져오기·내보내기 (VOCA-FR-003, FR-05, FR-06) ───
    @staticmethod
    def check_wordbook_upload(data: bytes) -> tuple[ParsedWordbook | None, list[ValidationIssue]]:
        """올린 CSV 를 메모리에서 읽고 검증만 한다. 아무것도 바꾸지 않는다 (FR-02).

        확인(check)과 반영(import)을 나눈 이유: 그 사이에 화면이 확인 페이지를 보여 줘야 한다.
        """
        text, issue = wordbook_csv.decode_csv_bytes(data)
        if issue is not None:
            return None, [issue]
        return wordbook_csv.parse_wordbook_text(text)

    def import_wordbook(self, parsed: ParsedWordbook, mode: ImportMode) -> ImportReport:
        """추가: 이미 있는 영단어는 건너뜀. 바꾸기: 단어·학습 기록을 모두 지우고 새로 (ADR-28)."""
        with self._tx() as conn:
            if mode is ImportMode.REPLACE:
                repository.delete_all_words_and_history(conn)
            added, skipped = repository.add_words_skipping_existing(conn, parsed.entries, self._now())
        return ImportReport(added, skipped, len(parsed.duplicate_lines))

    def export_wordbook_csv(self) -> bytes:
        return wordbook_csv.encode_csv(wordbook_csv.wordbook_csv_text(self.words()))

    def export_wrong_list_csv(self) -> bytes:
        return wordbook_csv.encode_csv(wordbook_csv.wrong_list_csv_text(self.wrong_list()))

    # ── 설정 (VOCA-FR-061, 062) ─────────────────────────────
    def save_settings(self, settings: Settings) -> None:
        with self._tx() as conn:
            repository.save_settings(conn, self._user_id, settings, self._now())

    # ── 통계 (VOCA-FR-031 ~ 034) ────────────────────────────
    def stats(self, session_limit: int = 20, date_limit: int = 14, top: int = 10) -> LearningStats:
        """통계는 모두 DB 이력에서 계산한다. 화면에 값을 써 넣지 않는다 (VOCA-FR-034)."""
        with self._tx() as conn:
            p = self._read_progress(conn)
            summary = self._summarize(p, len(repository.wrong_list_rows(conn, self._user_id)))
            exam_count, total, correct = repository.exam_totals(conn, self._user_id)
            return LearningStats(
                summary=summary,
                exam_count=exam_count,
                overall_ratio=correct / total if total else None,
                by_session=tuple(repository.trend_by_session(conn, self._user_id, session_limit)),
                by_date=tuple(repository.trend_by_date(conn, self._user_id, date_limit)),
                frequent_wrong=tuple(repository.frequent_wrong(conn, self._user_id, top)),
            )
