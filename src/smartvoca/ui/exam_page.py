#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험 응시 화면 (S-03): 일차 시험·오답 시험 공용
# 파일 위치: src/smartvoca/ui/exam_page.py
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QProgressBar, QVBoxLayout, QWidget

from ..core.models import CHOICE_COUNT, Exam
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    ChoiceItem,
    PageHeader,
    QuestionDots,
    add_shortcut,
    hint_label,
    make_button,
    primary_button,
    text_label,
)

MAX_DOTS = 60  # 문제가 이보다 많으면(오답이 많이 쌓인 오답 시험) 점 대신 막대로 보여 준다


class ExamPage(QWidget):
    """문제를 한 개씩 보여 주고 답을 모은다. 정오는 여기서 보여 주지 않는다 (ADR-10).

    채점과 저장은 하지 않는다. 모은 답을 submitted 로 내보내면 MainWindow 가 세션에 넘긴다.
    """

    back_requested = pyqtSignal()   # 뒤로·Esc: MainWindow 가 중단 확인을 띄운다
    submitted = pyqtSignal(list)    # 문제 순서대로 고른 보기 위치

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._exam: Exam | None = None
        self._answers: list[int | None] = []
        self._position = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader()
        self.header.back_clicked.connect(self.back_requested)
        layout.addWidget(self.header)

        # 답한 문제와 현재 문제를 한눈에 보여 주고, 눌러서 바로 옮겨 갈 수 있게 한다
        self.dots = QuestionDots()
        self.dots.jump_requested.connect(self.go_to)
        layout.addWidget(self.dots)
        self.answered_bar = QProgressBar()
        self.answered_bar.setTextVisible(False)
        self.answered_bar.setFixedHeight(6)
        layout.addWidget(self.answered_bar)
        self.answered_label = hint_label("")
        self.answered_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.answered_label)

        self.word_label = text_label("", 32, bold=True)
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setWordWrap(True)
        layout.addWidget(self.word_label)
        layout.addSpacing(4)

        self.choice_items: list[ChoiceItem] = []
        choices_layout = QVBoxLayout()
        choices_layout.setSpacing(10)
        for index in range(CHOICE_COUNT):
            item = ChoiceItem(index)
            item.clicked.connect(self.choose)
            self.choice_items.append(item)
            choices_layout.addWidget(item)
            add_shortcut(self, str(index + 1), lambda i=index: self.choose(i))
        layout.addLayout(choices_layout)
        layout.addStretch(1)

        bottom_row = QHBoxLayout()
        self.prev_button = make_button("←  이전")
        self.next_button = make_button("다음  →")
        self.prev_button.clicked.connect(self.go_prev)
        self.next_button.clicked.connect(self.go_next)
        self.unanswered_label = hint_label("")
        self.unanswered_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.submit_button = primary_button("제출")
        self.submit_button.setMinimumWidth(120)
        self.submit_button.clicked.connect(self._submit)
        bottom_row.addWidget(self.prev_button)
        bottom_row.addWidget(self.next_button)
        bottom_row.addWidget(self.unanswered_label, 1)
        bottom_row.addWidget(self.submit_button)
        layout.addLayout(bottom_row)

        add_shortcut(self, Qt.Key.Key_Right, self.go_next)
        add_shortcut(self, Qt.Key.Key_Left, self.go_prev)
        add_shortcut(self, Qt.Key.Key_Escape, self.back_requested.emit)
        add_shortcut(self, Qt.Key.Key_Return, self._press_enter)
        add_shortcut(self, Qt.Key.Key_Enter, self._press_enter)

    def start(self, title: str, exam: Exam) -> None:
        self._exam = exam
        self._answers = [None] * len(exam.questions)
        self._position = 0
        self.header.set_title(title)
        use_dots = len(self._answers) <= MAX_DOTS
        self.dots.setVisible(use_dots)
        self.answered_bar.setVisible(not use_dots)
        self.answered_bar.setMaximum(len(self._answers))
        self._render()

    @property
    def answers(self) -> list[int | None]:
        return list(self._answers)

    @property
    def position(self) -> int:
        """현재 문제 (0 부터)."""
        return self._position

    def choose(self, choice_index: int) -> None:
        """보기를 고른다. 다른 보기를 다시 고르면 바뀐다. 자동으로 다음 문제로 넘어가지 않는다."""
        if self._exam is None:
            return
        self._answers[self._position] = choice_index
        self._render()

    def go_to(self, position: int) -> None:
        if self._exam is not None and 0 <= position < len(self._answers):
            self._position = position
            self._render()

    def go_next(self) -> None:
        self.go_to(self._position + 1)

    def go_prev(self) -> None:
        self.go_to(self._position - 1)

    def _press_enter(self) -> None:
        # 마지막 문제에서 모두 답했으면 제출, 아니면 다음 문제로
        if self._position == len(self._answers) - 1 and self.submit_button.isEnabled():
            self._submit()
        else:
            self.go_next()

    def _submit(self) -> None:
        if self._exam is not None and None not in self._answers:
            self.submitted.emit(list(self._answers))

    def _render(self) -> None:
        question = self._exam.questions[self._position]
        total = len(self._answers)
        answered = sum(answer is not None for answer in self._answers)
        self.header.set_info(f"문제 {self._position + 1} / {total}")
        self.answered_label.setText(f"답한 문제 {answered} / {total}")
        self.dots.set_state([answer is not None for answer in self._answers], self._position)
        self.answered_bar.setValue(answered)
        self.word_label.setText(question.word)
        for index, item in enumerate(self.choice_items):
            item.set_text(question.choices[index])
            item.set_selected(self._answers[self._position] == index)
        self.prev_button.setEnabled(self._position > 0)
        self.next_button.setEnabled(self._position < total - 1)

        # 제출은 모든 문제에 답해야 켜진다. 꺼져 있는 이유를 옆에 적는다 (FR-15)
        self.submit_button.setEnabled(answered == total)
        missing = [str(i + 1) for i, answer in enumerate(self._answers) if answer is None]
        if not missing:
            self.unanswered_label.setText("모든 문제에 답했습니다. 제출할 수 있습니다")
        elif len(missing) <= 6:
            self.unanswered_label.setText(f"답하지 않은 문제: {', '.join(missing)}번")
        else:
            self.unanswered_label.setText(f"답하지 않은 문제 {len(missing)}개")
