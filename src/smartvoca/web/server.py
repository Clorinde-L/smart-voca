#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 프로그램 시작: 세션 열기, 로컬 웹 서버 시작, 브라우저 열기
# 파일 위치: src/smartvoca/web/server.py
"""`python -m smartvoca` 가 여기의 main() 을 부른다.

서버는 127.0.0.1(내 PC)에만 연다. 같은 와이파이의 다른 기기도 접속할 수 없다 (NFR-02, NFR-09).
"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import webbrowser

from werkzeug.serving import make_server

from .. import paths
from ..session import AppSession, WordbookLoadError
from .app import create_app

HOST = "127.0.0.1"
DEFAULT_PORT = 8765  # 주소가 늘 같아야 즐겨찾기해 둘 수 있다


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, port)) == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smartvoca", description="스마트 보카 (브라우저에서 실행)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"포트 번호 (기본 {DEFAULT_PORT})")
    parser.add_argument("--no-browser", action="store_true", help="브라우저를 자동으로 열지 않는다")
    args = parser.parse_args(argv)
    url = f"http://{HOST}:{args.port}/"

    # 이미 켜져 있으면 서버를 하나 더 띄우지 않는다.
    # 서버가 둘이면 서로 모르는 채로 같은 progress.json 을 덮어써 기록이 엉킨다.
    if _port_in_use(args.port):
        print(f"스마트 보카가 이미 실행 중입니다. 브라우저에서 엽니다: {url}")
        print(f"(다른 프로그램이 {args.port} 포트를 쓰고 있다면 --port 로 다른 번호를 주세요)")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    try:
        session = AppSession.open(paths.userdata_dir(), paths.default_wordbook_path())
    except WordbookLoadError as error:
        print(
            f"기본 단어장을 읽을 수 없어 시작할 수 없습니다.\n{paths.default_wordbook_path()}\n\n{error}",
            file=sys.stderr,
        )
        return 1

    app = create_app(session)
    # 한 번에 요청 하나만 처리한다(threaded=False). 사용자는 1명이고,
    # 그래야 AppSession·WebState 를 두 요청이 동시에 바꾸는 일이 없다 (ADR-20)
    server = make_server(HOST, args.port, app, threaded=False)
    print("스마트 보카 서버를 시작했습니다.")
    print(f"  주소: {url}")
    print("  끝내려면 이 창을 닫거나 Ctrl+C 를 누르세요.")
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n스마트 보카를 종료합니다.")
    finally:
        server.server_close()
    return 0
