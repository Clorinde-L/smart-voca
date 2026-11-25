#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 오답 목록(S-06), 학습 진척 통계(S-10), 설정(S-11) 라우트
# 파일 위치: src/smartvoca/web/routes_stats.py
from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from ..core.models import DAY_SIZE_RANGE, EXAM_COUNT_RANGE, REVIEW_COUNT_RANGE
from ..core.validation import parse_settings
from .common import app_session, bp, save_error


# ── S-06 오답 목록 ──────────────────────────────────────────
@bp.get("/wrong")
def wrong_list():
    return render_template("wrong_list.html", entries=app_session().wrong_list())


# ── S-10 학습 진척 통계 (VOCA-FR-031 ~ 034) ────────────────
@bp.get("/stats")
def stats():
    """값은 모두 AppSession.stats() 가 DB 이력에서 계산해 온 것이다. 여기서는 그리기 좋게 나누기만 한다."""
    data = app_session().stats()
    summary = data.summary
    return render_template(
        "stats.html",
        data=data,
        summary=summary,
        memorized_ratio=summary.memorized_words / summary.total_words if summary.total_words else 0,
    )


# ── S-11 설정 (VOCA-FR-061, 062) ───────────────────────────
@bp.get("/settings")
def settings():
    return render_template(
        "settings.html",
        settings=app_session().settings(),
        day_size_range=DAY_SIZE_RANGE,
        review_count_range=REVIEW_COUNT_RANGE,
        exam_count_range=EXAM_COUNT_RANGE,
    )


@bp.post("/settings")
def settings_save():
    session = app_session()
    current = session.settings()
    new, problems = parse_settings(request.form, current)
    if problems:
        for problem in problems:
            flash(problem, "error")
        return redirect(url_for("main.settings"))
    try:
        session.save_settings(new)
    except Exception as error:  # noqa: BLE001
        save_error(error)
        return redirect(url_for("main.settings"))
    message = "설정을 저장했습니다."
    if new.day_size != current.day_size:
        # 일차 번호는 하루 학습량으로 다시 나눈다. 외운 단어·시험 본 단어는 그대로다 (ADR-26)
        message += f" 이제 하루 {new.day_size}단어씩, 일차를 다시 나눴습니다."
    flash(message, "info")
    return redirect(url_for("main.settings"))
