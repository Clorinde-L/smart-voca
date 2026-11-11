#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 확인·알림·파일 선택 대화상자 (UI/UX 설계서 DL-01 ~ DL-05)
# 파일 위치: src/smartvoca/ui/dialogs.py
"""대화상자를 함수로 모아 둔다.

MainWindow 는 `dialogs.함수()` 로 부른다. 그래야 화면 테스트에서 이 함수들만 바꿔 끼워
사람이 버튼을 누르지 않아도 흐름을 검증할 수 있다.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from ..core.models import NoticeKind, StartupNotice, ValidationIssue

MAX_ISSUES_SHOWN = 20
CSV_FILTER = "CSV 파일 (*.csv)"


def _confirm(parent: QWidget, title: str, text: str, yes_text: str, no_text: str) -> bool:
    """기록을 지우거나 버리는 확인. 안전한 쪽(아니오)을 기본 버튼으로 둔다."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    yes_button = box.addButton(yes_text, QMessageBox.ButtonRole.AcceptRole)
    no_button = box.addButton(no_text, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(no_button)
    box.setEscapeButton(no_button)
    box.exec()
    return box.clickedButton() is yes_button


def confirm_replace_wordbook(
    parent: QWidget,
    file_name: str,
    word_count: int,
    day_count: int,
    done_days: int,
    wrong_count: int,
) -> bool:
    """DL-01 단어장 교체 확인."""
    text = (
        f'단어장을 "{file_name}" ({word_count:,} 단어, {day_count}일차)로 바꿉니다.\n\n'
        f"지금까지의 학습 기록(완료 일차 {done_days}개, 오답 단어 {wrong_count}개)이 "
        "모두 지워지고 되돌릴 수 없습니다.\n"
        "오답 단어를 남기려면 먼저 '오답 목록 내보내기'를 하세요.\n\n"
        "계속할까요?"
    )
    return _confirm(parent, "단어장 교체", text, "바꾸기", "취소")


def show_validation_issues(parent: QWidget, issues: list[ValidationIssue]) -> None:
    """DL-02 단어장 검증 오류. 처음 20건과 전체 건수를 보여 준다."""
    lines = []
    for issue in issues[:MAX_ISSUES_SHOWN]:
        prefix = f"{issue.line_no}번째 줄: " if issue.line_no is not None else ""
        lines.append(prefix + issue.message)
    if len(issues) > MAX_ISSUES_SHOWN:
        lines.append(f"… 외 {len(issues) - MAX_ISSUES_SHOWN}건")
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("단어장을 불러올 수 없습니다")
    box.setText(f"파일에서 문제 {len(issues)}건을 찾았습니다. 고친 뒤 다시 불러와 주세요.")
    box.setInformativeText("\n".join(lines))
    box.exec()


def confirm_abort_exam(parent: QWidget) -> bool:
    """DL-03 시험 중단 확인."""
    text = "시험을 그만둘까요?\n지금까지 고른 답은 저장되지 않고 이 시험은 없던 것이 됩니다."
    return _confirm(parent, "시험 중단", text, "그만두기", "계속 풀기")


def show_startup_notice(parent: QWidget, notice: StartupNotice) -> None:
    """DL-04 시작할 때의 알림 (기록 손상, 단어장 사본 오류)."""
    if notice.kind is NoticeKind.PROGRESS_CORRUPT:
        text = "학습 기록을 읽을 수 없어 처음 상태로 시작합니다."
    else:
        text = "저장된 단어장을 읽을 수 없어 기본 단어장으로 시작합니다."
    QMessageBox.warning(
        parent, "학습 기록", f'{text}\n기존 파일은 "{notice.backup_path}" 에 보존했습니다.'
    )


def show_save_error(parent: QWidget, error: Exception) -> None:
    """DL-04 저장 실패."""
    QMessageBox.critical(parent, "학습 기록", f"학습 기록을 저장하지 못했습니다.\n({error})")


def show_error(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)


def show_info(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def ask_open_csv(parent: QWidget) -> Path | None:
    """DL-05 열기."""
    name, _ = QFileDialog.getOpenFileName(parent, "단어장 불러오기", "", CSV_FILTER)
    return Path(name) if name else None


def ask_save_csv(parent: QWidget, title: str, default_name: str) -> Path | None:
    """DL-05 저장."""
    name, _ = QFileDialog.getSaveFileName(parent, title, default_name, CSV_FILTER)
    return Path(name) if name else None
