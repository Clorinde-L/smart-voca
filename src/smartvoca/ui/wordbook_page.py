#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 단어 목록 관리 화면 (S-07): 단어장 불러오기·내보내기, 오답 목록 내보내기
# 파일 위치: src/smartvoca/ui/wordbook_page.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.models import WordbookSource
from ..session import AppSession
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    PageHeader,
    add_shortcut,
    hint_label,
    make_button,
    make_panel,
    text_label,
)


class WordbookPage(QWidget):
    """버튼을 누르면 시그널만 내보낸다. 파일 선택·확인·교체는 MainWindow 가 한다."""

    back_clicked = pyqtSignal()
    import_clicked = pyqtSignal()
    export_wordbook_clicked = pyqtSignal()
    export_wrong_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader("단어 목록")
        self.header.back_clicked.connect(self.back_clicked)
        layout.addWidget(self.header)

        self.current_label = text_label("", 13, bold=True)
        layout.addWidget(self.current_label)

        self.import_button, _ = self._add_action(
            layout,
            "단어장 불러오기",
            "CSV 파일(word,meaning)을 단어장으로 씁니다. "
            "단어장을 바꾸면 학습 기록이 모두 지워집니다.\n"
            "기본 단어장으로 되돌리려면 data/toeic_words_2000.csv 를 불러오세요.",
            "불러오기",
            self.import_clicked,
        )
        self.export_wordbook_button, _ = self._add_action(
            layout,
            "단어장 내보내기",
            "현재 단어장을 CSV 파일로 저장합니다.",
            "내보내기",
            self.export_wordbook_clicked,
        )
        self.export_wrong_button, self.export_wrong_hint = self._add_action(
            layout, "오답 목록 내보내기", "", "내보내기", self.export_wrong_clicked
        )
        layout.addStretch(1)

        add_shortcut(self, Qt.Key.Key_Escape, self.back_clicked.emit)

    def _add_action(
        self, layout: QVBoxLayout, title: str, description: str, button_text: str, signal
    ) -> tuple[QPushButton, QLabel]:
        """제목·설명·버튼을 한 줄 패널로 만든다."""
        panel = make_panel()
        row = QHBoxLayout(panel)
        row.setContentsMargins(22, 18, 22, 18)
        row.setSpacing(18)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        hint = hint_label(description)
        text_layout.addWidget(text_label(title, 12, bold=True))
        text_layout.addWidget(hint)
        button = make_button(button_text)
        button.setMinimumWidth(120)
        button.setAccessibleName(title)
        button.clicked.connect(signal)
        row.addLayout(text_layout, 1)
        row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(panel)
        return button, hint

    def refresh(self, session: AppSession) -> None:
        kind = (
            "기본 토익"
            if session.wordbook_source is WordbookSource.DEFAULT
            else "사용자 단어장"
        )
        self.current_label.setText(
            f"현재 단어장: {kind} {len(session.words):,} 단어 ({len(session.days)}일차)"
        )
        wrong_count = session.summary().wrong_list_size
        self.export_wrong_button.setEnabled(wrong_count > 0)
        self.export_wrong_hint.setText(
            f"오답 단어 {wrong_count}개를 CSV 파일로 저장합니다."
            if wrong_count
            else "내보낼 오답 단어가 없습니다."
        )
