#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 안전한 파일 쓰기와 문제 파일 보존 (CSV·JSON 저장소 공용)
# 파일 위치: src/smartvoca/storage/fileutil.py
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def atomic_write_text(path: Path, text: str, encoding: str) -> None:
    """임시 파일에 다 쓴 뒤 한 번에 교체한다 (데이터 설계서 §5.3, NFR-06).

    쓰는 도중 프로그램이 꺼져도 불완전한 것은 임시 파일뿐이고 원래 파일은 직전 내용 그대로다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    # newline="" : 글 안의 줄바꿈(\r\n)을 운영체제가 다시 바꾸지 않게 한다
    with open(temp_path, "w", encoding=encoding, newline="") as file:
        file.write(text)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp_path, path)


def move_aside(path: Path, label: str) -> Path:
    """읽을 수 없는 파일을 지우지 않고 다른 이름으로 보존한다.

    progress.json + "corrupt" → progress.corrupt-20261111-143000.json
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.stem}.{label}-{stamp}{path.suffix}")
    counter = 1
    while backup_path.exists():  # 같은 초에 두 번 생기는 경우
        counter += 1
        backup_path = path.with_name(
            f"{path.stem}.{label}-{stamp}-{counter}{path.suffix}"
        )
    os.replace(path, backup_path)
    return backup_path
