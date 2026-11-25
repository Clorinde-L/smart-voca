#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 학습 화면 라우트: 메인(S-01), 일차 목록·상세(S-05, S-08), 카드(S-02)
# 파일 위치: src/smartvoca/web/routes_study.py
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for

from ..core.models import DayStatus, ExamKind, StudyCard, StudyKind
from .common import app_session, bp, save_error, web_state
from .state import CardMode, CardStudy


# ── S-01 메인 ───────────────────────────────────────────────
@bp.get("/")
def home():
    session = app_session()
    summary = session.summary()
    days = session.days()
    today = None
    if summary.current_day is not None:
        day, status, _ = days[summary.current_day - 1]
        today = {
            "day_no": day.day_no,
            "start": day.start + 1,
            "end": day.end,
            "count": day.size,
            "memorized": status is DayStatus.MEMORIZED,
        }
    return render_template(
        "home.html",
        summary=summary,
        today=today,
        day_map=[(day.day_no, status) for day, status, _ in days],  # '일차 한눈에': 전체 일차를 작은 칸으로
        settings=session.settings(),
    )


# ── S-02 카드 ───────────────────────────────────────────────
@bp.post("/study/today")
def study_today():
    day_no = app_session().summary().current_day
    if day_no is None:
        return redirect(url_for("main.home"))
    return _start_day_cards(day_no)


@bp.post("/study/day/<int:day_no>")
def study_day(day_no: int):
    return _start_day_cards(day_no)


def _start_day_cards(day_no: int):
    """어느 일차든 학습할 수 있다 (ADR-21). 그날 카드 뒤에 복습 카드를 섞는다 (VOCA-FR-013)."""
    session = app_session()
    found = session.day(day_no)
    if found is None:
        flash(f"{day_no}일차는 없습니다.", "error")
        return redirect(url_for("main.days"))
    status, _ = found
    study = CardStudy.start(
        CardMode.DAY,
        f"{day_no}일차 학습",
        session.day_cards(day_no),
        day_no,
        already_done=status is not DayStatus.AVAILABLE,
    )
    return _open_cards(study)


@bp.post("/study/wrong")
def study_wrong():
    entries = app_session().wrong_list()
    if not entries:
        flash("틀린 단어가 없습니다.", "info")
        return redirect(url_for("main.wrong_list"))
    cards = [StudyCard(entry.word, StudyKind.WRONG) for entry in entries]
    wrong_info = {entry.word.id: entry for entry in entries}
    return _open_cards(CardStudy.start(CardMode.WRONG, "오답 학습", cards, wrong_info=wrong_info))


def _open_cards(study: CardStudy):
    web_state().cards = study
    _after_card_move(study)  # 카드가 1장뿐이면 열자마자 모두 본 것이다
    return redirect(url_for("main.cards"))


def _after_card_move(study: CardStudy) -> None:
    """카드를 모두 본 순간 암기 이력을 남긴다 (FR-12, VOCA-FR-014).

    일차 학습은 그 일차 번호와 함께, 오답 학습은 일차 없이 남긴다.
    다시 학습(복습)해도 남긴다 — "언제 몇 번 외웠는지"가 이력이기 때문이다.
    """
    if not study.finish_if_seen_all():
        return
    try:
        app_session().complete_memorize(study.day_no, study.deck.cards)
    except Exception as error:  # noqa: BLE001  DB 오류는 알리고 화면은 계속 쓴다
        save_error(error)


@bp.get("/cards")
def cards():
    state = web_state()
    study = state.cards
    if study is None:
        return redirect(url_for("main.home"))
    if study.mode is CardMode.WRONG:
        back_url = url_for("main.wrong_list")
    else:
        back_url = url_for("main.day_detail", day_no=study.day_no)
    card = study.deck.current
    return render_template(
        "cards.html",
        study=study,
        deck=study.deck,
        card=card,
        word=card.word,
        entry=study.wrong_info.get(card.word.id),
        hide_meaning=state.hide_meaning,
        back_url=back_url,
    )


@bp.post("/cards/next")
def cards_next():
    return _move_card(forward=True)


@bp.post("/cards/prev")
def cards_prev():
    return _move_card(forward=False)


def _move_card(forward: bool):
    study = web_state().cards
    if study is None:
        return redirect(url_for("main.home"))
    moved = study.deck.next() if forward else study.deck.prev()
    if moved:
        _after_card_move(study)
    return redirect(url_for("main.cards"))


@bp.post("/cards/hide")
def cards_hide():
    web_state().hide_meaning = request.form.get("hide") == "on"
    return redirect(url_for("main.cards"))


@bp.post("/cards/action")
def cards_action():
    """시험 보기 / 오답 시험. 카드를 모두 봐야 켜진다 (FR-12, FR-24). 시험 설정 화면으로 간다."""
    study = web_state().cards
    if study is None or not study.unlocked:
        return redirect(url_for("main.cards") if study else url_for("main.home"))
    if study.mode is CardMode.DAY:
        return redirect(url_for("main.exam_setup", kind=ExamKind.DAY.value, day=study.day_no))
    return redirect(url_for("main.exam_setup", kind=ExamKind.WRONG.value))


# ── S-05 일차 목록 · S-08 일차 상세 ─────────────────────────
# 거르기 탭: (쿼리 값, 이름, 남길 상태들). None 은 전체
DAY_FILTERS = (
    ("all", "전체", None),
    ("todo", "학습 전", {DayStatus.AVAILABLE}),
    ("memorized", "시험 남음", {DayStatus.MEMORIZED}),
    ("done", "완료", {DayStatus.DONE}),
)


@bp.get("/days")
def days():
    """전체 일차를 격자로 보여 준다. 골라서 상세로 들어간다 (ADR-22)."""
    session = app_session()
    show = request.args.get("show", "all")
    if show not in {key for key, _, _ in DAY_FILTERS}:
        show = "all"
    wanted = {key: statuses for key, _, statuses in DAY_FILTERS}[show]
    cards, counts = [], {key: 0 for key, _, _ in DAY_FILTERS}
    current = session.summary().current_day
    for day, status, words in session.days():
        for key, _, statuses in DAY_FILTERS:
            if statuses is None or status in statuses:
                counts[key] += 1
        if wanted is not None and status not in wanted:
            continue
        cards.append(
            {
                "day_no": day.day_no,
                "first": words[0].word,
                "last": words[-1].word,
                "count": len(words),
                "status": status,
                "is_current": day.day_no == current,
            }
        )
    return render_template("day_list.html", cards=cards, show=show, filters=DAY_FILTERS, counts=counts)


@bp.get("/days/<int:day_no>")
def day_detail(day_no: int):
    """한 일차의 단어를 먼저 훑어보고 학습·시험을 고른다."""
    session = app_session()
    found = session.day(day_no)
    if found is None:
        abort(404)
    status, words = found
    summary = session.summary()
    return render_template(
        "day_detail.html",
        day_no=day_no,
        total_days=summary.total_days,
        status=status,
        words=words,
        wrong_words={entry.word.id for entry in session.wrong_list()},
        can_exam=status is not DayStatus.AVAILABLE,
        is_current=day_no == summary.current_day,
        review_count=session.settings().review_count,
    )
