#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 메인 창: 화면 전환과 세션 호출을 한곳에서 관리 (UI/UX 설계서 §4 전이도)
# 파일 위치: src/smartvoca/ui/main_window.py
"""창 하나에서 화면만 바꾼다 (ADR-09).

화면(*Page)은 서로를 모르고 시그널만 내보낸다. 어느 화면으로 갈지, 언제 세션을 부를지는
전부 여기에 있다 — 전이도와 이 파일을 나란히 놓고 볼 수 있게 하기 위함이다.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from ..core.models import DAY_SIZE, DayStatus, Exam
from ..session import AppSession
from . import dialogs
from .card_page import CardMode, CardPage
from .day_list_page import DayListPage
from .exam_page import ExamPage
from .home_page import HomePage
from .result_page import ResultPage
from .wordbook_page import WordbookPage
from .wrong_list_page import WrongListPage


class MainWindow(QMainWindow):
    def __init__(self, session: AppSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("스마트 보카")
        self.resize(960, 700)
        self.setMinimumSize(800, 600)

        self._card_day: int | None = None   # 카드 화면이 다루는 일차 (오답 학습이면 None)
        self._exam: Exam | None = None      # 응시 중인 시험지
        self._exam_day: int | None = None   # 일차 시험이면 일차 번호, 오답 시험이면 None
        self._exam_return: QWidget | None = None  # 시험을 그만두면 돌아갈 화면

        self.home_page = HomePage()
        self.card_page = CardPage()
        self.exam_page = ExamPage()
        self.result_page = ResultPage()
        self.day_list_page = DayListPage()
        self.wrong_list_page = WrongListPage()
        self.wordbook_page = WordbookPage()
        self.stack = QStackedWidget()
        for page in (
            self.home_page,
            self.card_page,
            self.exam_page,
            self.result_page,
            self.day_list_page,
            self.wrong_list_page,
            self.wordbook_page,
        ):
            self.stack.addWidget(page)
        self.setCentralWidget(self.stack)
        self._connect_signals()
        self.show_home()

    def _connect_signals(self) -> None:
        self.home_page.start_clicked.connect(self.start_current_day)
        self.home_page.past_days_clicked.connect(self.show_day_list)
        self.home_page.wrong_clicked.connect(self.show_wrong_list)
        self.home_page.wordbook_clicked.connect(self.show_wordbook)

        self.card_page.back_clicked.connect(self._on_card_back)
        self.card_page.all_seen.connect(self._on_cards_all_seen)
        self.card_page.action_clicked.connect(self._on_card_action)

        self.exam_page.back_requested.connect(self._on_exam_back)
        self.exam_page.submitted.connect(self._on_exam_submitted)

        self.result_page.next_day_clicked.connect(self.open_day_cards)
        self.result_page.wrong_list_clicked.connect(self.show_wrong_list)
        self.result_page.home_clicked.connect(self.show_home)

        self.day_list_page.back_clicked.connect(self.show_home)
        self.day_list_page.review_requested.connect(self.open_review_cards)
        self.day_list_page.exam_requested.connect(self.start_day_exam)

        self.wrong_list_page.back_clicked.connect(self.show_home)
        self.wrong_list_page.study_clicked.connect(self.open_wrong_cards)
        self.wrong_list_page.export_clicked.connect(self.export_wrong_list)

        self.wordbook_page.back_clicked.connect(self.show_home)
        self.wordbook_page.import_clicked.connect(self.import_wordbook)
        self.wordbook_page.export_wordbook_clicked.connect(self.export_wordbook)
        self.wordbook_page.export_wrong_clicked.connect(self.export_wrong_list)

    def _go(self, page: QWidget) -> None:
        self.stack.setCurrentWidget(page)
        page.setFocus()  # 단축키가 바로 듣도록 초점을 화면에 준다

    # ── 화면 열기 ───────────────────────────────────────────
    def show_home(self) -> None:
        self.home_page.refresh(self.session)
        self._go(self.home_page)

    def show_day_list(self) -> None:
        self.day_list_page.refresh(self.session)
        self._go(self.day_list_page)

    def show_wrong_list(self) -> None:
        self.wrong_list_page.refresh(self.session)
        self._go(self.wrong_list_page)

    def show_wordbook(self) -> None:
        self.wordbook_page.refresh(self.session)
        self._go(self.wordbook_page)

    # ── 카드 ────────────────────────────────────────────────
    def start_current_day(self) -> None:
        day_no = self.session.summary().current_day
        if day_no is not None:
            self.open_day_cards(day_no)

    def open_day_cards(self, day_no: int) -> None:
        self._card_day = day_no
        already_memorized = self.session.day_status(day_no) is not DayStatus.AVAILABLE
        self.card_page.start(
            CardMode.DAY,
            f"{day_no}일차 학습",
            self.session.day_words(day_no),
            already_done=already_memorized,
        )
        self._go(self.card_page)

    def open_review_cards(self, day_no: int) -> None:
        self._card_day = day_no
        self.card_page.start(
            CardMode.REVIEW, f"{day_no}일차 복습", self.session.day_words(day_no)
        )
        self._go(self.card_page)

    def open_wrong_cards(self) -> None:
        self._card_day = None
        wrong_info = {entry.word: entry for entry in self.session.wrong_list()}
        self.card_page.start(
            CardMode.WRONG, "오답 학습", self.session.wrong_words(), wrong_info=wrong_info
        )
        self._go(self.card_page)

    def _card_mode(self) -> CardMode:
        return self.card_page.mode

    def _on_cards_all_seen(self) -> None:
        """일차 학습에서 카드를 모두 보면 암기 완료를 기록한다 (FR-12). 복습·오답은 기록하지 않는다."""
        if self._card_mode() is not CardMode.DAY or self._card_day is None:
            return
        if self.session.day_status(self._card_day) is DayStatus.AVAILABLE:
            try:
                self.session.complete_memorize(self._card_day)
            except OSError as error:
                dialogs.show_save_error(self, error)

    def _on_card_action(self) -> None:
        if self._card_mode() is CardMode.DAY and self._card_day is not None:
            self.start_day_exam(self._card_day)
        elif self._card_mode() is CardMode.WRONG:
            self.start_wrong_exam()

    def _on_card_back(self) -> None:
        mode = self._card_mode()
        if mode is CardMode.REVIEW:
            self.show_day_list()
        elif mode is CardMode.WRONG:
            self.show_wrong_list()
        else:
            self.show_home()

    # ── 시험 ────────────────────────────────────────────────
    def start_day_exam(self, day_no: int) -> None:
        self._begin_exam(self.session.build_day_exam(day_no), day_no, f"{day_no}일차 시험")

    def start_wrong_exam(self) -> None:
        self._begin_exam(self.session.build_wrong_exam(), None, "오답 시험")

    def _begin_exam(self, exam: Exam, day_no: int | None, title: str) -> None:
        self._exam, self._exam_day = exam, day_no
        self._exam_return = self.stack.currentWidget()
        self.exam_page.start(title, exam)
        self._go(self.exam_page)

    def _on_exam_back(self) -> None:
        """시험을 그만두면 아무것도 반영하지 않고 들어온 화면으로 돌아간다 (ADR-12)."""
        if not dialogs.confirm_abort_exam(self):
            return
        self._exam = None
        if self._exam_return is self.day_list_page:
            self.show_day_list()
        else:
            self._go(self._exam_return or self.home_page)

    def _on_exam_submitted(self, answers: list) -> None:
        exam, day_no = self._exam, self._exam_day
        if exam is None:
            return
        self._exam = None
        try:
            if day_no is not None:
                is_retest = self.session.day_status(day_no) is DayStatus.DONE
                result = self.session.submit_day_exam(day_no, exam, answers)
                next_day = day_no + 1 if day_no < len(self.session.days) else None
                self.result_page.show_day_result(day_no, result, is_retest, next_day)
            else:
                result, graduated = self.session.submit_wrong_exam(exam, answers)
                remaining = self.session.summary().wrong_list_size
                self.result_page.show_wrong_result(result, graduated, remaining)
        except OSError as error:
            dialogs.show_save_error(self, error)
            self.show_home()
            return
        self._go(self.result_page)

    # ── 단어장 불러오기·내보내기 ─────────────────────────────
    def import_wordbook(self) -> None:
        """파일 선택 → 검증 → 확인 → 교체 (UI/UX 설계서 §6.3)."""
        path = dialogs.ask_open_csv(self)
        if path is None:
            return
        words, issues = self.session.check_wordbook_file(path)
        if issues:
            dialogs.show_validation_issues(self, issues)
            return
        summary = self.session.summary()
        day_count = -(-len(words) // DAY_SIZE)  # 올림 나눗셈
        if not dialogs.confirm_replace_wordbook(
            self, path.name, len(words), day_count, summary.done_days, summary.wrong_list_size
        ):
            return
        try:
            self.session.replace_wordbook(words)
        except OSError as error:
            dialogs.show_save_error(self, error)
            return
        dialogs.show_info(
            self, "단어장 교체", f"단어장을 바꿨습니다. ({len(words):,} 단어, {day_count}일차)"
        )
        self.show_home()

    def export_wordbook(self) -> None:
        path = dialogs.ask_save_csv(self, "단어장 내보내기", "wordbook.csv")
        if path is None:
            return
        try:
            self.session.export_wordbook(path)
        except OSError as error:
            dialogs.show_error(self, "내보내기", f"파일을 저장하지 못했습니다.\n({error})")
            return
        dialogs.show_info(self, "내보내기", f"단어장을 저장했습니다.\n{path}")

    def export_wrong_list(self) -> None:
        if not self.session.wrong_list():
            dialogs.show_info(self, "내보내기", "내보낼 오답 단어가 없습니다.")
            return
        path = dialogs.ask_save_csv(self, "오답 목록 내보내기", "wrong_words.csv")
        if path is None:
            return
        try:
            self.session.export_wrong_list(path)
        except OSError as error:
            dialogs.show_error(self, "내보내기", f"파일을 저장하지 못했습니다.\n({error})")
            return
        dialogs.show_info(self, "내보내기", f"오답 목록을 저장했습니다.\n{path}")

    def closeEvent(self, event) -> None:
        # 시험 중에 창을 닫으려 하면 그만둘지 먼저 묻는다
        if self.stack.currentWidget() is self.exam_page and self._exam is not None:
            if not dialogs.confirm_abort_exam(self):
                event.ignore()
                return
        event.accept()
