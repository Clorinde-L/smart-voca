#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 화면 라우트 모듈들이 함께 쓰는 것: Blueprint, 세션·상태 꺼내기, 메뉴, 보안 검사
# 파일 위치: src/smartvoca/web/common.py
"""app.py 가 500줄을 넘어 기능별 routes_*.py 로 나누면서 공통 부분을 여기로 옮겼다 (CLAUDE.md 개발 원칙 5).

모든 라우트는 Blueprint "main" 하나에 붙는다. 그래서 엔드포인트 이름(main.home 등)은 나누기 전과 같다.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, redirect, request, url_for
from flask import session as cookie
from werkzeug.exceptions import RequestEntityTooLarge

from ..core.models import GRADUATE_STREAK, DayStatus, Direction, ExamKind, QuestionFormat
from ..session import AppSession
from .state import CardMode, StateStore, WebState

EXTENSION_KEY = "smartvoca"
STATE_COOKIE_KEY = "sid"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # 학교 서버는 20MB 까지 받는다. 단어장 CSV 는 수백 KB 다

bp = Blueprint("main", __name__)


@dataclass
class WebContext:
    session: AppSession
    states: StateStore


def app_session() -> AppSession:
    return current_app.extensions[EXTENSION_KEY].session


def web_state() -> WebState:
    """이 브라우저의 화면 상태. 쿠키에 무작위 ID 를 두고 서버 메모리에서 찾는다 (ADR-30)."""
    states: StateStore = current_app.extensions[EXTENSION_KEY].states
    state_id = cookie.get(STATE_COOKIE_KEY)
    if not state_id:
        state_id = cookie[STATE_COOKIE_KEY] = states.new_id()
    return states.get(state_id)


def all_web_states() -> list[WebState]:
    return current_app.extensions[EXTENSION_KEY].states.all_states()


def save_error(error: Exception) -> None:
    """DL-04 저장 실패."""
    flash(f"학습 기록을 저장하지 못했습니다. ({error})", "error")


# 메뉴 막대의 항목: (이름, 엔드포인트, 이 항목을 켜 둘 화면들)
NAV_ITEMS = (
    ("홈", "main.home", {"main.home"}),
    ("일차", "main.days", {"main.days", "main.day_detail", "main.cards"}),
    ("오답 학습", "main.wrong_list", {"main.wrong_list"}),
    ("시험", "main.exam_setup", {"main.exam_setup"}),
    ("통계", "main.stats", {"main.stats"}),
    ("단어 관리", "main.wordbook", {"main.wordbook", "main.import_wordbook", "main.word_edit"}),
    ("설정", "main.settings", {"main.settings"}),
)


# 화면 테마 (ADR-32). 고른 값은 브라우저에만 저장하므로(localStorage) 서버는 선택지만 그려 보낸다.
# 강조색 값은 style.css 의 [data-accent="..."] 블록에 있다. 이름을 바꾸면 거기도 함께 고친다.
THEME_BRIGHTNESS = (("auto", "자동"), ("light", "밝게"), ("dark", "어둡게"))
THEME_ACCENTS = (
    ("indigo", "남보라"),  # 기본값
    ("sea", "바다"),
    ("forest", "숲"),
    ("rose", "로즈"),
    ("sunset", "노을"),
    ("mono", "모노"),
)


def _nav_endpoint() -> str | None:
    """메뉴에서 켤 항목을 고를 때 쓰는 엔드포인트. 오답 카드 학습은 '오답 학습'에 속한다."""
    endpoint = request.endpoint
    if endpoint == "main.cards":
        study = web_state().cards
        if study is not None and study.mode is CardMode.WRONG:
            return "main.wrong_list"
    return endpoint


def template_globals() -> dict:
    """모든 템플릿이 쓰는 값. 메뉴 막대의 오답 수는 화면마다 DB 에서 새로 읽는다."""
    globals_ = {
        "GRADUATE_STREAK": GRADUATE_STREAK,
        "DayStatus": DayStatus,
        "Direction": Direction,
        "QuestionFormat": QuestionFormat,
        "ExamKind": ExamKind,
        "nav_items": NAV_ITEMS,
        "theme_brightness": THEME_BRIGHTNESS,
        "theme_accents": THEME_ACCENTS,
        "nav_endpoint": None,
        "nav_wrong_count": 0,
    }
    if request.endpoint:  # 오류 페이지 등 요청 정보가 없는 경우를 빼고
        globals_["nav_endpoint"] = _nav_endpoint()
        globals_["nav_wrong_count"] = len(app_session().wrong_list())
    return globals_


# ── 보안: 이 페이지에서 보낸 요청만 ─────────────────────────────
@bp.before_app_request
def _guard_request():
    """다른 웹사이트가 몰래 이 서버로 폼을 보내 기록을 지우는 일을 막는다.

    브라우저는 폼을 보낼 때 출처(Origin, 없으면 Referer)를 붙인다. 출처의 호스트가 이 서버가 아니면 거절한다.
    호스트만 비교하는 이유: 학교 서버에서는 앞단 프록시가 https 를 받고 앱에는 http 로 넘기므로
    주소 전체(http://… 와 https://…)를 비교하면 정상 요청도 막힌다 (ADR-30).
    출처가 없는 요청(브라우저가 아닌 테스트 클라이언트 등)은 통과시킨다.
    """
    if request.method == "POST":
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin is not None and urlsplit(origin).netloc != request.host:
            abort(403)


@bp.app_errorhandler(RequestEntityTooLarge)
def _too_large(error):
    flash(f"파일이 너무 큽니다. {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 이하의 CSV 를 골라 주세요.", "error")
    return redirect(url_for("main.wordbook"))
