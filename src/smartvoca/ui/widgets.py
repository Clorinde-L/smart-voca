#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 여러 화면이 함께 쓰는 부품: 머리줄, 패널, 메뉴 카드, 보기 항목, 문제 점, 점수 고리, 표
# 파일 위치: src/smartvoca/ui/widgets.py
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .theme import PAGE_MARGIN, SPACING  # 화면 파일이 여기서 함께 가져다 쓴다

__all__ = ["PAGE_MARGIN", "SPACING"]


def set_font(widget: QWidget, point_size: int, bold: bool = False) -> None:
    font = QFont(widget.font())
    font.setPointSize(point_size)
    font.setBold(bold)
    widget.setFont(font)


def set_role(widget: QWidget, role: str) -> None:
    """스타일시트의 [role="..."] 규칙을 적용한다 (muted, onPrimary 등)."""
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def text_label(text: str = "", point_size: int = 11, bold: bool = False, role: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)  # 단어장의 글자가 HTML 로 해석되지 않게
    set_font(label, point_size, bold)
    if role:
        label.setProperty("role", role)
    return label


def hint_label(text: str = "") -> QLabel:
    """흐린 색의 안내 문구 (버튼이 꺼져 있는 이유 등)."""
    label = text_label(text, 10, role="muted")
    label.setWordWrap(True)
    return label


def make_button(text: str, kind: str = "") -> QPushButton:
    """kind: ""(기본) / primary(화면마다 하나, 다음에 할 일) / ghost(뒤로) / onPrimary."""
    button = QPushButton(text)
    if kind:
        button.setProperty("kind", kind)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)
    return button


def primary_button(text: str) -> QPushButton:
    return make_button(text, "primary")


