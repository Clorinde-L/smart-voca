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
import re
from html.parser import HTMLParser

import pytest
from conftest import DEFAULT_CSV, DEFAULT_DAY_COUNT, DEFAULT_WORD_COUNT

from smartvoca.core.models import DayStatus
from smartvoca.session import AppSession
from smartvoca.web.app import EXTENSION_KEY, create_app
from smartvoca.web.state import CardMode, CardStudy


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
    session = AppSession.open(tmp_path / "userdata", DEFAULT_CSV, random.Random(1))
    flask_app = create_app(session, secret_key="test")
    flask_app.testing = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def ctx(app):
    return app.extensions[EXTENSION_KEY]


def view_all_cards(client, ctx) -> None:
    while ctx.state.cards.deck.can_next:
        client.post("/cards/next")


def answer_all(client, ctx, wrong_positions=frozenset()) -> None:
    """모든 문제에 차례로 답한다. wrong_positions 에 든 문제(0 부터)만 틀린다."""
    run = ctx.state.exam
    for position in range(run.total):
        assert run.position == position
        question = run.exam.questions[position]
        choice = question.answer_index
        if position in wrong_positions:
            choice = (choice + 1) % 4
        client.post("/exam/answer", data={"choice": choice})


def finish_day(client, ctx, wrong_positions=frozenset()) -> None:
    client.post("/study/today")
    view_all_cards(client, ctx)
    client.post("/cards/action")
    answer_all(client, ctx, wrong_positions)
    client.post("/exam/submit")


# ── S-01 ────────────────────────────────────────────────────
def test_메인_화면이_처음_상태를_보여_준다(client):
    home = page(client.get("/"))
    assert home.texts["today"] == "1일차"
    assert home.texts["start"] == "1일차 학습 시작"
    assert home.texts["progress"] == f"0 / {DEFAULT_DAY_COUNT} 일차 완료"
    assert "아직 학습한 일차가 없습니다" in home.texts["menu-days"]
    assert home.attrs["menu-days"].get("aria-disabled") == "true"
    assert "오답 학습 (0)" in home.texts["menu-wrong"]
    assert f"기본 토익 {DEFAULT_WORD_COUNT:,} 단어" in home.texts["wordbook-label"]


def test_하루_학습_흐름(client, ctx):
    """UI/UX 설계서 §6.1: 카드 20장 → 시험 → 결과 → 메인."""
    response = client.post("/study/today")
    assert response.headers["Location"] == "/cards"
    cards = page(client.get("/cards"))
    assert cards.texts["info"] == "1 / 20"
    assert cards.texts["word"] == "executive"  # 기본 단어장 첫 단어
    assert cards.texts["meaning"] == ctx.session.words[0].meaning
    assert disabled(cards, "action")

    for _ in range(18):
        client.post("/cards/next")
    assert disabled(page(client.get("/cards")), "action")   # 19장째까지는 꺼져 있다
    client.post("/cards/next")
    cards = page(client.get("/cards"))
    assert not disabled(cards, "action")                     # 20장째를 보는 순간 켜진다
    assert cards.texts["hint"] == "암기 완료! 시험을 볼 수 있습니다"
    assert ctx.session.day_status(1) is DayStatus.MEMORIZED

    assert client.post("/cards/action").headers["Location"] == "/exam"
    exam = page(client.get("/exam"))
    assert disabled(exam, "submit")
    question = ctx.state.exam.exam.questions[0]
    assert exam.texts["word"] == question.word
    assert len(set(question.choices)) == 4
    assert "answer_index" not in client.get("/exam").get_data(as_text=True)

    run = ctx.state.exam
    wrong_words = {run.exam.questions[i].word for i in (0, 5, 9)}
    answer_all(client, ctx, wrong_positions={0, 5, 9})
    exam = page(client.get("/exam"))
    assert not disabled(exam, "submit")
    assert "autofocus" in exam.attrs["submit"]   # 모두 풀면 제출 버튼에 초점 (UD-05)

    assert client.post("/exam/submit").headers["Location"] == "/result"
    result = page(client.get("/result"))
    assert result.texts["score"] == "17 / 20"
    assert result.texts["status"] == "1일차 완료 · 2일차가 열렸습니다"
    assert {row[0] for row in result.rows["wrong-table"]} == wrong_words
    assert result.texts["primary"] == "2일차 학습"

    home = page(client.get("/"))
    assert home.texts["today"] == "2일차"
    assert home.texts["progress"] == f"1 / {DEFAULT_DAY_COUNT} 일차 완료"
    assert "오답 학습 (3)" in home.texts["menu-wrong"]
    assert home.attrs["menu-days"].get("href") == "/days"


