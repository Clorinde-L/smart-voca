#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 기준 디렉토리와 데이터 파일 경로 규칙
# 파일 위치: src/smartvoca/paths.py
"""경로는 이 모듈에서만 정한다. 다른 모듈은 경로를 인자로 받는다 (시스템 구조 §5.2)."""
from __future__ import annotations

import sys
from pathlib import Path


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
