#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - Flask 앱 만들기: 설정, 화면 상태 저장소, 라우트 모듈 등록 (UI/UX 설계서 §4)
# 파일 위치: src/smartvoca/web/app.py
"""화면 계층의 시작점.

- 화면을 보여 주는 요청은 GET, 기록이나 진행 상태를 바꾸는 요청은 POST 다.
- POST 는 처리가 끝나면 GET 화면으로 리다이렉트한다(Post/Redirect/Get).
  그래야 새로고침해도 같은 답이 두 번 제출되지 않는다.
- 판단(카드를 다 봤는가, 제출할 수 있는가)은 routes_*.py 와 state.py 에서 한다. 템플릿은 그리기만 한다.
- 주소는 모두 url_for 로 만든다. url_for 는 "/days" 처럼 "/" 로 시작하는 경로를 주므로
  학교 서버가 /2026/voca-<학번>/ 아래로 옮겨도 그대로 동작한다 (R-04).

2026-11-25 라우트를 기능별 모듈로 나눴다 (routes_study, routes_exam, routes_words, routes_stats).
"""
from __future__ import annotations

import secrets

from flask import Flask

from ..session import AppSession
from . import routes_exam, routes_stats, routes_study, routes_words  # noqa: F401  라우트를 bp 에 붙인다
from .common import EXTENSION_KEY, MAX_UPLOAD_BYTES, WebContext, bp, template_globals
from .state import StateStore


def create_app(session: AppSession, secret_key: str | None = None) -> Flask:
    app = Flask(__name__)
    # 쿠키(화면 상태 ID, flash 알림)에 서명하는 키. 환경변수 SECRET_KEY 로 받고,
    # 없으면 기동할 때 무작위로 만든다 (NFR-004, R-08). 무작위면 서버를 다시 켤 때 진행 중인 화면만 사라진다.
    app.secret_key = secret_key or secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.extensions[EXTENSION_KEY] = WebContext(session, StateStore())
    app.register_blueprint(bp)
    app.context_processor(template_globals)
    return app
