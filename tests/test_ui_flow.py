#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 화면 흐름 테스트: 창을 화면 없이(offscreen) 띄워 버튼·단축키로 조작
# 파일 위치: tests/test_ui_flow.py
"""UI/UX 설계서 §6 의 사용 흐름을 실제 위젯으로 따라가 본다.

대화상자는 사람이 눌러야 닫히므로 dialogs 모듈의 함수를 바꿔 끼운다.
"""
from __future__ import annotations

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # 창을 실제 화면에 띄우지 않는다

import pytest
from PyQt6.QtTest import QTest
from conftest import DEFAULT_CSV, DEFAULT_DAY_COUNT, DEFAULT_WORD_COUNT, write_csv

from smartvoca.core.models import DayStatus, Exam, Question
from smartvoca.session import AppSession
from smartvoca.ui import dialogs
from smartvoca.ui.app import create_application
from smartvoca.ui.card_page import CardMode
from smartvoca.ui.exam_page import AUTO_ADVANCE_MS
from smartvoca.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return create_application([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    # 알림 대화상자는 뜨지 않게 하고, 무엇이 불렸는지만 적어 둔다
    shown = []
    for name in ("show_info", "show_error", "show_save_error", "show_validation_issues"):
        monkeypatch.setattr(dialogs, name, lambda *args, _n=name: shown.append((_n, args)))
    session = AppSession.open(tmp_path / "userdata", DEFAULT_CSV, random.Random(1))
    main_window = MainWindow(session)
    main_window.shown_dialogs = shown
    main_window.show()
    yield main_window
    main_window._exam = None  # 닫을 때 시험 중단 확인이 뜨지 않게
    main_window.close()


def view_all_cards(window: MainWindow) -> None:
    while window.card_page.next_button.isEnabled():
        window.card_page.next_button.click()


def answer_all(window: MainWindow, wrong_positions: set[int] = frozenset()) -> None:
    """모든 문제에 답한다. wrong_positions 에 든 문제(0 부터)만 틀린다."""
    page = window.exam_page
    for position, question in enumerate(window._exam.questions):
        choice = question.answer_index
        if position in wrong_positions:
            choice = (choice + 1) % 4
        page.choice_items[choice].clicked.emit(choice)
        if page.next_button.isEnabled():
            page.next_button.click()


def finish_day(window: MainWindow, wrong_positions: set[int] = frozenset()) -> None:
    window.home_page.start_button.click()
    view_all_cards(window)
    window.card_page.action_button.click()
    answer_all(window, wrong_positions)
    window.exam_page.submit_button.click()


def test_메인_화면이_처음_상태를_보여_준다(window):
    home = window.home_page
    assert window.stack.currentWidget() is home
    assert home.today_label.text() == "1일차"
    assert home.start_button.text() == "1일차 학습 시작"
    assert home.progress_label.text() == f"0 / {DEFAULT_DAY_COUNT} 일차 완료"
    assert not home.past_days_button.isEnabled()
    assert home.wrong_button.title() == "오답 학습 (0)"
    assert f"기본 토익 {DEFAULT_WORD_COUNT:,} 단어" in home.wordbook_label.text()


def test_하루_학습_흐름(window):
    """UI/UX 설계서 §6.1: 카드 20장 → 시험 → 결과 → 메인."""
    window.home_page.start_button.click()
    card = window.card_page
    assert window.stack.currentWidget() is card
    assert card.header.info() == "1 / 20"
    assert card.word_label.text() == "executive"  # 기본 단어장 첫 단어
    assert card.meaning_label.text() == window.session.words[0].meaning
    assert not card.prev_button.isEnabled()
    assert not card.action_button.isEnabled()

    for _ in range(18):
        card.next_button.click()
    assert not card.action_button.isEnabled()  # 19장째까지는 꺼져 있다
    card.next_button.click()
    assert card.action_button.isEnabled()      # 20장째를 보는 순간 켜진다
    assert not card.next_button.isEnabled()
    assert window.session.day_status(1) is DayStatus.MEMORIZED

    card.action_button.click()
    exam = window.exam_page
    assert window.stack.currentWidget() is exam
    assert not exam.submit_button.isEnabled()
    assert len({item.text() for item in exam.choice_items}) == 4

    answer_all(window, wrong_positions={0, 5, 9})
    assert exam.submit_button.isEnabled()
    wrong_words = {window._exam.questions[i].word for i in (0, 5, 9)}
    exam.submit_button.click()

    result = window.result_page
    assert window.stack.currentWidget() is result
    assert result.score_ring.text() == "17 / 20"
    assert result.status_label.text() == "1일차 완료 · 2일차가 열렸습니다"
    assert result.table.rowCount() == 3
    assert {result.table.item(row, 0).text() for row in range(3)} == wrong_words
    assert result.primary_button.text() == "2일차 학습"

    result.home_button.click()
    home = window.home_page
    assert home.today_label.text() == "2일차"
    assert home.progress_label.text() == f"1 / {DEFAULT_DAY_COUNT} 일차 완료"
    assert home.wrong_button.title() == "오답 학습 (3)"
    assert home.past_days_button.isEnabled()


def test_답하지_않은_문제가_있으면_제출할_수_없다(window):
    window.home_page.start_button.click()
    view_all_cards(window)
    window.card_page.action_button.click()
    exam = window.exam_page
    exam.choice_items[0].clicked.emit(0)
    assert exam.answered_label.text() == "답한 문제 1 / 20"
    assert not exam.submit_button.isEnabled()
    assert exam.choice_items[0].is_selected()
    exam.choice_items[2].clicked.emit(2)  # 답을 바꿀 수 있다
    assert exam.choice_items[2].is_selected() and not exam.choice_items[0].is_selected()
    exam.next_button.click()
    exam.prev_button.click()
    assert exam.choice_items[2].is_selected()  # 돌아와도 고른 답이 남아 있다


def test_시험을_그만두면_기록이_바뀌지_않는다(window, monkeypatch):
    window.home_page.start_button.click()
    view_all_cards(window)
    window.card_page.action_button.click()
    answer_all(window, wrong_positions={0})

    monkeypatch.setattr(dialogs, "confirm_abort_exam", lambda parent: False)
    window.exam_page.header.click_back()
    assert window.stack.currentWidget() is window.exam_page  # '계속 풀기'

    monkeypatch.setattr(dialogs, "confirm_abort_exam", lambda parent: True)
    window.exam_page.header.click_back()
    assert window.stack.currentWidget() is window.card_page
    assert window.session.day_status(1) is DayStatus.MEMORIZED
    assert window.session.wrong_list() == []


def test_지난_일차에서_복습과_재시험을_한다(window):
    finish_day(window)
    window.result_page.home_button.click()
    window.home_page.past_days_button.click()
    days = window.day_list_page
    assert window.stack.currentWidget() is days
    assert days.table.rowCount() == 1
    assert days.table.item(0, 2).text() == "완료"
    assert not days.review_button.isEnabled()

    days.table.selectRow(0)
    assert days.review_button.isEnabled() and days.exam_button.isEnabled()
    days.review_button.click()
    card = window.card_page
    assert card.mode is CardMode.REVIEW
    assert card.header.title() == "1일차 복습"
    assert not card.action_button.isVisible()  # 복습에는 시험 버튼이 없다
    before = window.session.summary()
    view_all_cards(window)
    assert window.session.summary() == before  # 복습은 기록을 바꾸지 않는다
    card.header.click_back()
    assert window.stack.currentWidget() is days

    days.table.selectRow(0)
    days.exam_button.click()
    answer_all(window, wrong_positions={3})
    window.exam_page.submit_button.click()
    result = window.result_page
    assert result.status_label.text() == "1일차 재시험"
    assert not result.primary_button.isVisible()
    assert window.session.summary().wrong_list_size == 1
    assert window.session.summary().current_day == 2


def test_오답_정리_흐름(window):
    """UI/UX 설계서 §6.2: 오답 목록 → 카드 → 오답 시험을 3번 → 목록에서 빠짐."""
    finish_day(window, wrong_positions={0, 1})
    window.result_page.home_button.click()

    for round_no in range(1, 4):
        window.home_page.wrong_button.click()
        wrong = window.wrong_list_page
        assert window.stack.currentWidget() is wrong
        assert wrong.table.rowCount() == 2
        assert wrong.table.item(0, 3).text() == f"{round_no - 1} / 3"
        wrong.study_button.click()
        card = window.card_page
        assert card.mode is CardMode.WRONG
        assert f"연속 정답 {round_no - 1} / 3" in card.stats_label.text()
        assert not card.action_button.isEnabled()
        view_all_cards(window)
        assert card.action_button.isEnabled()
        card.action_button.click()
        answer_all(window)
        window.exam_page.submit_button.click()
        result = window.result_page
        assert result.score_ring.text() == "2 / 2"
        if round_no < 3:
            assert result.status_label.text() == "오답 목록에서 빠진 단어 0개 · 남은 오답 2개"
            result.home_button.click()

    assert result.status_label.text() == "오답 목록에서 빠진 단어 2개 · 남은 오답 0개"
    assert result.graduated_label.isVisible()
    result.primary_button.click()
    wrong = window.wrong_list_page
    assert window.stack.currentWidget() is wrong
    assert wrong.empty_label.isVisible() and not wrong.table.isVisible()
    assert not wrong.study_button.isEnabled() and not wrong.export_button.isEnabled()


def test_단어장을_불러오면_확인을_거쳐_교체된다(window, tmp_path, monkeypatch):
    """UI/UX 설계서 §6.3."""
    finish_day(window, wrong_positions={0})
    window.result_page.home_button.click()
    window.home_page.wordbook_button.click()
    page = window.wordbook_page
    assert f"기본 토익 {DEFAULT_WORD_COUNT:,} 단어 ({DEFAULT_DAY_COUNT}일차)" in page.current_label.text()

    bad = write_csv(tmp_path / "bad.csv", ["word,meaning", "a,1", "A,2", "c,3", "d,4"])
    monkeypatch.setattr(dialogs, "ask_open_csv", lambda parent: bad)
    page.import_button.click()
    assert window.shown_dialogs[-1][0] == "show_validation_issues"
    assert len(window.session.words) == DEFAULT_WORD_COUNT

    good = write_csv(
        tmp_path / "good.csv", ["word,meaning"] + [f"w{i},뜻{i}" for i in range(45)]
    )
    monkeypatch.setattr(dialogs, "ask_open_csv", lambda parent: good)
    asked = []
    monkeypatch.setattr(
        dialogs, "confirm_replace_wordbook", lambda *args: asked.append(args[1:]) or False
    )
    page.import_button.click()
    assert asked == [("good.csv", 45, 3, 1, 1)]  # 파일명, 단어 수, 일차 수, 완료 일차, 오답 수
    assert len(window.session.words) == DEFAULT_WORD_COUNT     # '취소'하면 그대로

    monkeypatch.setattr(dialogs, "confirm_replace_wordbook", lambda *args: True)
    page.import_button.click()
    home = window.home_page
    assert window.stack.currentWidget() is home
    assert home.today_label.text() == "1일차"
    assert home.progress_label.text() == "0 / 3 일차 완료"
    assert home.wrong_button.title() == "오답 학습 (0)"
    assert "사용자 단어장 45 단어" in home.wordbook_label.text()


def test_단어장과_오답_목록을_내보낸다(window, tmp_path, monkeypatch):
    finish_day(window, wrong_positions={0})
    window.result_page.home_button.click()
    window.home_page.wordbook_button.click()
    targets = iter([tmp_path / "wb.csv", tmp_path / "wrong.csv"])
    monkeypatch.setattr(dialogs, "ask_save_csv", lambda parent, title, name: next(targets))
    window.wordbook_page.export_wordbook_button.click()
    window.wordbook_page.export_wrong_button.click()
    assert len((tmp_path / "wb.csv").read_text(encoding="utf-8-sig").splitlines()) == DEFAULT_WORD_COUNT + 1  # 헤더 포함
    assert len((tmp_path / "wrong.csv").read_text(encoding="utf-8-sig").splitlines()) == 2


def test_가장_긴_뜻이_최소_창_크기에서_잘리지_않는다(window, qapp):
    """NFR-07: 줄바꿈된 글의 높이가 라벨에 주어진 높이 안에 들어오는지 본다."""
    longest = max(window.session.words, key=lambda word: len(word.meaning))
    window.resize(800, 600)

    window.card_page.start(CardMode.REVIEW, "긴 뜻", [longest])
    window._go(window.card_page)
    qapp.processEvents()
    label = window.card_page.meaning_label
    assert label.heightForWidth(label.width()) <= label.height()

    # 긴 뜻이 보기로 들어간 문제를 직접 띄운다
    choices = (longest.meaning, "뜻 A", "뜻 B", "뜻 C")
    window.exam_page.start("긴 뜻", Exam((Question(longest.word, choices, 0),)))
    window._go(window.exam_page)
    qapp.processEvents()
    text_label = window.exam_page.choice_items[0].text_label_widget()
    assert text_label.heightForWidth(text_label.width()) <= text_label.height()
    assert window.exam_page.choice_items[0].height() > window.exam_page.choice_items[1].height() - 1


def test_메인_화면의_현황_칸이_기록을_따라간다(window):
    home = window.home_page
    assert (home.done_tile.value(), home.learned_tile.value(), home.wrong_tile.value()) == (
        "0일",
        "0개",
        "0개",
    )
    finish_day(window, wrong_positions={0, 1})
    window.result_page.home_button.click()
    assert (home.done_tile.value(), home.learned_tile.value(), home.wrong_tile.value()) == (
        "1일",
        "20개",
        "2개",
    )


def test_뜻을_가리고_외울_수_있다(window):
    window.home_page.start_button.click()
    card = window.card_page
    assert card.meaning_label.isVisible() and not card.reveal_button.isVisible()  # 기본은 함께 보기

    card.hide_check.setChecked(True)
    assert not card.meaning_label.isVisible() and card.reveal_button.isVisible()
    card.reveal_button.click()
    assert card.meaning_label.isVisible()
    card.next_button.click()
    assert not card.meaning_label.isVisible()  # 다음 카드는 다시 가려진다
    card.reveal_meaning()                      # Space 단축키가 부르는 동작
    assert card.meaning_label.text() == window.session.words[1].meaning
    assert card.meaning_label.isVisible()

    view_all_cards(window)
    assert card.action_button.isEnabled()      # 가리고 봐도 암기 완료는 같다
    card.hide_check.setChecked(False)


def test_문제_번호_점을_눌러_그_문제로_간다(window):
    window.home_page.start_button.click()
    view_all_cards(window)
    window.card_page.action_button.click()
    exam = window.exam_page
    assert exam.dots.isVisible() and not exam.answered_bar.isVisible()
    exam.dots.jump_requested.emit(11)
    assert exam.position == 11
    assert exam.header.info() == "문제 12 / 20"
    assert exam.word_label.text() == window._exam.questions[11].word


# ── 시험 자동 넘김 (UI/UX 설계서 UD-05) ─────────────────────────
def start_first_exam(window: MainWindow):
    window.home_page.start_button.click()
    view_all_cards(window)
    window.card_page.action_button.click()
    return window.exam_page


def test_답을_고르면_잠시_뒤_다음_문제로_넘어간다(window):
    exam = start_first_exam(window)
    exam.choice_items[1].clicked.emit(1)
    assert exam.position == 0 and exam.auto_advance_pending  # 고른 답을 볼 틈을 준다
    QTest.qWait(AUTO_ADVANCE_MS + 150)
    assert exam.position == 1 and not exam.auto_advance_pending
    exam.prev_button.click()
    assert exam.choice_items[1].is_selected()  # 돌아가 답을 고칠 수 있다 (FR-15)


def test_직접_옮겨_가면_자동_넘김은_취소된다(window):
    exam = start_first_exam(window)
    exam.choice_items[0].clicked.emit(0)
    exam.dots.jump_requested.emit(5)
    QTest.qWait(AUTO_ADVANCE_MS + 150)
    assert exam.position == 5


def test_마지막_문제에_답하면_안_푼_문제로_간다(window):
    exam = start_first_exam(window)
    exam.dots.jump_requested.emit(19)
    exam.choice_items[0].clicked.emit(0)
    QTest.qWait(AUTO_ADVANCE_MS + 150)
    assert exam.position == 0  # 1번부터 아직 안 풀었다


def test_모두_풀면_제출_버튼에_초점이_간다(window, monkeypatch):
    exam = start_first_exam(window)
    focused = []
    # offscreen 에서는 활성 창이 없어 hasFocus() 로 확인할 수 없으므로 setFocus 호출을 기록한다
    monkeypatch.setattr(exam.submit_button, "setFocus", lambda *args: focused.append(True))
    answer_all(window)
    QTest.qWait(AUTO_ADVANCE_MS + 150)
    assert exam.position == 19 and exam.submit_button.isEnabled()
    assert focused


def test_시험과_카드에_단축키_안내가_있다(window):
    exam = start_first_exam(window)
    assert "보기 선택" in exam.key_hints.texts()
    window.open_review_cards(1)  # 카드를 모두 봐서 1일차는 암기 완료 → 복습할 수 있다
    card = window.card_page
    assert card.mode is CardMode.REVIEW
    assert card.key_hints_no_action.isVisible() and not card.key_hints.isVisible()  # 복습엔 시험 안내가 없다


# ── 단어 목록 검색 (UI/UX 설계서 UD-06) ──────────────────────────
def test_단어_목록에_전체_단어가_일차와_함께_나온다(window):
    window.home_page.wordbook_button.click()
    page = window.wordbook_page
    assert page.proxy.rowCount() == DEFAULT_WORD_COUNT
    assert page.result_label.text() == f"{DEFAULT_WORD_COUNT:,}개"
    assert page.proxy.index(0, 0).data() == "1일차"
    assert page.proxy.index(DEFAULT_WORD_COUNT - 1, 0).data() == f"{DEFAULT_DAY_COUNT}일차"


def test_영단어나_뜻으로_검색한다(window):
    window.home_page.wordbook_button.click()
    page = window.wordbook_page
    page.search_edit.setText("EXECUTIVE")            # 대소문자 무시
    assert page.visible_words() == ["executive"]
    page.search_edit.setText("재고")                 # 뜻으로 찾기
    assert "inventory" in page.visible_words()
    assert all("재고" in page.proxy.index(r, 2).data() for r in range(page.proxy.rowCount()))
    assert page.result_label.text().endswith(f"/ {DEFAULT_WORD_COUNT:,}개")


def test_숫자로_검색하면_그_일차_단어가_나온다(window):
    window.home_page.wordbook_button.click()
    page = window.wordbook_page
    page.search_edit.setText("12일차")
    expected = [w.word for w in window.session.day_words(12)]
    assert page.visible_words() == expected
    page.search_edit.setText(str(DEFAULT_DAY_COUNT))  # 마지막 일차는 남은 단어만
    assert len(page.visible_words()) == DEFAULT_WORD_COUNT - (DEFAULT_DAY_COUNT - 1) * 20


def test_검색_결과가_없으면_안내한다(window):
    window.home_page.wordbook_button.click()
    page = window.wordbook_page
    page.search_edit.setText("zzzz없는단어")
    assert page.visible_words() == []
    assert page.empty_label.isVisible() and not page.table.isVisible()


def test_Esc는_검색어를_먼저_지우고_다음에_뒤로_간다(window):
    window.home_page.wordbook_button.click()
    page = window.wordbook_page
    page.search_edit.setText("account")
    page._press_escape()
    assert page.search_edit.text() == "" and window.stack.currentWidget() is page
    page._press_escape()
    assert window.stack.currentWidget() is window.home_page
