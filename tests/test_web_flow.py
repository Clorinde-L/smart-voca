#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 웹 화면 흐름 테스트: 브라우저 없이 Flask 테스트 클라이언트로 요청을 보내 따라감
# 파일 위치: tests/test_web_flow.py
"""UI/UX 설계서 §6 의 사용 흐름을 HTTP 요청으로 따라가 본다.

테스트 클라이언트는 실제 서버를 띄우지 않고 앱 함수를 바로 부른다.
화면에 무엇이 보이는지는 HTML 에서 data-testid 가 붙은 요소의 글자로 확인한다.
"""
from __future__ import annotations

import io
import random
from html.parser import HTMLParser

import pytest
from conftest import DEFAULT_CSV, DEFAULT_DAY_COUNT, DEFAULT_WORD_COUNT, Clock

from smartvoca.core.models import DayStatus, QuestionFormat
from smartvoca.session import AppSession
from smartvoca.web.app import create_app
from smartvoca.web.common import EXTENSION_KEY, STATE_COOKIE_KEY
from smartvoca.web.state import WebState


# ── HTML 읽기 도우미 ────────────────────────────────────────
class _Page(HTMLParser):
    """data-testid 가 붙은 요소의 글자·속성과, data-testid 가 붙은 표의 본문 행(tbody)을 모은다."""

    VOID = {"input", "br", "img", "meta", "link", "col", "circle"}

    def __init__(self, html: str):
        super().__init__()
        self.texts: dict[str, str] = {}
        self.attrs: dict[str, dict[str, str | None]] = {}
        self.rows: dict[str, list[list[str]]] = {}
        self._open: list[tuple[str, str | None]] = []  # 열린 태그 (태그, testid)
        self._buffers: dict[str, list[str]] = {}       # 글자를 모으는 중인 testid
        self._table: str | None = None                 # 행을 모으는 중인 표
        self._in_body = False
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        testid = attrs.get("data-testid")
        if testid:
            self.attrs[testid] = attrs
            self._buffers[testid] = []
            if tag == "table":
                self._table, self.rows[testid] = testid, []
        if self._table:
            if tag == "tbody":
                self._in_body = True
            elif tag == "tr" and self._in_body:
                self._cells = []
            elif tag == "td" and self._cells is not None:
                self._cell = []
        if tag not in self.VOID:
            self._open.append((tag, testid))

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            self.rows[self._table].append(self._cells)
            self._cells = None
        elif tag == "tbody":
            self._in_body = False
        while self._open:  # 닫는 태그를 빠뜨린 요소가 있어도 짝을 찾을 때까지 닫는다
            open_tag, testid = self._open.pop()
            if testid:
                self.texts[testid] = " ".join("".join(self._buffers.pop(testid)).split())
                if testid == self._table:
                    self._table = None
            if open_tag == tag:
                break

    def handle_data(self, data):
        for buffer in self._buffers.values():
            buffer.append(data)
        if self._cell is not None:
            self._cell.append(data)


def page(response) -> _Page:
    assert response.status_code == 200, response.status_code
    return _Page(response.get_data(as_text=True))


def disabled(parsed: _Page, testid: str) -> bool:
    return "disabled" in parsed.attrs[testid]



# ── 준비 ────────────────────────────────────────────────────
@pytest.fixture
def app(tmp_path):
    session = AppSession.open(tmp_path / "voca.db", DEFAULT_CSV, random.Random(1), Clock())
    flask_app = create_app(session, secret_key="test")
    flask_app.testing = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def ctx(app):
    return app.extensions[EXTENSION_KEY]


def state_of(client, ctx) -> WebState:
    """이 테스트 클라이언트(브라우저 하나)의 화면 상태 (ADR-30)."""
    with client.session_transaction() as cookie:
        return ctx.states.get(cookie[STATE_COOKIE_KEY])


def view_all_cards(client, ctx) -> None:
    while state_of(client, ctx).cards.deck.can_next:
        client.post("/cards/next")


def answer_all(client, ctx, wrong_positions=frozenset()) -> None:
    """모든 문제에 차례로 답한다. wrong_positions 에 든 문제(0 부터)만 틀린다."""
    run = state_of(client, ctx).exam
    for position in range(run.total):
        assert run.position == position
        question = run.exam.questions[position]
        wrong = position in wrong_positions
        if question.format is QuestionFormat.SHORT:
            client.post("/exam/answer", data={"text": "틀린답xyz" if wrong else question.answer})
        else:
            choice = question.answer_index
            client.post("/exam/answer", data={"choice": (choice + 1) % len(question.choices) if wrong else choice})


def start_exam(client, kind="day", day=1, direction="en_ko", fmt="choice", count=None):
    data = {"kind": kind, "direction": direction, "format": fmt}
    if day is not None:
        data["day"] = day
    if count is not None:
        data["count"] = count
    return client.post("/exam/start", data=data)


