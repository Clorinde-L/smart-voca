#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 단어장 CSV 읽기·검증·쓰기 테스트 (FR-01, FR-02, FR-05, FR-06, VOCA-FR-003, NFR-08)
# 파일 위치: tests/test_wordbook_csv.py
from __future__ import annotations

import csv
import io

import pytest
from conftest import DEFAULT_CSV, DEFAULT_WORD_COUNT, make_words

from smartvoca.core.models import WrongEntry
from smartvoca.storage.wordbook_csv import (
    decode_csv_bytes,
    encode_csv,
    parse_wordbook_text,
    read_wordbook_csv,
    wordbook_csv_text,
    wrong_list_csv_text,
)


def parse(*lines: str):
    return parse_wordbook_text("\n".join(lines) + "\n")


def test_기본_단어장을_읽는다():
    parsed, issues = read_wordbook_csv(DEFAULT_CSV)
    assert issues == [] and len(parsed.entries) == DEFAULT_WORD_COUNT


@pytest.mark.parametrize("header", ["영단어,뜻", "word,meaning", "Word, Meaning"])
def test_과제_제공_형식과_기존_형식의_헤더를_모두_받는다(header):
    parsed, issues = parse(header, "agenda,안건", 'issue,"문제, 쟁점"')
    assert issues == []
    assert parsed.entries == (("agenda", "안건"), ("issue", "문제, 쟁점"))


def test_BOM_이_있든_없든_CP949_든_읽는다():
    text = "영단어,뜻\nagenda,안건\n"
    for data in (text.encode("utf-8-sig"), text.encode("utf-8"), text.encode("cp949")):
        decoded, issue = decode_csv_bytes(data)
        assert issue is None
        parsed, issues = parse_wordbook_text(decoded)
        assert issues == [] and parsed.entries == (("agenda", "안건"),)


def test_파일_안의_중복은_앞줄만_쓰고_줄_번호를_알려_준다():
    parsed, issues = parse("영단어,뜻", "agenda,안건", "Agenda,다른 뜻", "memo,메모", "agenda,또")
    assert issues == []
    assert parsed.entries == (("agenda", "안건"), ("memo", "메모"))
    assert parsed.duplicate_lines == (3, 5)


@pytest.mark.parametrize(
    "lines, rule, line_no",
    [
        (["단어,의미", "a,b"], "V-02", 1),
        (["영단어,뜻", "a,b,c"], "V-03", 2),
        (["영단어,뜻", "a,"], "V-04", 2),
        (["영단어,뜻", "", "  "], "V-06", None),
    ],
)
def test_규칙을_어기면_아무것도_돌려주지_않는다(lines, rule, line_no):
    parsed, issues = parse(*lines)
    assert parsed is None
    assert issues[0].rule == rule and issues[0].line_no == line_no


def test_빈_파일():
    parsed, issues = parse_wordbook_text("")
    assert parsed is None and issues[0].rule == "V-02"


def test_내보낸_단어장을_다시_읽으면_같다():
    words = make_words(5)
    text = wordbook_csv_text(words)
    parsed, issues = parse_wordbook_text(text)
    assert issues == [] and parsed.entries == tuple((w.word, w.meaning) for w in words)
    assert encode_csv(text).startswith(b"\xef\xbb\xbf")  # 엑셀 한글 깨짐 방지 BOM (NFR-08)


def test_오답_목록_내보내기():
    words = make_words(2)
    text = wrong_list_csv_text([WrongEntry(words[1], 3, 1), WrongEntry(words[0], 1, 0)])
    rows = list(csv.reader(io.StringIO(text)))
    assert rows == [["word", "meaning", "wrong_count"], ["w2", "뜻2", "3"], ["w1", "뜻1", "1"]]
    with pytest.raises(ValueError):
        wrong_list_csv_text([])
