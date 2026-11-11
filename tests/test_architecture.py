#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 계층 의존 규칙 검사: 로직 쪽이 PyQt·UI 를 import 하지 않는지 (NFR-03)
# 파일 위치: tests/test_architecture.py
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "smartvoca"
NON_UI_FILES = sorted(
    path
    for path in PACKAGE_DIR.rglob("*.py")
    if "ui" not in path.relative_to(PACKAGE_DIR).parts and path.name != "__main__.py"
)


def imported_modules(path: Path) -> set[str]:
    """파일이 import 하는 모듈 이름. 상대 import 는 앞에 점을 붙여 돌려준다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or ""))
    return names


def test_검사할_파일이_있다():
    assert len(NON_UI_FILES) >= 8


@pytest.mark.parametrize("path", NON_UI_FILES, ids=lambda p: p.relative_to(PACKAGE_DIR).as_posix())
def test_로직_쪽은_PyQt_와_UI_를_import_하지_않는다(path):
    for name in imported_modules(path):
        bare = name.lstrip(".")
        assert not bare.startswith(("PyQt", "PySide")), f"{path.name}: {name}"
        assert bare != "ui" and not bare.startswith("ui."), f"{path.name}: {name}"
        assert "smartvoca.ui" not in name, f"{path.name}: {name}"


@pytest.mark.parametrize(
    "path",
    sorted((PACKAGE_DIR / "core").glob("*.py")),
    ids=lambda p: p.name,
)
def test_core_는_storage_를_import_하지_않는다(path):
    for name in imported_modules(path):
        assert "storage" not in name, f"{path.name}: {name}"