def test_답하지_않은_문제가_있으면_제출할_수_없다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    client.post("/cards/action")
    client.post("/exam/answer", data={"choice": 0})
    exam = page(client.get("/exam"))
    assert exam.texts["answered"] == "답한 문제 1 / 20"
    assert disabled(exam, "submit")

    response = client.post("/exam/submit", follow_redirects=True)
    assert "모든 문제에 답해야 제출할 수 있습니다" in response.get_data(as_text=True)
    assert ctx.session.summary().done_days == 0

    client.post("/exam/goto", data={"position": 0})
    client.post("/exam/answer", data={"choice": 2})   # 돌아가 답을 바꿀 수 있다
    client.post("/exam/goto", data={"position": 0})
    html = client.get("/exam").get_data(as_text=True)
    assert html.count("is-selected") == 1
    assert ctx.state.exam.answers[0] == 2


def test_시험을_그만두면_기록이_바뀌지_않는다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    client.post("/cards/action")
    answer_all(client, ctx, wrong_positions={0})

    assert client.post("/exam/abort").headers["Location"] == "/cards"
    assert ctx.session.day_status(1) is DayStatus.MEMORIZED
    assert ctx.session.wrong_list() == []
    assert client.get("/exam").headers["Location"] == "/"   # 시험지는 사라졌다


def test_제출한_시험은_다시_제출되지_않는다(client, ctx):
    finish_day(client, ctx, wrong_positions={0})
    before = ctx.session.wrong_list()
    assert client.post("/exam/submit").headers["Location"] == "/"
    assert ctx.session.wrong_list() == before


def test_지난_일차에서_복습과_재시험을_한다(client, ctx):
    finish_day(client, ctx)
    days = page(client.get("/days"))
    assert len(days.rows["day-table"]) == 1
    day_row = days.rows["day-table"][0]
    assert (day_row[0], day_row[2]) == ("1일차", "완료")

    client.post("/study/review/1")
    cards = page(client.get("/cards"))
    assert "1일차 복습" in client.get("/cards").get_data(as_text=True)
    assert "action" not in cards.attrs           # 복습에는 시험 버튼이 없다
    before = ctx.session.summary()
    view_all_cards(client, ctx)
    assert ctx.session.summary() == before       # 복습은 기록을 바꾸지 않는다
    assert 'href="/days"' in client.get("/cards").get_data(as_text=True)  # 뒤로 → 지난 일차

    assert client.post("/exam/day/1").headers["Location"] == "/exam"
    answer_all(client, ctx, wrong_positions={3})
    client.post("/exam/submit")
    result = page(client.get("/result"))
    assert result.texts["status"] == "1일차 재시험"
    assert "primary" not in result.texts
    assert ctx.session.summary().wrong_list_size == 1
    assert ctx.session.summary().current_day == 2


def test_잠긴_일차는_열_수_없다(client, ctx):
    response = client.post("/study/day/5", follow_redirects=True)
    assert "5일차는 아직 열리지 않았습니다" in response.get_data(as_text=True)
    assert ctx.state.cards is None
    assert client.post("/exam/day/1").headers["Location"] == "/days"
    assert ctx.state.exam is None


def test_오답_정리_흐름(client, ctx):
    """UI/UX 설계서 §6.2: 오답 목록 → 카드 → 오답 시험을 3번 → 목록에서 빠짐."""
    finish_day(client, ctx, wrong_positions={0, 1})

    for round_no in range(1, 4):
        wrong = page(client.get("/wrong"))
        assert len(wrong.rows["wrong-table"]) == 2
        assert wrong.rows["wrong-table"][0][3] == f"{round_no - 1} / 3"
        client.post("/study/wrong")
        cards = page(client.get("/cards"))
        assert f"연속 정답 {round_no - 1} / 3" in cards.texts["stats"]
        assert disabled(cards, "action")
        view_all_cards(client, ctx)
        assert not disabled(page(client.get("/cards")), "action")
        client.post("/cards/action")
        answer_all(client, ctx)
        client.post("/exam/submit")
        result = page(client.get("/result"))
        assert result.texts["score"] == "2 / 2"
        if round_no < 3:
            assert result.texts["status"] == "오답 목록에서 빠진 단어 0개 · 남은 오답 2개"

    assert result.texts["status"] == "오답 목록에서 빠진 단어 2개 · 남은 오답 0개"
    assert "graduated" in result.texts
    assert result.attrs["primary"]["href"] == "/wrong"
    wrong = page(client.get("/wrong"))
    assert "empty" in wrong.texts and "wrong-table" not in wrong.rows
    assert disabled(wrong, "study") and disabled(wrong, "export")


