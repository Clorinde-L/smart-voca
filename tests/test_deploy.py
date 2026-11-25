#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 서버 배포 규칙 검사: Dockerfile, 점검 워크플로, 주소 규칙 (VOCA-SUB-031~037, R-01~R-16)
# 파일 위치: tests/test_deploy.py
"""Docker 가 없는 PC 에서도 규칙 위반을 미리 잡는다. 최종 판정은 GitHub Actions 의 점검 워크플로가 한다."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "smartvoca" / "web"
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def instructions() -> list[str]:
    """주석·빈 줄을 뺀 Dockerfile 지시 (줄 이어 쓰기는 합친다)."""
    text = re.sub(r"\\\n", " ", DOCKERFILE)
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def test_R02_공식_이미지에_버전_태그가_있다():
    [base] = [line for line in instructions() if line.startswith("FROM")]
    image = base.split()[1]
    assert ":" in image and not image.endswith(":latest")


def test_R03_R15_운영_서버로_0000_8080_에서_exec_형식으로_뜬다():
    [cmd] = [line for line in instructions() if line.startswith("CMD")]
    assert cmd.startswith('CMD ["')  # exec 형식
    assert '"gunicorn"' in cmd and '"0.0.0.0:8080"' in cmd
    assert "--reload" not in cmd and "flask" not in cmd.lower()


def test_R05_R06_UID_10001_로_실행하고_data_를_그_소유로_만든다():
    lines = instructions()
    assert lines[-1].startswith("CMD") and [l for l in lines if l.startswith("USER")][-1] == "USER 10001"
    assert "--uid 10001" in DOCKERFILE and "chown 10001:10001 /data" in DOCKERFILE
    assert "DB_PATH=/data/voca.db" in DOCKERFILE


def test_R10_서버가_거부하는_지시가_없다():
    assert not DOCKERFILE.splitlines()[0].lower().replace(" ", "").startswith("#syntax=")
    for forbidden in ("--mount=type=ssh", "--mount=type=secret", "--network", "--security"):
        assert forbidden not in DOCKERFILE


def test_R13_의존성을_먼저_설치한다():
    lines = instructions()
    first_copy = next(i for i, l in enumerate(lines) if l.startswith("COPY"))
    assert lines[first_copy].startswith("COPY requirements.txt")
    assert "pip install" in lines[first_copy + 1]


def test_requirements_는_버전을_고정하고_windows_전용_패키지가_없다():
    packages = [
        line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert packages and all("==" in p for p in packages)
    assert {p.split("==")[0].lower() for p in packages} >= {"flask", "gunicorn"}
    assert not any(p.lower().startswith(("pywin32", "pyqt")) for p in packages)


def test_R09_점검_워크플로를_고치지_않고_넣었다():
    original = ROOT / "ai-agent" / "uploads" / "2026-final" / "docker-check.yml"
    copied = ROOT / ".github" / "workflows" / "docker-check.yml"
    assert copied.read_bytes().replace(b"\r\n", b"\n") == original.read_bytes().replace(b"\r\n", b"\n")


def test_R11_R12_dockerignore_와_gitattributes():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert {".git", ".venv", "__pycache__", "*.db", ".env"} <= set(ignored)
    assert "* text=auto eol=lf" in (ROOT / ".gitattributes").read_text(encoding="utf-8")


def test_env_파일을_커밋하지_않는다():
    assert ".env" in (ROOT / ".gitignore").read_text(encoding="utf-8").split()


@pytest.mark.parametrize(
    "path", sorted([*(WEB / "templates").glob("*.html"), *(WEB / "static").glob("*")]), ids=lambda p: p.name
)
def test_R04_주소에_호스트를_쓰지_않고_속성은_따옴표로_감싼다(path):
    text = path.read_text(encoding="utf-8")
    assert "localhost" not in text and "127.0.0.1" not in text
    assert not re.search(r"\s(href|src|action)=[^\"'{\s>]", text), "따옴표 없는 주소 속성"
    if path.suffix == ".js":
        assert "fetch(" not in text or re.search(r"fetch\([\"'`]/", text)


def test_파일_이름이_소문자다():
    """Windows 에서는 되던 Static/Style.css 가 리눅스 서버에서 404 가 되는 일을 막는다."""
    for path in [*(WEB / "templates").iterdir(), *(WEB / "static").iterdir()]:
        assert path.name == path.name.lower(), path.name
