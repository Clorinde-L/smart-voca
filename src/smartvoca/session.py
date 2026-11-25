#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - UI 가 쓰는 유일한 창구: 로직 호출 순서와 저장 시점을 한곳에서 관리
# 파일 위치: src/smartvoca/session.py
"""응용 계층 (시스템 구조 §4.2, ADR-05).

"채점 → 기록 반영 → 저장" 같은 순서를 화면마다 쓰면 저장을 빠뜨리기 쉽다.
그 순서를 여기에 모아 두고, 화면은 메서드 하나만 부르게 한다.
기록을 바꾸는 메서드는 돌아오기 전에 저장까지 끝낸다 (FR-26).
"""
from __future__ import annotations

import random
from collections.abc import Sequence
from pathlib import Path

from .core import exam as exam_logic
from .core import progress as progress_logic
from .core import schedule
from .core.models import (
    DayRange,
    DayStatus,
    Exam,
    ExamResult,
    LoadStatus,
    NoticeKind,
    Progress,
    ProgressSummary,
    StartupNotice,
    ValidationIssue,
    Word,
    WordbookSource,
    WrongEntry,
)
from .storage import wordbook_csv
from .storage.progress_store import ProgressStore


class WordbookLoadError(Exception):
    """기본 단어장을 읽을 수 없어 프로그램을 시작할 수 없음."""

    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(issue.message for issue in issues))


class AppSession:
    def __init__(
        self,
        base_dir: Path,
        words: Sequence[Word],
        wordbook_source: WordbookSource,
        progress: Progress,
        store: ProgressStore,
        rng: random.Random,
        startup_notices: Sequence[StartupNotice] = (),
    ):
        self._base_dir = Path(base_dir)
        self._words = tuple(words)
        self._wordbook_source = wordbook_source
        self._days = schedule.build_days(len(self._words))
        self._progress = progress
        self._store = store
        self._rng = rng
        self._startup_notices = tuple(startup_notices)

    @classmethod
    def open(
        cls, base_dir: Path, default_csv_path: Path, rng: random.Random | None = None
    ) -> AppSession:
        """시작 순서: 단어장 → 일차 편성 → 기록 복원 → 정합화 (프로세스 설계서 §4).

        정합화에 단어장이 필요하므로 단어장을 먼저 읽는다.
        """
        notices = []
        active = wordbook_csv.load_active_wordbook(base_dir, default_csv_path)
        if active.invalid_backup_path is not None:
            notices.append(
                StartupNotice(NoticeKind.WORDBOOK_INVALID, active.invalid_backup_path)
            )
        if not active.words:
            raise WordbookLoadError(active.issues)

        store = ProgressStore(base_dir)
        loaded = store.load()
        if loaded.status is LoadStatus.CORRUPT:
            notices.append(StartupNotice(NoticeKind.PROGRESS_CORRUPT, loaded.backup_path))
        total_days = len(schedule.build_days(len(active.words)))
        progress = progress_logic.reconcile_progress(
            loaded.progress, active.words, total_days
        )
        return cls(
            base_dir=base_dir,
            words=active.words,
            wordbook_source=active.source,
            progress=progress,
            store=store,
            rng=rng or random.Random(),
            startup_notices=notices,
        )

    # ── 조회 ────────────────────────────────────────────────
    @property
    def words(self) -> tuple[Word, ...]:
        return self._words

    @property
    def wordbook_source(self) -> WordbookSource:
        return self._wordbook_source

    @property
    def days(self) -> list[DayRange]:
        return list(self._days)

    @property
    def startup_notices(self) -> tuple[StartupNotice, ...]:
        return self._startup_notices

    def summary(self) -> ProgressSummary:
        return schedule.progress_summary(self._progress, len(self._days))

    def day_status(self, day_no: int) -> DayStatus:
        return schedule.day_status(self._progress, day_no)

    def day_words(self, day_no: int) -> list[Word]:
        day = self._days[day_no - 1]
        return list(self._words[day.start : day.end])

    def reviewable_days(self) -> list[int]:
        return schedule.reviewable_days(self._progress, len(self._days))

    def wrong_list(self) -> list[WrongEntry]:
        return progress_logic.sorted_wrong_list(self._progress, self._words)

    def wrong_words(self) -> list[Word]:
        """오답 목록 순서대로의 단어 (오답 카드·오답 시험의 대상)."""
        word_of = {word.word: word for word in self._words}
        return [word_of[entry.word] for entry in self.wrong_list()]

    # ── 일차 학습·시험 ──────────────────────────────────────
    def complete_memorize(self, day_no: int) -> None:
        """일차의 카드를 모두 봤을 때 부른다 (FR-12)."""
        if not 1 <= day_no <= len(self._days):
            raise ValueError(f"{day_no}일차는 없습니다")
        progress_logic.mark_memorized(self._progress, day_no)
        self._store.save(self._progress)

    def build_day_exam(self, day_no: int) -> Exam:
        if not schedule.can_take_exam(self._progress, day_no):
            raise ValueError(f"{day_no}일차는 아직 시험을 볼 수 없습니다")
        return exam_logic.build_exam(self.day_words(day_no), self._words, self._rng)

    def submit_day_exam(
        self, day_no: int, exam: Exam, answers: Sequence[int | None]
    ) -> ExamResult:
        """채점 → 오답 기록·일차 완료 → 저장 (FR-16 ~ FR-19)."""
        result = exam_logic.grade_exam(exam, answers)
        progress_logic.apply_day_exam_result(self._progress, day_no, result)
        self._store.save(self._progress)
        return result

    # ── 오답 시험 ───────────────────────────────────────────
    def build_wrong_exam(self) -> Exam:
        return exam_logic.build_exam(self.wrong_words(), self._words, self._rng)

    def submit_wrong_exam(
        self, exam: Exam, answers: Sequence[int | None]
    ) -> tuple[ExamResult, list[str]]:
        """채점 → 연속 정답 갱신 → 저장. 목록에서 빠진 단어도 함께 돌려준다 (FR-25)."""
        result = exam_logic.grade_exam(exam, answers)
        graduated = progress_logic.apply_wrong_exam_result(self._progress, result)
        self._store.save(self._progress)
        return result, graduated

    # ── 단어장 ──────────────────────────────────────────────
    def check_wordbook_file(self, path: Path) -> tuple[list[Word], list[ValidationIssue]]:
        """불러올 CSV 를 읽고 검증만 한다. 아무것도 바꾸지 않는다 (FR-02).

        교체를 check 와 replace 둘로 나눈 이유: 그 사이에 화면이 확인 대화상자를 띄워야 한다.
        """
        return wordbook_csv.read_wordbook_csv(path)

    def replace_wordbook(self, words: Sequence[Word]) -> None:
        """단어장을 바꾸고 학습 기록을 초기화한다 (FR-03, FR-04, ADR-03)."""
        wordbook_csv.replace_wordbook(self._base_dir, words)
        self._progress = progress_logic.new_progress()
        self._store.save(self._progress)
        self._words = tuple(words)
        self._wordbook_source = WordbookSource.CUSTOM
        self._days = schedule.build_days(len(self._words))

    def export_wordbook(self, path: Path) -> None:
        wordbook_csv.write_wordbook_csv(path, self._words)

    def export_wrong_list(self, path: Path) -> None:
        wordbook_csv.write_wrong_list_csv(path, self.wrong_list(), self._words)