def upload(client, name: str, lines: list[str]):
    data = {"file": (io.BytesIO(("\n".join(lines) + "\n").encode("utf-8-sig")), name)}
    return client.post("/wordbook/import", data=data, content_type="multipart/form-data")


def test_단어장을_불러오면_확인을_거쳐_교체된다(client, ctx):
    """UI/UX 설계서 §6.3."""
    finish_day(client, ctx, wrong_positions={0})
    wordbook = page(client.get("/wordbook"))
    assert f"기본 토익 {DEFAULT_WORD_COUNT:,} 단어 ({DEFAULT_DAY_COUNT}일차)" in wordbook.texts["current"]

    bad = page(upload(client, "bad.csv", ["word,meaning", "a,1", "A,2", "c,3", "d,4"]))
    assert "문제 1건" in bad.texts["issue-summary"]
    assert "3번째 줄" in bad.texts["issues"]
    assert ctx.state.pending_import is None
    assert len(ctx.session.words) == DEFAULT_WORD_COUNT

    good_lines = ["word,meaning"] + [f"w{i},뜻{i}" for i in range(45)]
    response = upload(client, "good.csv", good_lines)
    confirm = page(response)
    assert confirm.texts["confirm-text"] == '단어장을 "good.csv" (45 단어, 3일차)로 바꿉니다.'
    assert "완료 일차 1개, 오답 단어 1개" in response.get_data(as_text=True)
    client.post("/wordbook/import/cancel")                       # '취소'하면 그대로
    assert len(ctx.session.words) == DEFAULT_WORD_COUNT
    assert client.post("/wordbook/import/confirm").headers["Location"] == "/wordbook"  # 확인할 것이 없음

    upload(client, "good.csv", good_lines)
    assert client.post("/wordbook/import/confirm").headers["Location"] == "/"
    home = page(client.get("/"))
    assert home.texts["today"] == "1일차"
    assert home.texts["progress"] == "0 / 3 일차 완료"
    assert "오답 학습 (0)" in home.texts["menu-wrong"]
    assert "사용자 단어장 45 단어" in home.texts["wordbook-label"]


def test_파일을_고르지_않으면_안내한다(client):
    response = client.post("/wordbook/import", data={}, follow_redirects=True)
    assert "불러올 CSV 파일을 골라 주세요" in response.get_data(as_text=True)


def test_단어장과_오답_목록을_내보낸다(client, ctx):
    response = client.get("/export/wrong_words.csv", follow_redirects=True)
    assert "내보낼 오답 단어가 없습니다" in response.get_data(as_text=True)

    finish_day(client, ctx, wrong_positions={0})
    wordbook = client.get("/export/wordbook.csv")
    assert "attachment" in wordbook.headers["Content-Disposition"]
    assert "wordbook.csv" in wordbook.headers["Content-Disposition"]
    assert len(wordbook.data.decode("utf-8-sig").splitlines()) == DEFAULT_WORD_COUNT + 1  # 헤더 포함
    wrong = client.get("/export/wrong_words.csv")
    assert len(wrong.data.decode("utf-8-sig").splitlines()) == 2


# ── S-02 · S-03 세부 동작 ───────────────────────────────────
def test_뜻을_가리고_외울_수_있다(client, ctx):
    client.post("/study/today")
    html = client.get("/cards").get_data(as_text=True)
    assert "data-reveal" not in html
    client.post("/cards/hide", data={"hide": "on"})
    cards = page(client.get("/cards"))
    assert "hidden" in cards.attrs["meaning"]          # 뜻은 숨기고
    assert "data-reveal" in client.get("/cards").get_data(as_text=True)  # 뜻 보기 버튼을 둔다
    client.post("/cards/hide", data={})
    assert "hidden" not in page(client.get("/cards")).attrs["meaning"]


