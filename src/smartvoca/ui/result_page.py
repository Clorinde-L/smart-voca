#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험 결과 화면 (S-04): 일차 시험·오답 시험 공용
# 파일 위치: src/smartvoca/ui/result_page.py
from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..core.models import ExamResult
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    PageHeader,
    ScoreRing,
    add_shortcut,
    fill_table,
    hint_label,
    make_button,
    make_panel,
    make_table,
    primary_button,
    set_role,
    text_label,
)


def _cheer(correct: int, total: int) -> str:
    ratio = correct / total if total else 0
    if ratio == 1:
        return "모두 맞혔습니다. 완벽해요!"
    if ratio >= 0.9:
        return "거의 다 맞혔습니다. 아주 좋아요."
    if ratio >= 0.6:
        return "잘하고 있어요. 틀린 단어만 한 번 더 보면 됩니다."
    return "괜찮아요. 틀린 단어는 오답 학습에서 다시 볼 수 있습니다."


class ResultPage(QWidget):
    """채점 결과를 보여 준다. 이 화면이 뜬 시점에 기록은 이미 저장되어 있다 (FR-26).

    제출은 되돌릴 수 없으므로 '뒤로'가 없다.
    """

    next_day_clicked = pyqtSignal(int)
    wrong_list_clicked = pyqtSignal()
    home_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._next_day: int | None = None
        self._is_wrong_exam = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader(show_back=False)
        layout.addWidget(self.header)

        summary = make_panel(shadow=True)
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(28, 20, 28, 20)
        summary_layout.setSpacing(28)
        self.score_ring = ScoreRing()
        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)
        self.status_label = text_label("", 15, bold=True)
        self.status_label.setWordWrap(True)
        self.cheer_label = hint_label("")
        self.graduated_label = text_label("", 11, role="success")
        self.graduated_label.setWordWrap(True)
        text_layout.addStretch(1)
        text_layout.addWidget(self.status_label)
        text_layout.addWidget(self.cheer_label)
        text_layout.addWidget(self.graduated_label)
        text_layout.addStretch(1)
        summary_layout.addWidget(self.score_ring)
        summary_layout.addLayout(text_layout, 1)
        layout.addWidget(summary)

        self.table_title = text_label("", 11, bold=True)
        layout.addWidget(self.table_title)
        # 정답과 고른 답을 색이 아니라 열 제목으로 구분한다
        self.table = make_table(["단어", "정답", "내가 고른 답"], stretch_columns=[1, 2])
        layout.addWidget(self.table, 1)
        self.perfect_label = text_label("틀린 단어가 없습니다", 13, role="muted")
        self.perfect_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.perfect_label, 1)

        button_row = QHBoxLayout()
        self.home_button = make_button("메인으로")
        self.home_button.clicked.connect(self.home_clicked)
        self.primary_button = primary_button("")
        self.primary_button.setMinimumWidth(170)
        self.primary_button.clicked.connect(self._press_primary)
        button_row.addStretch(1)
        button_row.addWidget(self.home_button)
        button_row.addWidget(self.primary_button)
        layout.addLayout(button_row)

        add_shortcut(self, Qt.Key.Key_Return, self._press_enter)
        add_shortcut(self, Qt.Key.Key_Enter, self._press_enter)
        add_shortcut(self, Qt.Key.Key_Escape, self.home_clicked.emit)

    def show_day_result(
        self, day_no: int, result: ExamResult, is_retest: bool, next_day: int | None
    ) -> None:
        """일차 시험 결과. next_day 가 None 이면 더 열 일차가 없다."""
        self._is_wrong_exam = False
        self._next_day = None if is_retest else next_day
        self.header.set_title(f"{day_no}일차 시험 결과")
        if is_retest:
            status = f"{day_no}일차 재시험"
        elif next_day is None:
            status = "모든 일차를 완료했습니다"
        else:
            status = f"{day_no}일차 완료 · {next_day}일차가 열렸습니다"
        self.status_label.setText(status)
        self.graduated_label.setVisible(False)
        self.primary_button.setVisible(self._next_day is not None)
        if self._next_day is not None:
            self.primary_button.setText(f"{self._next_day}일차 학습")
        self._show_result(result, "오답 목록에 추가되었습니다")

    def show_wrong_result(
        self, result: ExamResult, graduated: Sequence[str], remaining: int
    ) -> None:
        """오답 시험 결과. graduated 는 이번에 오답 목록에서 빠진 단어."""
        self._is_wrong_exam = True
        self._next_day = None
        self.header.set_title("오답 시험 결과")
        self.status_label.setText(
            f"오답 목록에서 빠진 단어 {len(graduated)}개 · 남은 오답 {remaining}개"
        )
        self.graduated_label.setVisible(bool(graduated))
        self.graduated_label.setText("✓ 목록에서 빠진 단어: " + ", ".join(graduated))
        self.primary_button.setVisible(True)
        self.primary_button.setText("오답 목록으로")
        self._show_result(result, "연속 정답이 0 으로 돌아갑니다")

    def _show_result(self, result: ExamResult, wrong_note: str) -> None:
        self.score_ring.set_score(result.correct_count, result.total)
        self.cheer_label.setText(_cheer(result.correct_count, result.total))
        set_role(self.graduated_label, "success")
        has_wrong = bool(result.wrong_items)
        self.table_title.setVisible(has_wrong)
        self.table.setVisible(has_wrong)
        self.perfect_label.setVisible(not has_wrong)
        if has_wrong:
            self.table_title.setText(f"틀린 단어 {len(result.wrong_items)}개 — {wrong_note}")
            fill_table(
                self.table,
                [
                    [item.word, item.correct_meaning, item.chosen_meaning]
                    for item in result.wrong_items
                ],
                bold_columns=(0,),
            )

    def _press_primary(self) -> None:
        if self._is_wrong_exam:
            self.wrong_list_clicked.emit()
        elif self._next_day is not None:
            self.next_day_clicked.emit(self._next_day)

    def _press_enter(self) -> None:
        if self.primary_button.isVisible():
            self._press_primary()
        else:
            self.home_clicked.emit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.table.resizeRowsToContents()  # 폭이 바뀌면 줄바꿈 위치가 달라진다
