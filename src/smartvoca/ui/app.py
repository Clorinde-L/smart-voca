#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 프로그램 시작: QApplication 생성, 세션 열기, 메인 창 표시
# 파일 위치: src/smartvoca/ui/app.py
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from .. import paths
from ..session import AppSession, WordbookLoadError
from . import dialogs
from .main_window import MainWindow
from .widgets import APP_STYLE


def create_application(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName("스마트 보카")
    app.setStyle("Fusion")
    # 화면 색을 직접 정했으므로 Windows 가 어두운 테마여도 밝은 배색으로 고정한다
    style_hints = app.styleHints()
    if hasattr(style_hints, "setColorScheme"):
        style_hints.setColorScheme(Qt.ColorScheme.Light)
    app.setFont(QFont("Malgun Gothic", 11))
    app.setStyleSheet(APP_STYLE)
    return app


def main() -> int:
    app = create_application(sys.argv)
    try:
        session = AppSession.open(paths.userdata_dir(), paths.default_wordbook_path())
    except WordbookLoadError as error:
        QMessageBox.critical(
            None,
            "스마트 보카",
            f"기본 단어장을 읽을 수 없어 시작할 수 없습니다.\n"
            f"{paths.default_wordbook_path()}\n\n{error}",
        )
        return 1
    window = MainWindow(session)
    window.show()
    for notice in session.startup_notices:
        dialogs.show_startup_notice(window, notice)
    return app.exec()
