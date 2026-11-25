#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 계층 의존 규칙 검사: 로직 쪽이 화면 계층(web)·화면 라이브러리를 import 하지 않는지 (NFR-03)
# 파일 위치: tests/test_architecture.py
# 2026-11-25 화면 계층을 PyQt(ui) 에서 Flask(web) 로 바꾸며 검사 대상을 바꿈 (ADR-18)
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "smartvoca"
UI_PACKAGE = "web"
UI_LIBRARIES = ("flask", "werkzeug", "jinja2", "PyQt", "PySide")
LOGIC_FILES = sorted(
    path
    for path in PACKAGE_DIR.rglob("*.py")
    if UI_PACKAGE not in path.relative_to(PACKAGE_DIR).parts and path.name != "__main__.py"
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
    assert len(LOGIC_FILES) >= 8


def test_예전_PyQt_화면_패키지가_남아_있지_않다():
    assert not (PACKAGE_DIR / "ui").exists()


@pytest.mark.parametrize("path", LOGIC_FILES, ids=lambda p: p.relative_to(PACKAGE_DIR).as_posix())
def test_로직_쪽은_화면_라이브러리와_web_을_import_하지_않는다(path):
    for name in imported_modules(path):
        bare = name.lstrip(".")
        assert not bare.startswith(UI_LIBRARIES), f"{path.name}: {name}"
        assert bare != UI_PACKAGE and not bare.startswith(UI_PACKAGE + "."), f"{path.name}: {name}"
        assert f"smartvoca.{UI_PACKAGE}" not in name, f"{path.name}: {name}"


@pytest.mark.parametrize(
    "path",
    sorted((PACKAGE_DIR / "core").glob("*.py")),
    ids=lambda p: p.name,
)
def test_core_는_storage_를_import_하지_않는다(path):
    for name in imported_modules(path):
        assert "storage" not in name, f"{path.name}: {name}"


@pytest.mark.parametrize(
    "path", sorted((PACKAGE_DIR / UI_PACKAGE).glob("*.py")), ids=lambda p: p.name
)
def test_화면은_storage_를_직접_부르지_않는다(path):
    """R-04: 화면은 AppSession 을 거친다. 저장 시점(FR-26)을 한곳에서 관리하기 위함이다."""
    for name in imported_modules(path):
        assert "storage" not in name, f"{path.name}: {name}"
