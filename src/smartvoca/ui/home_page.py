#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 메인 화면 (S-01): 오늘 할 일차, 진도, 학습 현황, 메뉴
# 파일 위치: src/smartvoca/ui/home_page.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from ..core.models import DayStatus, WordbookSource
from ..session import AppSession
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    MenuCard,
    StatTile,
    add_shortcut,
    hint_label,
    make_button,
    make_panel,
    set_font,
    text_label,
)


class HomePage(QWidget):
    """들어오자마자 '오늘 할 일'이 가장 크게 보이게 한다 (UI/UX 설계서 §1.1 고민 없는 시작)."""

    start_clicked = pyqtSignal()
    past_days_clicked = pyqtSignal()
    wrong_clicked = pyqtSignal()
    wordbook_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)

        title_row = QHBoxLayout()
        title_row.addWidget(text_label("스마트 보카", 20, bold=True))
        title_row.addStretch(1)
        self.wordbook_label = hint_label("")
        self.wordbook_label.setWordWrap(False)
        title_row.addWidget(self.wordbook_label)
        layout.addLayout(title_row)

        layout.addWidget(self._build_hero())

        stats_row = QHBoxLayout()
        stats_row.setSpacing(SPACING)
        self.done_tile = StatTile("완료한 일차")
        self.learned_tile = StatTile("시험까지 마친 단어")
        self.wrong_tile = StatTile("오답 단어")
        for tile in (self.done_tile, self.learned_tile, self.wrong_tile):
            stats_row.addWidget(tile, 1)
        layout.addLayout(stats_row)

        menu_row = QHBoxLayout()
        menu_row.setSpacing(SPACING)
        self.past_days_button = MenuCard("복", "지난 일차", "복습·재시험")
        self.wrong_button = MenuCard("오", "오답 학습", "틀린 단어 다시 보기")
        self.wordbook_button = MenuCard("단", "단어 목록", "불러오기·내보내기")
        self.past_days_button.clicked.connect(self.past_days_clicked)
        self.wrong_button.clicked.connect(self.wrong_clicked)
        self.wordbook_button.clicked.connect(self.wordbook_clicked)
        for card in (self.past_days_button, self.wrong_button, self.wordbook_button):
            menu_row.addWidget(card, 1)
        layout.addLayout(menu_row)
        layout.addStretch(1)

        self.key_hint = hint_label("Enter 를 누르면 오늘의 학습을 바로 시작합니다")
        self.key_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.key_hint)

        add_shortcut(self, Qt.Key.Key_Return, self._press_start)
        add_shortcut(self, Qt.Key.Key_Enter, self._press_start)

    def _build_hero(self) -> QWidget:
        hero = make_panel("hero", shadow=True)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(18)

        top_row = QHBoxLayout()
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.addWidget(text_label("오늘의 학습", 10, bold=True, role="onPrimaryMuted"))
        self.today_label = text_label("", 26, bold=True, role="onPrimary")
        self.today_label.setWordWrap(True)
        self.range_label = text_label("", 11, role="onPrimaryMuted")
        self.range_label.setWordWrap(True)
        text_layout.addWidget(self.today_label)
        text_layout.addWidget(self.range_label)
        self.start_button = make_button("학습 시작", "onPrimary")
        set_font(self.start_button, 13, bold=True)
        self.start_button.setMinimumSize(190, 54)
        self.start_button.clicked.connect(self.start_clicked)
        top_row.addLayout(text_layout, 1)
        top_row.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignVCenter)
        hero_layout.addLayout(top_row)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setProperty("tone", "onPrimary")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_label = text_label("", 10, bold=True, role="onPrimary")
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.progress_label)
        hero_layout.addLayout(progress_row)
        return hero

    def _press_start(self) -> None:
        if self.start_button.isVisible() and self.start_button.isEnabled():
            self.start_clicked.emit()

    def refresh(self, session: AppSession) -> None:
        """보일 때마다 세션에서 값을 다시 읽어 그린다 (FR-09)."""
        summary = session.summary()
        day_no = summary.current_day
        if day_no is None:
            self.today_label.setText("모든 일차를 완료했습니다")
            self.range_label.setText("지난 일차에서 복습하거나 다시 시험을 볼 수 있습니다.")
            self.start_button.setVisible(False)
            self.key_hint.setVisible(False)
        else:
            day = session.days[day_no - 1]
            memorized = session.day_status(day_no) is DayStatus.MEMORIZED
            self.today_label.setText(f"{day_no}일차")
            range_text = f"단어 {day.start + 1:,} ~ {day.end:,} · {day.end - day.start}개"
            if memorized:
                range_text += " · 암기 완료, 시험이 남았습니다"
            self.range_label.setText(range_text)
            self.start_button.setText(
                f"{day_no}일차 이어서 하기" if memorized else f"{day_no}일차 학습 시작"
            )
            self.start_button.setVisible(True)
            self.key_hint.setVisible(True)

        self.progress_bar.setMaximum(summary.total_days)
        self.progress_bar.setValue(summary.done_days)
        self.progress_label.setText(f"{summary.done_days} / {summary.total_days} 일차 완료")

        learned_words = sum(
            day.end - day.start
            for day in session.days
            if session.day_status(day.day_no) is DayStatus.DONE
        )
        self.done_tile.set_value(f"{summary.done_days}일")
        self.learned_tile.set_value(f"{learned_words:,}개")
        self.wrong_tile.set_value(f"{summary.wrong_list_size:,}개")

        has_past_days = bool(session.reviewable_days())
        self.past_days_button.setEnabled(has_past_days)
        self.past_days_button.set_description(
            "복습·재시험" if has_past_days else "아직 학습한 일차가 없습니다"
        )
        self.wrong_button.set_title(f"오답 학습 ({summary.wrong_list_size})")

        if session.wordbook_source is WordbookSource.DEFAULT:
            self.wordbook_label.setText(f"단어장: 기본 토익 {len(session.words):,} 단어")
        else:
            self.wordbook_label.setText(f"단어장: 사용자 단어장 {len(session.words):,} 단어")
