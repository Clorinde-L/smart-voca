#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 기준 디렉토리와 데이터 파일 경로 규칙
# 파일 위치: src/smartvoca/paths.py
"""경로는 이 모듈에서만 정한다. 다른 모듈은 경로를 인자로 받는다 (시스템 구조 §5.2)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

DB_PATH_ENV = "DB_PATH"   # 서버에서는 /data/voca.db (Dockerfile, R-06)


def base_dir() -> Path:
    """기준 디렉토리.

    소스로 실행하면 프로젝트 루트(src/smartvoca/paths.py 에서 세 단계 위),
    PyInstaller 로 만든 exe 로 실행하면 exe 가 있는 폴더다.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def default_wordbook_path() -> Path:
    return base_dir() / "data" / "toeic_words.csv"


def userdata_dir() -> Path:
    return base_dir() / "userdata"


def db_path() -> Path:
    """SQLite 파일. 환경변수 DB_PATH 가 있으면 그것, 없으면 로컬 실행용 userdata/voca.db (ADR-25)."""
    configured = os.environ.get(DB_PATH_ENV, "").strip()
    return Path(configured) if configured else userdata_dir() / "voca.db"
