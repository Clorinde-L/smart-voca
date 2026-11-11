#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 카드 화면 (S-02): 일차 학습·복습·오답 학습 공용
# 파일 위치: src/smartvoca/ui/card_page.py
from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.cards import CardDeck
from ..core.models import GRADUATE_STREAK, Word, WrongEntry
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    PageHeader,
    add_shortcut,
    hint_label,
    primary_button,
    set_font,
)


class CardMode(Enum):
    DAY = "day"        # 일차 학습: 모두 보면 '시험 보기'가 켜진다
    REVIEW = "review"  # 복습: 하단 버튼 없음, 기록을 바꾸지 않는다
    WRONG = "wrong"    # 오답 학습: 모두 보면 '오답 시험'이 켜진다


_ACTION_TEXT = {CardMode.DAY: "시험 보기", CardMode.WRONG: "오답 시험"}
_HINT_BEFORE = {
    CardMode.DAY: "남은 카드를 모두 보면 시험을 볼 수 있습니다",
    CardMode.WRONG: "남은 카드를 모두 보면 오답 시험을 볼 수 있습니다",
}
_HINT_AFTER = {
    CardMode.DAY: "암기 완료! 시험을 볼 수 있습니다",
    CardMode.WRONG: "카드를 모두 봤습니다. 오답 시험을 볼 수 있습니다",
}


class CardPage(QWidget):
    back_clicked = pyqtSignal()
    action_clicked = pyqtSignal()  # 시험 보기 / 오답 시험
    all_seen = pyqtSignal()        # 이번에 카드를 모두 봤을 때 한 번

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._deck: CardDeck | None = None
        self._mode = CardMode.DAY
        self._wrong_info: Mapping[str, WrongEntry] = {}
        self._all_seen_reported = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader()
        self.header.back_clicked.connect(self.back_clicked)
        layout.addWidget(self.header)

        card = QFrame()
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(20)
        self.word_label = QLabel("")
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setWordWrap(True)
        set_font(self.word_label, 32, bold=True)
        # 뜻은 CSV 뜻 칸 그대로 보여 주고, 길면 줄바꿈한다 (FR-10, NFR-07)
        self.meaning_label = QLabel("")
        self.meaning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meaning_label.setWordWrap(True)
        self.meaning_label.setTextFormat(Qt.TextFormat.PlainText)
        set_font(self.meaning_label, 16)
        self.stats_label = hint_label("")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for label in (self.word_label, self.meaning_label, self.stats_label):
            label.setStyleSheet("border: none;")
        card_layout.addStretch(1)
        card_layout.addWidget(self.word_label)
        card_layout.addWidget(self.meaning_label)
        card_layout.addWidget(self.stats_label)
        card_layout.addStretch(1)
        layout.addWidget(card, 1)

        move_row = QHBoxLayout()
        self.prev_button = QPushButton("◀ 이전")
        self.next_button = QPushButton("다음 ▶")
        for button in (self.prev_button, self.next_button):
            button.setMinimumWidth(140)
        self.prev_button.clicked.connect(self.go_prev)
        self.next_button.clicked.connect(self.go_next)
        move_row.addWidget(self.prev_button)
        move_row.addStretch(1)
        move_row.addWidget(self.next_button)
        layout.addLayout(move_row)

        bottom_row = QHBoxLayout()
        self.hint = hint_label("")
        self.action_button = primary_button("")
        self.action_button.clicked.connect(self.action_clicked)
        bottom_row.addWidget(self.hint, 1)
        bottom_row.addWidget(self.action_button)
        layout.addLayout(bottom_row)

        add_shortcut(self, Qt.Key.Key_Right, self.go_next)
        add_shortcut(self, Qt.Key.Key_Left, self.go_prev)
        add_shortcut(self, Qt.Key.Key_Escape, self.back_clicked.emit)
        add_shortcut(self, Qt.Key.Key_Return, self._press_action)
        add_shortcut(self, Qt.Key.Key_Enter, self._press_action)

    @property
    def mode(self) -> CardMode:
        return self._mode

    def start(
        self,
        mode: CardMode,
        title: str,
        words: Sequence[Word],
        already_done: bool = False,
        wrong_info: Mapping[str, WrongEntry] | None = None,
    ) -> None:
        """새 카드 묶음으로 시작한다. 항상 첫 카드부터다 (요구사항 명세서 D-03).

        already_done: 이미 암기 완료한 일차라서 처음부터 시험 버튼을 켜 둘 때.
        """
        self._mode = mode
        self._deck = CardDeck(words)
        self._wrong_info = wrong_info or {}
        self._all_seen_reported = already_done
        self.header.set_title(title)
        has_action = mode in _ACTION_TEXT
        self.action_button.setVisible(has_action)  # 복습에는 시험 버튼이 없다 (FR-21)
        self.hint.setVisible(has_action)
        if has_action:
            self.action_button.setText(_ACTION_TEXT[mode])
        self._render()

    def go_next(self) -> None:
        if self._deck is not None and self._deck.next():
            self._render()

    def go_prev(self) -> None:
        if self._deck is not None and self._deck.prev():
            self._render()

    def _press_action(self) -> None:
        if self.action_button.isVisible() and self.action_button.isEnabled():
            self.action_clicked.emit()
        else:
            self.go_next()

    def _render(self) -> None:
        deck = self._deck
        word = deck.current
        self.header.set_info(f"{deck.position} / {deck.total}")
        self.word_label.setText(word.word)
        self.meaning_label.setText(word.meaning)
        entry = self._wrong_info.get(word.word)
        self.stats_label.setVisible(entry is not None)
        if entry is not None:
            self.stats_label.setText(
                f"틀린 횟수 {entry.wrong_count} · 연속 정답 {entry.streak} / {GRADUATE_STREAK}"
            )
        self.prev_button.setEnabled(deck.can_prev)
        self.next_button.setEnabled(deck.can_next)

        unlocked = self._all_seen_reported or deck.seen_all
        if self._mode in _ACTION_TEXT:
            self.action_button.setEnabled(unlocked)
            hints = _HINT_AFTER if unlocked else _HINT_BEFORE
            self.hint.setText(hints[self._mode])
        if deck.seen_all and not self._all_seen_reported:
            self._all_seen_reported = True
            self.all_seen.emit()
