#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 여러 화면이 함께 쓰는 부품: 머리줄, 줄바꿈되는 보기 항목, 표·글자 도우미
# 파일 위치: src/smartvoca/ui/widgets.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

PAGE_MARGIN = 24
SPACING = 12

APP_STYLE = """
QWidget { color: #1c1c1c; }
QMainWindow, QStackedWidget, QWidget#page { background: #f6f7f9; }
QPushButton { padding: 8px 16px; border: 1px solid #b9bec7; border-radius: 6px; background: #ffffff; }
QPushButton:hover { background: #eef2f8; }
QPushButton:disabled { color: #9aa0a8; background: #eceef1; border-color: #d5d8dd; }
QPushButton[primary="true"] { background: #2f6fed; color: #ffffff; border-color: #2f6fed; font-weight: bold; }
QPushButton[primary="true"]:hover { background: #255fd1; }
QPushButton[primary="true"]:disabled { background: #a9c1f5; border-color: #a9c1f5; color: #ffffff; }
QLabel[hint="true"] { color: #6b7280; }
QFrame#panel { background: #ffffff; border: 1px solid #d9dde3; border-radius: 10px; }
QFrame#choice { background: #ffffff; border: 1px solid #c5cad3; border-radius: 8px; }
QFrame#choice[selected="true"] { background: #e8f0ff; border: 2px solid #2f6fed; }
QTableWidget { background: #ffffff; border: 1px solid #d9dde3; gridline-color: #e6e8ec; }
QProgressBar { border: 1px solid #c5cad3; border-radius: 6px; background: #ffffff; height: 16px; }
QProgressBar::chunk { background: #2f6fed; border-radius: 5px; }
"""


def set_font(widget: QWidget, point_size: int, bold: bool = False) -> None:
    font = QFont(widget.font())
    font.setPointSize(point_size)
    font.setBold(bold)
    widget.setFont(font)


def hint_label(text: str = "") -> QLabel:
    """흐린 색의 안내 문구 (버튼이 꺼져 있는 이유 등)."""
    label = QLabel(text)
    label.setProperty("hint", True)
    label.setWordWrap(True)
    set_font(label, 10)
    return label


def primary_button(text: str) -> QPushButton:
    """화면마다 하나 두는 '다음에 할 일' 버튼."""
    button = QPushButton(text)
    button.setProperty("primary", True)
    return button


def add_shortcut(widget: QWidget, key, handler) -> QShortcut:
    """화면(과 그 안의 위젯)에 초점이 있을 때만 듣는 단축키.

    버튼에 초점이 있어도 방향키·숫자키가 먹도록 keyPressEvent 대신 QShortcut 을 쓴다.
    """
    shortcut = QShortcut(QKeySequence(key), widget)
    shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    shortcut.activated.connect(handler)
    return shortcut


class PageHeader(QWidget):
    """'← 뒤로' · 제목 · 오른쪽 정보로 된 화면 머리줄."""

    back_clicked = pyqtSignal()

    def __init__(self, title: str = "", show_back: bool = True):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._back_button = QPushButton("← 뒤로")
        self._back_button.clicked.connect(self.back_clicked)
        self._back_button.setVisible(show_back)
        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_font(self._title, 16, bold=True)
        self._info = QLabel("")
        self._info.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._info.setMinimumWidth(self._back_button.sizeHint().width())
        layout.addWidget(self._back_button)
        layout.addWidget(self._title, 1)
        layout.addWidget(self._info)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_info(self, text: str) -> None:
        self._info.setText(text)


class ChoiceItem(QFrame):
    """시험 보기 1개. 긴 뜻이 줄바꿈되도록 QLabel 을 담은 클릭 가능한 틀로 만든다.

    QPushButton 은 글자를 자동으로 줄바꿈하지 않아 긴 뜻이 잘리기 때문이다 (NFR-07).
    """

    clicked = pyqtSignal(int)

    def __init__(self, index: int):
        super().__init__()
        self._index = index
        self.setObjectName("choice")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(52)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        number = QLabel(str(index + 1))
        set_font(number, 13, bold=True)
        number.setFixedWidth(22)
        self._text = QLabel("")
        self._text.setWordWrap(True)
        self._text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        set_font(self._text, 13)
        self._mark = QLabel("")
        self._mark.setFixedWidth(64)
        self._mark.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(number)
        layout.addWidget(self._text, 1)
        layout.addWidget(self._mark)
        # 틀의 테두리 스타일이 안쪽 글자 라벨에 번지지 않게 한다
        for label in (number, self._text, self._mark):
            label.setStyleSheet("border: none; background: transparent;")

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def text(self) -> str:
        return self._text.text()

    def is_selected(self) -> bool:
        return bool(self.property("selected"))

    def set_selected(self, selected: bool) -> None:
        # 색만으로 구분하지 않도록 '● 선택' 글자를 함께 붙인다
        self.setProperty("selected", selected)
        self._mark.setText("● 선택" if selected else "")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)


def make_table(headers: list[str], stretch_columns: list[int]) -> QTableWidget:
    """읽기 전용, 행 단위 선택, 셀 안 줄바꿈 표."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setWordWrap(True)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    for column in range(len(headers)):
        mode = (
            QHeaderView.ResizeMode.Stretch
            if column in stretch_columns
            else QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(column, mode)
    return table


def fill_table(table: QTableWidget, rows: list[list[str]], centered_columns=()) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, text in enumerate(row):
            item = QTableWidgetItem(text)
            if column in centered_columns:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_index, column, item)
    table.resizeRowsToContents()
