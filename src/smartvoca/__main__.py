#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 실행 진입점 (python -m smartvoca)
# 파일 위치: src/smartvoca/__main__.py
import sys

from smartvoca.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
