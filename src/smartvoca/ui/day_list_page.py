#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 지난 일차 화면 (S-05): 복습과 재시험의 진입점
# 파일 위치: src/smartvoca/ui/day_list_page.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..session import AppSession
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    PageHeader,
    add_shortcut,
    fill_table,
    make_table,
    primary_button,
    set_font,
)


class DayListPage(QWidget):
    """암기 완료 이상인 일차를 보여 주고, 고른 일차를 복습하거나 시험 본다 (ADR-11)."""

    back_clicked = pyqtSignal()
    review_requested = pyqtSignal(int)
    exam_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._day_numbers: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader("지난 일차")
        self.header.back_clicked.connect(self.back_clicked)
        layout.addWidget(self.header)

        self.table = make_table(["일차", "단어", "상태"], stretch_columns=[1])
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self._request_review())
        layout.addWidget(self.table, 1)

        bottom_row = QHBoxLayout()
        self.selected_label = QLabel("일차를 고르세요")
        set_font(self.selected_label, 11, bold=True)
        self.review_button = primary_button("카드로 복습")
        self.exam_button = QPushButton("시험 보기")
        self.review_button.clicked.connect(self._request_review)
        self.exam_button.clicked.connect(self._request_exam)
        bottom_row.addWidget(self.selected_label, 1)
        bottom_row.addWidget(self.review_button)
        bottom_row.addWidget(self.exam_button)
        layout.addLayout(bottom_row)

        add_shortcut(self, Qt.Key.Key_Escape, self.back_clicked.emit)
        add_shortcut(self, Qt.Key.Key_Return, self._request_review)
        add_shortcut(self, Qt.Key.Key_Enter, self._request_review)

    def refresh(self, session: AppSession) -> None:
        self._day_numbers = session.reviewable_days()
        rows = []
        for day_no in self._day_numbers:
            words = session.day_words(day_no)
            rows.append(
                [
                    f"{day_no}일차",
                    f"{words[0].word} ~ {words[-1].word}",
                    session.day_status(day_no).value,  # '완료' / '암기 완료' 를 글자로 적는다
                ]
            )
        fill_table(self.table, rows, centered_columns=(0, 2))
        self.table.clearSelection()
        self._update_buttons()

    def selected_day(self) -> int | None:
        row = self.table.currentRow()
        if not self.table.selectedItems() or not 0 <= row < len(self._day_numbers):
            return None
        return self._day_numbers[row]

    def _update_buttons(self) -> None:
        day_no = self.selected_day()
        self.review_button.setEnabled(day_no is not None)
        self.exam_button.setEnabled(day_no is not None)
        self.selected_label.setText("일차를 고르세요" if day_no is None else f"{day_no}일차")

    def _request_review(self) -> None:
        day_no = self.selected_day()
        if day_no is not None:
            self.review_requested.emit(day_no)

    def _request_exam(self) -> None:
        day_no = self.selected_day()
        if day_no is not None:
            self.exam_requested.emit(day_no)
