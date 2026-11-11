#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 메인 화면 (S-01): 오늘 할 일차, 진도, 메뉴
# 파일 위치: src/smartvoca/ui/home_page.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import DayStatus, WordbookSource
from ..session import AppSession
from .widgets import PAGE_MARGIN, SPACING, add_shortcut, hint_label, primary_button, set_font


class HomePage(QWidget):
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

        app_title = QLabel("스마트 보카")
        set_font(app_title, 20, bold=True)
        layout.addWidget(app_title)

        # 오늘의 학습: 가장 큰 버튼 하나로 바로 시작하게 한다
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QHBoxLayout(panel)
        panel_layout.setContentsMargins(20, 18, 20, 18)
        text_layout = QVBoxLayout()
        caption = hint_label("오늘의 학습")
        caption.setStyleSheet("border: none;")
        self.today_label = QLabel("")
        self.today_label.setWordWrap(True)
        self.today_label.setStyleSheet("border: none;")
        set_font(self.today_label, 18, bold=True)
        self.range_label = hint_label("")
        self.range_label.setStyleSheet("border: none;")
        text_layout.addWidget(caption)
        text_layout.addWidget(self.today_label)
        text_layout.addWidget(self.range_label)
        self.start_button = primary_button("학습 시작")
        set_font(self.start_button, 13, bold=True)
        self.start_button.setMinimumHeight(48)
        self.start_button.clicked.connect(self.start_clicked)
        panel_layout.addLayout(text_layout, 1)
        panel_layout.addWidget(self.start_button)
        layout.addWidget(panel)

        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("진도"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_label = QLabel("")
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.progress_label)
        layout.addLayout(progress_row)
        layout.addStretch(1)

        menu_row = QHBoxLayout()
        menu_row.setSpacing(SPACING)
        self.past_days_button, self.past_days_hint = self._add_menu(
            menu_row, "지난 일차", "복습·재시험", self.past_days_clicked
        )
        self.wrong_button, _ = self._add_menu(
            menu_row, "오답 학습", "틀린 단어 다시 보기", self.wrong_clicked
        )
        self.wordbook_button, _ = self._add_menu(
            menu_row, "단어 목록", "불러오기·내보내기", self.wordbook_clicked
        )
        layout.addLayout(menu_row)
        layout.addStretch(2)

        self.wordbook_label = hint_label("")
        layout.addWidget(self.wordbook_label)

        add_shortcut(self, Qt.Key.Key_Return, self._press_start)
        add_shortcut(self, Qt.Key.Key_Enter, self._press_start)

    def _add_menu(self, row: QHBoxLayout, text: str, description: str, signal):
        column = QVBoxLayout()
        button = QPushButton(text)
        button.setMinimumHeight(44)
        button.clicked.connect(signal)
        hint = hint_label(description)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(button)
        column.addWidget(hint)
        row.addLayout(column, 1)
        return button, hint

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
        else:
            day = session.days[day_no - 1]
            self.today_label.setText(f"{day_no}일차")
            self.range_label.setText(f"단어 {day.start + 1:,} ~ {day.end:,}")
            memorized = session.day_status(day_no) is DayStatus.MEMORIZED
            self.start_button.setText(
                f"{day_no}일차 이어서 하기" if memorized else f"{day_no}일차 학습 시작"
            )
            self.start_button.setVisible(True)

        self.progress_bar.setMaximum(summary.total_days)
        self.progress_bar.setValue(summary.done_days)
        self.progress_label.setText(f"{summary.done_days} / {summary.total_days} 일차 완료")

        has_past_days = bool(session.reviewable_days())
        self.past_days_button.setEnabled(has_past_days)
        self.past_days_hint.setText(
            "복습·재시험" if has_past_days else "아직 학습한 일차가 없습니다"
        )
        self.wrong_button.setText(f"오답 학습 ({summary.wrong_list_size})")

        if session.wordbook_source is WordbookSource.DEFAULT:
            self.wordbook_label.setText(f"단어장: 기본 토익 {len(session.words):,} 단어")
        else:
            self.wordbook_label.setText(f"단어장: 사용자 단어장 {len(session.words):,} 단어")