def finish_day(client, ctx, wrong_positions=frozenset(), fmt="choice") -> None:
    client.post("/study/today")
    view_all_cards(client, ctx)
    client.post("/cards/action")
    day_no = state_of(client, ctx).cards.day_no
    start_exam(client, day=day_no, fmt=fmt)
    answer_all(client, ctx, wrong_positions)
    client.post("/exam/submit")


def upload(client, text: str, name="words.csv"):
    data = {"file": (io.BytesIO(text.encode("utf-8-sig")), name)}
    return client.post("/wordbook/import", data=data, content_type="multipart/form-data")


# ── S-01 메인 ───────────────────────────────────────────────
def test_메인_화면이_처음_상태를_보여_준다(client):
    home = page(client.get("/"))
    assert home.texts["today"] == "1일차"
    assert home.texts["progress"] == f"0 / {DEFAULT_DAY_COUNT} 일차 완료"
    assert f"{DEFAULT_WORD_COUNT:,}" in home.texts["wordbook-label"]
    assert "0 / 2,109" in home.texts["tile-memorized"]


# ── 하루 학습: 카드 → 시험 설정 → 응시 → 결과 ───────────────
def test_하루_학습_흐름(client, ctx):
    client.post("/study/today")
    cards = page(client.get("/cards"))
    assert cards.texts["info"] == "1 / 20"  # 1일차는 전날·오답이 없어 복습 카드가 없다
    assert disabled(cards, "action")
    view_all_cards(client, ctx)
    assert not disabled(page(client.get("/cards")), "action")
    assert ctx.session.day(1)[0] is DayStatus.MEMORIZED

    response = client.post("/cards/action")
    assert response.headers["Location"].startswith("/exam/setup?kind=day&day=1")
    setup = page(client.get(response.headers["Location"]))
    assert "1일차 시험: 20문제" in setup.texts["setup-intro"]
    assert "checked" in setup.attrs["direction-en_ko"] and "checked" in setup.attrs["format-choice"]

    assert start_exam(client).headers["Location"] == "/exam"
    exam = page(client.get("/exam"))
    assert exam.texts["format"] == "4지선다 · 영→한"
    assert disabled(exam, "submit")
    answer_all(client, ctx, wrong_positions={0, 1})
    assert client.post("/exam/submit").headers["Location"] == "/result"
    result = page(client.get("/result"))
    assert result.texts["score"] == "18 / 20"
    assert len(result.rows["wrong-table"]) == 2
    assert "1일차 완료" in result.texts["status"]
    assert ctx.session.day(1)[0] is DayStatus.DONE
    assert ctx.session.summary().wrong_list_size == 2


def test_2일차_카드에는_복습_카드가_섞인다(client, ctx):
    finish_day(client, ctx, wrong_positions={0})
    client.post("/study/today")
    assert state_of(client, ctx).cards.deck.total == 24
    view_all_cards(client, ctx)
    assert page(client.get("/cards")).texts["kind"] in ("복습", "오답")


@pytest.mark.parametrize("fmt", ["ox", "short"])
def test_OX_와_단답형으로_시험을_본다(client, ctx, fmt):
    finish_day(client, ctx, wrong_positions={3}, fmt=fmt)
    result = page(client.get("/result"))
    assert result.texts["score"] == "19 / 20"
    label = {"ox": "OX", "short": "단답형"}[fmt]
    assert result.texts["exam-info"].startswith(label)


def test_한영_방향이면_뜻을_보여_준다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    start_exam(client, direction="ko_en")
    question = state_of(client, ctx).exam.question
    assert page(client.get("/exam")).texts["word"] == question.target.meaning


def test_답하지_않은_문제가_있으면_제출할_수_없다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    start_exam(client)
    client.post("/exam/answer", data={"choice": 0})
    response = client.post("/exam/submit", follow_redirects=True)
    assert "모든 문제에 답해야" in response.get_data(as_text=True)
    assert ctx.session.stats().exam_count == 0


def test_시험을_그만두면_기록이_바뀌지_않는다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    start_exam(client)
    answer_all(client, ctx)
    assert client.post("/exam/abort").headers["Location"] == "/days/1"
    assert ctx.session.day(1)[0] is DayStatus.MEMORIZED
    assert client.get("/exam").headers["Location"] == "/"


def test_암기_전에는_일차_시험을_시작할_수_없다(client):
    setup = page(client.get("/exam/setup?kind=day&day=2"))
    assert "카드를 모두 본 뒤" in setup.texts["setup-problem"]
    assert "/exam/setup" in start_exam(client, day=2).headers["Location"]
    assert client.get("/exam/setup?kind=day&day=999").status_code == 404