def test_문제_번호를_눌러_그_문제로_간다(client, ctx):
    client.post("/study/today")
    view_all_cards(client, ctx)
    client.post("/cards/action")
    client.post("/exam/goto", data={"position": 5})
    assert page(client.get("/exam")).texts["info"] == "문제 6 / 20"
    html = client.get("/exam").get_data(as_text=True)
    assert len(re.findall(r'class="dot[ "]', html)) == 20   # 문제 번호 점 20개 (묶음 class="dots" 는 빼고)


def test_시험과_카드에_단축키_안내가_있다(client, ctx):
    client.post("/study/today")
    cards = client.get("/cards").get_data(as_text=True)
    assert "카드 넘기기" in cards and 'data-key="ArrowLeft"' in cards
    view_all_cards(client, ctx)
    client.post("/cards/action")
    exam = client.get("/exam").get_data(as_text=True)
    assert "보기 선택" in exam and 'data-key="1"' in exam and 'data-key="Escape"' in exam
    assert "시험을 그만둘까요?" in exam                    # DL-03 문구


def test_가장_긴_뜻도_자르지_않고_보낸다(client, ctx):
    """NFR-07: 뜻을 줄이지 않고 그대로 보낸다. 줄바꿈은 CSS(overflow-wrap)가 맡는다."""
    longest = max(ctx.session.words, key=lambda word: len(word.meaning))
    ctx.state.cards = CardStudy.start(CardMode.REVIEW, "긴 뜻", [longest], day_no=1)
    assert page(client.get("/cards")).texts["meaning"] == longest.meaning


# ── S-07 검색 (FR-29) ───────────────────────────────────────
def test_단어_목록에_전체_단어가_일차와_함께_나온다(client):
    wordbook = page(client.get("/wordbook"))
    assert len(wordbook.rows["word-table"]) == DEFAULT_WORD_COUNT
    assert wordbook.rows["word-table"][0][:2] == ["1일차", "executive"]
    assert wordbook.texts["count"] == f"{DEFAULT_WORD_COUNT:,}개"


def test_영단어나_숫자로_검색한다(client):
    found = page(client.get("/wordbook", query_string={"q": "account"}))
    assert all("account" in row[1] or "account" in row[2].lower() for row in found.rows["word-table"])
    assert found.texts["count"].endswith(f" / {DEFAULT_WORD_COUNT:,}개")

    day12 = page(client.get("/wordbook", query_string={"q": "12일차"}))
    assert len(day12.rows["word-table"]) == 20
    assert {row[0] for row in day12.rows["word-table"]} == {"12일차"}


def test_검색_결과가_없으면_안내하고_Esc는_검색어를_먼저_지운다(client):
    html = client.get("/wordbook", query_string={"q": "zzzz"}).get_data(as_text=True)
    empty = _Page(html)
    assert empty.texts["empty"] == "검색 결과가 없습니다"
    assert html.count('data-key="Escape"') == 1 and "검색 지우기</a>" in html  # Esc → 검색 지우기
    plain = client.get("/wordbook").get_data(as_text=True)
    assert plain.count('data-key="Escape"') == 1 and "← 뒤로" in plain        # Esc → 뒤로


# ── 시작 알림 · 보안 ────────────────────────────────────────
def test_기록이_손상되었으면_첫_화면에서_한_번_알린다(tmp_path):
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    (userdata / "progress.json").write_text("{깨진 파일", encoding="utf-8")
    app = create_app(AppSession.open(userdata, DEFAULT_CSV, random.Random(1)), secret_key="t")
    client = app.test_client()
    assert "학습 기록을 읽을 수 없어 처음 상태로 시작합니다" in client.get("/").get_data(as_text=True)
    assert "학습 기록을 읽을 수 없어" not in client.get("/").get_data(as_text=True)


def test_다른_사이트에서_보낸_요청은_거절한다(client, ctx):
    response = client.post("/study/today", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert ctx.state.cards is None
    same = client.post("/study/today", headers={"Origin": "http://localhost"})
    assert same.status_code == 302


def test_내_PC_주소가_아니면_거절한다(client):
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/", headers={"Host": "127.0.0.1:8765"}).status_code == 200
