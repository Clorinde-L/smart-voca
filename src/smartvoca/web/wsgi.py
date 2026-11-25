#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 서버 배포용 진입점: gunicorn 이 여기의 app 을 띄운다 (ADR-29)
# 파일 위치: src/smartvoca/web/wsgi.py
"""`gunicorn smartvoca.web.wsgi:app` 으로 실행한다 (Dockerfile 의 CMD).

로컬 실행(`python -m smartvoca`, server.py)과 다른 점은 두 가지다.
- 듣는 주소는 gunicorn 이 정한다(0.0.0.0:8080). 브라우저를 열지 않는다.
- 기록 위치는 환경변수 DB_PATH 를 따르고, 세션 키는 SECRET_KEY 를 쓴다 (NFR-004, R-06, R-08).
"""
from __future__ import annotations

import os

from .. import paths
from ..session import AppSession
from .app import create_app

session = AppSession.open(paths.db_path(), paths.default_wordbook_path())
app = create_app(session, secret_key=os.environ.get("SECRET_KEY"))
