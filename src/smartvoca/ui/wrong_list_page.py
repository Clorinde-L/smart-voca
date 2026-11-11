#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 오답 목록 화면 (S-06): 틀린 단어 표, 카드 학습·내보내기 진입
# 파일 위치: src/smartvoca/ui/wrong_list_page.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..core.models import GRADUATE_STREAK
from ..session import AppSession
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    PageHeader,
    add_shortcut,
    fill_table,
    hint_label,
    make_table,
    primary_button,
    set_font,
)


class WrongListPage(QWidget):
    back_clicked = pyqtSignal()
    study_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader("오답 학습")
        self.header.back_clicked.connect(self.back_clicked)
        layout.addWidget(self.header)

        # 순서는 세션이 준 그대로다(오답 횟수 순). 사용자가 정렬을 바꾸지 못하게 둔다 (FR-22)
        self.table = make_table(["단어", "뜻", "틀린 횟수", "연속 정답"], stretch_columns=[1])
        layout.addWidget(self.table, 1)
        self.empty_label = hint_label(
            "틀린 단어가 없습니다. 일차 시험에서 틀린 단어가 여기에 모입니다."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_font(self.empty_label, 12)
        layout.addWidget(self.empty_label, 1)

        # 목록에서 빠지는 기준을 화면에 적어 둔다 (현황·환경 분석서 I-03)
        self.rule_label = hint_label(
            f"오답 시험에서 {GRADUATE_STREAK}번 연속 맞히면 목록에서 빠집니다"
        )
        layout.addWidget(self.rule_label)

        button_row = QHBoxLayout()
        self.study_button = primary_button("카드로 학습")
        self.export_button = QPushButton("오답 목록 내보내기")
        self.study_button.clicked.connect(self.study_clicked)
        self.export_button.clicked.connect(self.export_clicked)
        button_row.addWidget(self.study_button)
        button_row.addStretch(1)
        button_row.addWidget(self.export_button)
        layout.addLayout(button_row)

        add_shortcut(self, Qt.Key.Key_Escape, self.back_clicked.emit)
        add_shortcut(self, Qt.Key.Key_Return, self._press_study)
        add_shortcut(self, Qt.Key.Key_Enter, self._press_study)

    def _press_study(self) -> None:
        if self.study_button.isEnabled():
            self.study_clicked.emit()

    def refresh(self, session: AppSession) -> None:
        entries = session.wrong_list()
        meaning_of = {word.word: word.meaning for word in session.wrong_words()}
        has_entries = bool(entries)
        self.header.set_info(f"오답 단어 {len(entries)}개")
        self.table.setVisible(has_entries)
        self.rule_label.setVisible(has_entries)
        self.empty_label.setVisible(not has_entries)
        self.study_button.setEnabled(has_entries)
        self.export_button.setEnabled(has_entries)
        fill_table(
            self.table,
            [
                [
                    entry.word,
                    meaning_of[entry.word],
                    str(entry.wrong_count),
                    f"{entry.streak} / {GRADUATE_STREAK}",
                ]
                for entry in entries
            ],
            centered_columns=(2, 3),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.table.resizeRowsToContents()