# ── 실력 시험 (VOCA-FR-021, 022) ────────────────────────────
def test_실력_시험은_문제_수를_정해서_본다(client, ctx):
    setup = page(client.get("/exam/setup"))
    assert "전체 단어 2,109개" in setup.texts["setup-intro"]
    response = start_exam(client, kind="random", day=None, count=5, direction="mix")
    assert response.headers["Location"] == "/exam"
    assert state_of(client, ctx).exam.total == 5
    answer_all(client, ctx)
    client.post("/exam/submit")
    assert page(client.get("/result")).texts["score"] == "5 / 5"
    assert "/exam/setup" in start_exam(client, kind="random", day=None, count=0).headers["Location"]


# ── 오답 (FR-22 ~ FR-25) ────────────────────────────────────
def test_오답_정리_흐름(client, ctx):
    finish_day(client, ctx, wrong_positions={0})
    assert len(page(client.get("/wrong")).rows["wrong-table"]) == 1
    client.post("/study/wrong")
    assert page(client.get("/cards")).texts["kind"] == "오답"
    assert client.post("/cards/action").headers["Location"] == "/exam/setup?kind=wrong"
    for _ in range(3):
        start_exam(client, kind="wrong", day=None)
        answer_all(client, ctx)
        client.post("/exam/submit")
    assert "graduated" in page(client.get("/result")).texts
    assert "empty" in page(client.get("/wrong")).texts
    assert "오답 목록이 비어" in page(client.get("/exam/setup?kind=wrong")).texts["setup-problem"]


# ── 통계·설정 (VOCA-FR-031 ~ 034, 061, 062) ─────────────────
def test_통계_화면은_시험_이력으로_그린다(client, ctx):
    assert "no-exams" in page(client.get("/stats")).texts
    finish_day(client, ctx, wrong_positions={0, 1})
    stats = page(client.get("/stats"))
    assert stats.texts["current-day"] == "2일차"
    assert stats.texts["memorized"] == "20 / 2,109"
    assert stats.texts["overall"] == "90%"
    assert len(stats.rows["frequent-wrong"]) == 2
    assert len(stats.rows["date-table"]) == 1


def test_설정을_저장하면_일차와_시험_기본값이_바뀐다(client, ctx):
    form = {"day_size": "10", "review_count": "0", "exam_count": "15", "exam_direction": "ko_en", "exam_format": "short"}
    client.post("/settings", data=form)
    settings = page(client.get("/settings"))
    assert settings.attrs["day_size"]["value"] == "10"
    assert "checked" in settings.attrs["exam_format-short"]
    assert ctx.session.summary().total_days == 211
    setup = page(client.get("/exam/setup"))
    assert setup.attrs["count"]["value"] == "15" and "checked" in setup.attrs["direction-ko_en"]
    client.post("/settings", data={**form, "day_size": "1"})
    assert ctx.session.settings().day_size == 10  # 범위 밖이면 저장하지 않는다


# ── 단어 관리 (VOCA-FR-001 ~ 004) ───────────────────────────
def test_단어를_등록하고_수정하고_삭제한다(client, ctx):
    response = client.post("/words", data={"word": "zebra", "meaning": "[명] 얼룩말"})
    assert response.headers["Location"] == "/wordbook?q=zebra"
    found = page(client.get("/wordbook?q=zebra"))
    assert found.rows["word-table"][0][1:3] == ["zebra", "[명] 얼룩말"]
    word = next(w for w in ctx.session.words() if w.word == "zebra")

    duplicate = client.post("/words", data={"word": "ZEBRA", "meaning": "x"}, follow_redirects=True)
    assert "이미 등록된 단어" in duplicate.get_data(as_text=True)

    edit = page(client.get(f"/words/{word.id}/edit"))
    assert edit.attrs["edit-word"]["value"] == "zebra"
    client.post(f"/words/{word.id}/edit", data={"word": "zebras", "meaning": "얼룩말들"})
    assert ctx.session.get_word(word.id).meaning == "얼룩말들"

    client.post(f"/words/{word.id}/delete")
    assert ctx.session.get_word(word.id) is None
    assert client.post(f"/words/{word.id}/delete").status_code == 404


def test_단어_목록은_처음_500개만_그리고_검색은_전체에서(client):
    listing = page(client.get("/wordbook"))
    assert len(listing.rows["word-table"]) == 500 and "more" in listing.texts
    assert len(page(client.get("/wordbook?all=1")).rows["word-table"]) == DEFAULT_WORD_COUNT
    assert len(page(client.get("/wordbook?q=12")).rows["word-table"]) == 20
    assert "empty" in page(client.get("/wordbook?q=zzzzzz")).texts


