#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 화면 전체의 색·글꼴·스타일시트와 앱 아이콘
# 파일 위치: src/smartvoca/ui/theme.py
"""디자인 값은 이 모듈에만 둔다.

화면 파일에 색 코드를 직접 쓰지 않고 여기의 이름을 가져다 쓰면,
색 하나를 바꿀 때 이 파일만 고치면 된다.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

# 색 ─ 차분한 남보라를 강조색 하나로 쓰고, 나머지는 회색 계열로 둔다
BACKGROUND = "#f3f5fa"
SURFACE = "#ffffff"
BORDER = "#e3e7ef"
BORDER_STRONG = "#cbd2de"
TEXT = "#141a2a"
TEXT_MUTED = "#677086"
PRIMARY = "#4f5bd5"
PRIMARY_HOVER = "#414cc0"
PRIMARY_PRESSED = "#3640a8"
PRIMARY_SOFT = "#eceefc"
PRIMARY_DISABLED = "#b9bfee"
SUCCESS = "#1f9d61"
SUCCESS_SOFT = "#e4f6ec"
WARNING = "#c9820a"
WARNING_SOFT = "#fdf3dd"
DANGER = "#d1435b"
DANGER_SOFT = "#fdeaee"

# 글꼴 ─ 영문·숫자는 Segoe UI, 한글은 맑은 고딕으로 넘어간다 (둘 다 Windows 기본 글꼴)
FONT_FAMILIES = ["Segoe UI", "Malgun Gothic"]
BASE_POINT_SIZE = 11

PAGE_MARGIN = 28
SPACING = 14
RADIUS = 14


def base_font() -> QFont:
    return QFont(FONT_FAMILIES, BASE_POINT_SIZE)


APP_STYLE = f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, QStackedWidget, QWidget#page {{ background: {BACKGROUND}; }}
QLabel {{ background: transparent; border: none; }}
QLabel[role="muted"] {{ color: {TEXT_MUTED}; }}
QLabel[role="onPrimary"] {{ color: #ffffff; }}
QLabel[role="onPrimaryMuted"] {{ color: #dfe2fb; }}
QLabel[role="success"] {{ color: {SUCCESS}; }}

QPushButton {{
    padding: 9px 18px; border: 1px solid {BORDER_STRONG}; border-radius: 10px;
    background: {SURFACE}; font-weight: 600;
}}
QPushButton:hover {{ background: {PRIMARY_SOFT}; border-color: {PRIMARY}; }}
QPushButton:pressed {{ background: #dfe2fb; }}
QPushButton:focus {{ border: 2px solid {PRIMARY}; padding: 8px 17px; }}
QPushButton:disabled {{ color: #a3aabb; background: #eef0f5; border-color: {BORDER}; }}

QPushButton[kind="primary"] {{ background: {PRIMARY}; color: #ffffff; border: 1px solid {PRIMARY}; }}
QPushButton[kind="primary"]:hover {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
QPushButton[kind="primary"]:pressed {{ background: {PRIMARY_PRESSED}; }}
QPushButton[kind="primary"]:focus {{ border: 2px solid #1e2a8a; padding: 8px 17px; }}
QPushButton[kind="primary"]:disabled {{
    background: {PRIMARY_DISABLED}; border-color: {PRIMARY_DISABLED}; color: #ffffff;
}}

QPushButton[kind="onPrimary"] {{ background: #ffffff; color: {PRIMARY}; border: 1px solid #ffffff; }}
QPushButton[kind="onPrimary"]:hover {{ background: {PRIMARY_SOFT}; }}
QPushButton[kind="onPrimary"]:focus {{ border: 2px solid #1e2a8a; padding: 8px 17px; }}

QPushButton[kind="ghost"] {{ background: transparent; border: 1px solid transparent; color: {TEXT_MUTED}; }}
QPushButton[kind="ghost"]:hover {{ background: #e7eaf2; color: {TEXT}; border-color: transparent; }}
QPushButton[kind="ghost"]:focus {{ border: 2px solid {PRIMARY}; padding: 8px 17px; }}

QPushButton[kind="menu"] {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}px;
    padding: 0px; text-align: left;
}}
QPushButton[kind="menu"]:hover {{ border-color: {PRIMARY}; background: #fafbff; }}
QPushButton[kind="menu"]:focus {{ border: 2px solid {PRIMARY}; padding: 0px; }}
QPushButton[kind="menu"]:disabled {{ background: #eef0f5; border-color: {BORDER}; }}

QFrame#panel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}
QFrame#hero {{
    border: none; border-radius: {RADIUS}px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5a66e0, stop:1 #3f49b8);
}}
QFrame#tile {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}px; }}
QFrame#choice {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 12px; }}
QFrame#choice:hover {{ border-color: {PRIMARY}; background: #fafbff; }}
QFrame#choice[selected="true"] {{ background: {PRIMARY_SOFT}; border: 2px solid {PRIMARY}; }}
QLabel#choiceNumber {{
    background: #eef0f5; color: {TEXT_MUTED}; border-radius: 13px; font-weight: 700;
}}
QFrame#choice[selected="true"] QLabel#choiceNumber {{ background: {PRIMARY}; color: #ffffff; }}
QLabel#choiceMark {{ color: {PRIMARY}; font-weight: 700; }}
QLabel#badge {{
    background: {PRIMARY_SOFT}; color: {PRIMARY}; border-radius: 18px; font-weight: 700;
}}
QLabel#pill {{
    background: {PRIMARY_SOFT}; color: {PRIMARY}; border-radius: 11px; padding: 3px 10px;
    font-weight: 600;
}}

QProgressBar {{ border: none; border-radius: 4px; background: #dfe3ec; }}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 4px; }}
QProgressBar[tone="onPrimary"] {{ background: rgba(255, 255, 255, 70); }}
QProgressBar[tone="onPrimary"]::chunk {{ background: #ffffff; }}

QLabel#keycap {{
    background: {SURFACE}; color: {TEXT_MUTED}; border: 1px solid {BORDER_STRONG};
    border-bottom-width: 2px; border-radius: 5px; padding: 1px 7px; min-width: 12px;
}}
QLabel#statusDone {{ color: {SUCCESS}; font-weight: 700; }}
QLabel#statusMemorized {{ color: {WARNING}; font-weight: 700; }}

QLineEdit#search {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 10px;
    padding: 9px 14px; selection-background-color: {PRIMARY_SOFT}; selection-color: {TEXT};
}}
QLineEdit#search:focus {{ border: 2px solid {PRIMARY}; padding: 8px 13px; }}

QTableWidget, QTableView {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}px;
    gridline-color: transparent; outline: none;
    selection-background-color: {PRIMARY_SOFT}; selection-color: {TEXT};
    alternate-background-color: #f8f9fc;
}}
QTableWidget::item, QTableView::item {{ padding: 8px 10px; border-bottom: 1px solid #eef0f5; }}
QHeaderView::section {{
    background: #f8f9fc; color: {TEXT_MUTED}; font-weight: 600;
    padding: 9px 10px; border: none; border-bottom: 1px solid {BORDER};
}}
QTableCornerButton::section {{ background: #f8f9fc; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #c7cddb; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #a9b1c4; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QCheckBox {{ color: {TEXT_MUTED}; spacing: 8px; }}
QMessageBox {{ background: {SURFACE}; }}
"""


def app_icon() -> QIcon:
    """앱 아이콘을 그려서 만든다. 그림 파일을 따로 배포하지 않아도 된다."""
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(PRIMARY))
    painter.drawRoundedRect(QRectF(4, 4, 120, 120), 28, 28)
    font = QFont(FONT_FAMILIES, 60)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRectF(4, 0, 120, 120), Qt.AlignmentFlag.AlignCenter, "V")
    painter.end()
    return QIcon(pixmap)