def add_shadow(widget: QWidget, blur: int = 28, alpha: int = 26) -> None:
    """패널이 배경에서 살짝 떠 보이게 하는 옅은 그림자."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(20, 26, 42, alpha))
    widget.setGraphicsEffect(shadow)


def make_panel(object_name: str = "panel", shadow: bool = False) -> QFrame:
    panel = QFrame()
    panel.setObjectName(object_name)
    if shadow:
        add_shadow(panel)
    return panel


def add_shortcut(widget: QWidget, key, handler) -> QShortcut:
    """화면(과 그 안의 위젯)에 초점이 있을 때만 듣는 단축키.

    버튼에 초점이 있어도 방향키·숫자키가 먹도록 keyPressEvent 대신 QShortcut 을 쓴다.
    """
    shortcut = QShortcut(QKeySequence(key), widget)
    shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
    shortcut.activated.connect(handler)
    return shortcut


class KeyHints(QWidget):
    """화면 아래에 두는 단축키 안내 줄. [키] 설명 · [키] 설명 … 꼴로 보여 준다.

    단축키는 이미 있지만 화면에 적혀 있지 않으면 쓰지 않게 되므로, 키 모양 글자로 눈에 띄게 둔다.
    """

    def __init__(self, hints: list[tuple[str, str]]):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addStretch(1)
        for position, (keys, description) in enumerate(hints):
            if position:
                separator = text_label("·", 10, role="muted")
                layout.addSpacing(4)
                layout.addWidget(separator)
                layout.addSpacing(4)
            for key in keys.split():
                keycap = QLabel(key)
                keycap.setObjectName("keycap")
                keycap.setAlignment(Qt.AlignmentFlag.AlignCenter)
                set_font(keycap, 9, bold=True)
                layout.addWidget(keycap)
            layout.addWidget(text_label(description, 10, role="muted"))
        layout.addStretch(1)

    def texts(self) -> list[str]:
        return [label.text() for label in self.findChildren(QLabel)]


class PageHeader(QWidget):
    """'← 뒤로' · 제목 · 오른쪽 정보로 된 화면 머리줄."""

    back_clicked = pyqtSignal()

    def __init__(self, title: str = "", show_back: bool = True):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._back_button = make_button("←  뒤로", "ghost")
        self._back_button.clicked.connect(self.back_clicked)
        self._back_button.setVisible(show_back)
        self._title = text_label(title, 15, bold=True)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info = QLabel("")
        self._info.setObjectName("pill")
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setVisible(False)
        # 제목이 창 가운데에 오도록 양쪽 칸의 폭을 같게 맞춘다
        side_width = 150
        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._back_button)
        left_layout.addStretch(1)
        right = QWidget()
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addStretch(1)
        right_layout.addWidget(self._info)
        left.setFixedWidth(side_width)
        right.setFixedWidth(side_width)
        layout.addWidget(left)
        layout.addWidget(self._title, 1)
        layout.addWidget(right)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def title(self) -> str:
        return self._title.text()

    def set_info(self, text: str) -> None:
        self._info.setText(text)
        self._info.setVisible(bool(text))

    def info(self) -> str:
        return self._info.text()

    def click_back(self) -> None:
        self._back_button.click()


class MenuCard(QPushButton):
    """메인 화면의 메뉴: 둥근 표식 + 제목 + 설명을 담은 큰 버튼.

    QPushButton 을 그대로 쓰므로 Tab·Enter·Space 로도 누를 수 있다.
    """

    def __init__(self, symbol: str, title: str, description: str):
        super().__init__()
        self.setProperty("kind", "menu")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)
        self._badge = QLabel(symbol)
        self._badge.setObjectName("badge")
        self._badge.setFixedSize(36, 36)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_font(self._badge, 13, bold=True)
        self._title = text_label(title, 12, bold=True)
        self._description = hint_label(description)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.addWidget(self._title)
        text_layout.addWidget(self._description)
        layout.addWidget(self._badge)
        layout.addLayout(text_layout, 1)
        # 안쪽 글자가 클릭을 가로채지 않게 한다
        for child in (self._badge, self._title, self._description):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def title(self) -> str:
        return self._title.text()

    def set_description(self, text: str) -> None:
        self._description.setText(text)

    def description(self) -> str:
        return self._description.text()


class StatTile(QFrame):
    """숫자 하나와 그 이름을 보여 주는 작은 칸."""

    def __init__(self, caption: str):
        super().__init__()
        self.setObjectName("tile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)
        self._value = text_label("", 18, bold=True)
        self._caption = hint_label(caption)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def value(self) -> str:
        return self._value.text()


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
        self.setMinimumHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        number = QLabel(str(index + 1))
        number.setObjectName("choiceNumber")
        number.setFixedSize(26, 26)
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text = text_label("", 13)
        self._text.setWordWrap(True)
        self._text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._mark = QLabel("")
        self._mark.setObjectName("choiceMark")
        self._mark.setFixedWidth(62)
        self._mark.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(number)
        layout.addWidget(self._text, 1)
        layout.addWidget(self._mark)

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def text(self) -> str:
        return self._text.text()

    def text_label_widget(self) -> QLabel:
        return self._text

    def is_selected(self) -> bool:
        return bool(self.property("selected"))

    def set_selected(self, selected: bool) -> None:
        # 색만으로 구분하지 않도록 '✓ 선택' 글자를 함께 붙인다
        self.setProperty("selected", selected)
        self._mark.setText("✓ 선택" if selected else "")
        for widget in (self, *self.findChildren(QLabel)):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)


class QuestionDots(QWidget):
    """시험 문제 번호를 점으로 늘어놓는다. 답한 문제·현재 문제가 한눈에 보이고, 누르면 그 문제로 간다.

    답한 문제는 색을 채우고 현재 문제는 굵은 테두리를 둘러, 색과 모양 두 가지로 구분한다.
    """

    jump_requested = pyqtSignal(int)
    DOT = 26
    GAP = 6

    def __init__(self):
        super().__init__()
        self._answered: list[bool] = []
        self._current = 0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def set_state(self, answered: list[bool], current: int) -> None:
        relayout = len(answered) != len(self._answered)
        self._answered, self._current = list(answered), current
        if relayout:
            self.updateGeometry()
        self.update()

    def _per_row(self, width: int) -> int:
        return max(1, (width + self.GAP) // (self.DOT + self.GAP))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        rows = -(-max(len(self._answered), 1) // self._per_row(width))
        return rows * self.DOT + (rows - 1) * self.GAP

    def sizeHint(self) -> QSize:
        return QSize(400, self.heightForWidth(max(self.width(), 400)))

    def _dot_rect(self, index: int) -> QRectF:
        per_row = self._per_row(self.width())
        row, column = divmod(index, per_row)
        in_row = min(per_row, len(self._answered) - row * per_row)
        row_width = in_row * self.DOT + (in_row - 1) * self.GAP
        left = (self.width() - row_width) / 2  # 줄마다 가운데 정렬
        step = self.DOT + self.GAP
        return QRectF(left + column * step, row * step, self.DOT, self.DOT)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        for index, answered in enumerate(self._answered):
            rect = self._dot_rect(index).adjusted(1.5, 1.5, -1.5, -1.5)
            is_current = index == self._current
            fill = QColor(theme.PRIMARY if answered else theme.SURFACE)
            border = QColor(theme.PRIMARY if (answered or is_current) else theme.BORDER_STRONG)
            painter.setBrush(fill)
            painter.setPen(QPen(border, 2.4 if is_current else 1.2))
            painter.drawEllipse(rect)
            if is_current and answered:  # 채워진 현재 문제는 안쪽에 흰 고리를 더해 구분한다
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#ffffff"), 1.4))
                painter.drawEllipse(rect.adjusted(3, 3, -3, -3))
            painter.setPen(QColor("#ffffff" if answered else theme.TEXT_MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(index + 1))

    def mousePressEvent(self, event) -> None:
        for index in range(len(self._answered)):
            if self._dot_rect(index).contains(event.position()):
                self.jump_requested.emit(index)
                return


class ScoreRing(QWidget):
    """맞은 비율을 고리로, 맞은 수 / 전체를 가운데 글자로 보여 준다."""

    def __init__(self):
        super().__init__()
        self._correct, self._total = 0, 1
        self.setFixedSize(164, 164)

    def set_score(self, correct: int, total: int) -> None:
        self._correct, self._total = correct, max(total, 1)
        self.update()

    def text(self) -> str:
        return f"{self._correct} / {self._total}"

    def paintEvent(self, event) -> None:
        ratio = self._correct / self._total
        color = QColor(
            theme.SUCCESS if ratio >= 0.9 else theme.PRIMARY if ratio >= 0.6 else theme.WARNING
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(10, 10, self.width() - 20, self.height() - 20)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#e1e5ee"), 11))
        painter.drawEllipse(rect)
        pen = QPen(color, 11)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * ratio))  # 12시에서 시계 방향
        font = QFont(self.font())
        font.setPointSize(21)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(rect.adjusted(0, -12, 0, -12), Qt.AlignmentFlag.AlignCenter, self.text())
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_MUTED))
        painter.drawText(
            rect.adjusted(0, 22, 0, 22), Qt.AlignmentFlag.AlignCenter, f"정답률 {round(ratio * 100)}%"
        )


def make_table(headers: list[str], stretch_columns: list[int]) -> QTableWidget:
    """읽기 전용, 행 단위 선택, 셀 안 줄바꿈 표."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setWordWrap(True)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setFrameShape(QFrame.Shape.NoFrame)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    for column in range(len(headers)):
        mode = (
            QHeaderView.ResizeMode.Stretch
            if column in stretch_columns
            else QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(column, mode)
    return table


def fill_table(table: QTableWidget, rows: list[list[str]], bold_columns=()) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, text in enumerate(row):
            item = QTableWidgetItem(text)
            if column in bold_columns:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            table.setItem(row_index, column, item)
    table.resizeRowsToContents()