def test_CSV_를_가져와_추가한다(client, ctx):
    confirm = page(upload(client, "영단어,뜻\nexecutive,중복\nnewword,새 단어\nNEWWORD,파일 안 중복\n"))
    assert "새 단어 1개, 이미 있는 단어 1개" in confirm.texts["confirm-text"]
    assert "4" in confirm.texts["duplicates"]
    response = client.post("/wordbook/import/confirm", data={"mode": "add"}, follow_redirects=True)
    assert "단어 1개를 등록했습니다" in response.get_data(as_text=True)
    assert len(ctx.session.words()) == DEFAULT_WORD_COUNT + 1


def test_CSV_로_바꾸면_기록이_지워지고_진행_중인_화면도_사라진다(client, ctx):
    finish_day(client, ctx)
    client.post("/study/today")
    upload(client, "word,meaning\n" + "".join(f"w{i},뜻{i}\n" for i in range(10)))
    client.post("/wordbook/import/confirm", data={"mode": "replace"})
    assert len(ctx.session.words()) == 10
    assert ctx.session.stats().exam_count == 0
    assert state_of(client, ctx).cards is None


def test_잘못된_CSV_는_문제를_보여_주고_아무것도_바꾸지_않는다(client, ctx):
    rejected = page(upload(client, "단어,의미\na,b\n"))
    assert "1건" in rejected.texts["issue-summary"]
    assert client.post("/wordbook/import/confirm", data={"mode": "add"}).headers["Location"] == "/wordbook"
    assert len(ctx.session.words()) == DEFAULT_WORD_COUNT
    assert "골라 주세요" in client.post("/wordbook/import", follow_redirects=True).get_data(as_text=True)


def test_단어장과_오답_목록을_내보낸다(client, ctx):
    response = client.get("/export/wordbook.csv")
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert response.data.startswith(b"\xef\xbb\xbfword,meaning")
    assert client.get("/export/wrong_words.csv").headers["Location"] == "/wrong"
    finish_day(client, ctx, wrong_positions={0})
    assert client.get("/export/wrong_words.csv").status_code == 200


# ── 화면 공통 ───────────────────────────────────────────────
def test_모든_메뉴_화면이_열린다(client):
    for url in ["/", "/days", "/days/1", "/wrong", "/exam/setup", "/stats", "/wordbook", "/settings"]:
        assert client.get(url).status_code == 200, url


def test_시험_화면에는_메뉴_막대가_없다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    start_exam(client)
    assert "nav-home" not in page(client.get("/exam")).attrs
    assert "nav-home" in page(client.get("/")).attrs


def test_브라우저마다_진행_중인_카드가_따로다(app):
    first, second = app.test_client(), app.test_client()
    first.post("/study/today")
    assert second.get("/cards").headers["Location"] == "/"
    assert first.get("/cards").status_code == 200


def test_다른_사이트에서_보낸_요청은_거절한다(client, ctx):
    response = client.post("/study/today", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    same = client.post("/study/today", headers={"Origin": "http://localhost"})
    assert same.status_code == 302


def test_프록시_뒤에서_https_출처라도_호스트가_같으면_받는다(client):
    """학교 서버: 브라우저는 https 로 보내고 앱은 http 로 받는다 (ADR-30)."""
    headers = {"Host": "lab.example", "Origin": "https://lab.example"}
    assert client.post("/study/today", headers=headers).status_code == 302
    referer = {"Host": "lab.example", "Referer": "https://lab.example/2026/voca-x/days"}
    assert client.post("/study/today", headers=referer).status_code == 302
    assert client.get("/", headers={"Host": "lab.example"}).status_code == 200


def test_리다이렉트_주소는_호스트_없이_슬래시로_시작한다(client):
    """학교 서버의 프록시가 앞에 /2026/voca-<학번> 을 붙일 수 있게 한다 (R-04)."""
    for response in (client.post("/study/today"), client.post("/exam/abort"), client.get("/result")):
        location = response.headers["Location"]
        assert location.startswith("/") and "://" not in location


# ── 화면 테마 (ADR-32) ──────────────────────────────────────
def test_테마_메뉴에_밝기와_강조색_선택지가_모두_있다(client):
    from smartvoca.web.common import THEME_ACCENTS, THEME_BRIGHTNESS

    html = client.get("/").get_data(as_text=True)
    for value, label in THEME_BRIGHTNESS:
        assert f'data-theme-choice="{value}"' in html and label in html
    for value, label in THEME_ACCENTS:
        assert f'data-accent-choice="{value}"' in html and label in html


def test_강조색마다_CSS_블록이_있다():
    """선택지 이름과 style.css 의 [data-accent] 블록 이름이 어긋나면 골라도 색이 바뀌지 않는다."""
    from pathlib import Path

    import smartvoca.web
    from smartvoca.web.common import THEME_ACCENTS

    css = (Path(smartvoca.web.__file__).parent / "static" / "style.css").read_text(encoding="utf-8")
    for value, _ in THEME_ACCENTS:
        assert f'[data-accent="{value}"]' in css, value
