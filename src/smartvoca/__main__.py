#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 실행 진입점 (python -m smartvoca). 2026-11-25 웹 서버로 변경 (ADR-18)
# 파일 위치: src/smartvoca/__main__.py
import sys

from smartvoca.web.server import main

if __name__ == "__main__":
    sys.exit(main())
