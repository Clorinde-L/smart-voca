#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 단어장 CSV 읽기·검증·쓰기·사본 관리 테스트 (PR-01, PR-12, PR-13)
# 파일 위치: tests/test_wordbook_csv.py
from __future__ import annotations

from conftest import DEFAULT_CSV, DEFAULT_WORD_COUNT, make_words, write_csv

from smartvoca.core.models import WordbookSource, WrongEntry
from smartvoca.storage.wordbook_csv import (
    load_active_wordbook,
    read_wordbook_csv,
    replace_wordbook,
    write_wordbook_csv,
    write_wrong_list_csv,
)

GOOD_LINES = ["word,meaning", "a,뜻1", "b,뜻2", "c,뜻3", "d,뜻4"]


def rules(issues):
    return [issue.rule for issue in issues]


# ── 읽기 (FR-01) ────────────────────────────────────────────
def test_기본_단어장을_읽는다(default_words):
    assert len(default_words) == DEFAULT_WORD_COUNT
    assert default_words[0].index == 0
    assert default_words[-1].index == DEFAULT_WORD_COUNT - 1
    assert default_words[0].word == "executive"


def test_BOM_이_없는_파일도_읽는다(tmp_path):
    path = write_csv(tmp_path / "nobom.csv", GOOD_LINES, encoding="utf-8")
    words, issues = read_wordbook_csv(path)
    assert issues == []
    assert words[0].word == "a"


def test_BOM_이_있는_파일의_첫_단어에_BOM_문자가_붙지_않는다(tmp_path):
    path = write_csv(tmp_path / "bom.csv", GOOD_LINES, encoding="utf-8-sig")
    words, _ = read_wordbook_csv(path)
    assert words[0].word == "a"


def test_쉼표가_든_뜻을_그대로_읽는다(tmp_path):
    lines = GOOD_LINES + ['issue,"[명] 문제, 쟁점; (잡지의) 호 [동] 발행하다"']
    words, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert issues == []
    assert words[-1].meaning == "[명] 문제, 쟁점; (잡지의) 호 [동] 발행하다"


def test_빈_줄은_건너뛰고_앞뒤_공백은_뗀다(tmp_path):
    lines = ["word,meaning", " a , 뜻1 ", "", "b,뜻2", "c,뜻3", "d,뜻4"]
    words, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert issues == []
    assert [(w.word, w.meaning) for w in words[:2]] == [("a", "뜻1"), ("b", "뜻2")]


# ── 검증 (FR-02) ────────────────────────────────────────────
def test_없는_파일은_V01(tmp_path):
    words, issues = read_wordbook_csv(tmp_path / "none.csv")
    assert words == [] and rules(issues) == ["V-01"]


def test_UTF8_이_아닌_파일은_V01(tmp_path):
    path = write_csv(tmp_path / "cp949.csv", GOOD_LINES, encoding="cp949")
    words, issues = read_wordbook_csv(path)
    assert words == [] and rules(issues) == ["V-01"]


def test_헤더가_다르면_V02(tmp_path):
    lines = ["영단어,뜻"] + GOOD_LINES[1:]
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert rules(issues) == ["V-02"] and issues[0].line_no == 1


def test_헤더의_대소문자와_공백_차이는_허용한다(tmp_path):
    lines = [" Word , MEANING "] + GOOD_LINES[1:]
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert issues == []


def test_빈_파일은_V02(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    _, issues = read_wordbook_csv(path)
    assert rules(issues) == ["V-02"]


def test_열이_2개가_아니면_V03(tmp_path):
    lines = GOOD_LINES + ["e,뜻5,extra"]
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert rules(issues) == ["V-03"] and issues[0].line_no == 6


def test_빈_칸은_V04(tmp_path):
    lines = GOOD_LINES + ["e,"]
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert rules(issues) == ["V-04"] and "meaning" in issues[0].message


def test_대소문자만_다른_중복을_잡는다(tmp_path):
    lines = ["word,meaning", "x,뜻0", "Agenda,뜻1", "b,뜻2", "agenda,뜻3", "d,뜻4"]
    words, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert words == []
    assert rules(issues) == ["V-05"]
    assert issues[0].line_no == 5 and "3번째 줄" in issues[0].message


def test_위반을_모아서_돌려준다(tmp_path):
    lines = GOOD_LINES + ["a,뜻5", "f,", "g,뜻7,extra"]
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert rules(issues) == ["V-05", "V-04", "V-03"]


def test_단어가_3개뿐이면_V06(tmp_path):
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", GOOD_LINES[:4]))
    assert rules(issues) == ["V-06"]


def test_서로_다른_뜻이_4개_미만이면_V07(tmp_path):
    lines = ["word,meaning", "a,같은 뜻", "b,같은 뜻", "c,뜻3", "d,뜻4"]
    _, issues = read_wordbook_csv(write_csv(tmp_path / "w.csv", lines))
    assert rules(issues) == ["V-07"]


# ── 쓰기 (FR-05, FR-06) ─────────────────────────────────────
def test_내보낸_단어장을_다시_읽으면_같다(tmp_path, default_words):
    path = tmp_path / "out.csv"
    write_wordbook_csv(path, default_words)
    words, issues = read_wordbook_csv(path)
    assert issues == []
    assert words == default_words


def test_내보낸_파일은_BOM_으로_시작한다(tmp_path):
    path = tmp_path / "out.csv"
    write_wordbook_csv(path, make_words(4))
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_오답_목록이_주어진_순서대로_나간다(tmp_path):
    words = make_words(4)
    entries = [WrongEntry("w3", 3, 0), WrongEntry("w1", 1, 2)]
    path = tmp_path / "wrong.csv"
    write_wrong_list_csv(path, entries, words)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines == ["word,meaning,wrong_count", "w3,뜻3,3", "w1,뜻1,1"]


# ── 단어장 사본 (FR-03, 데이터 설계서 §6.3) ───────────────────
def test_사본이_없으면_기본_단어장을_쓴다(tmp_path):
    active = load_active_wordbook(tmp_path, DEFAULT_CSV)
    assert active.source is WordbookSource.DEFAULT
    assert len(active.words) == DEFAULT_WORD_COUNT


def test_교체한_단어장이_다시_열어도_유지된다(tmp_path):
    replace_wordbook(tmp_path, make_words(40))
    active = load_active_wordbook(tmp_path, DEFAULT_CSV)
    assert active.source is WordbookSource.CUSTOM
    assert len(active.words) == 40


def test_망가진_사본은_보존하고_기본_단어장으로_시작한다(tmp_path):
    write_csv(tmp_path / "wordbook.csv", ["잘못된,헤더", "a,b"])
    active = load_active_wordbook(tmp_path, DEFAULT_CSV)
    assert active.source is WordbookSource.DEFAULT
    assert len(active.words) == DEFAULT_WORD_COUNT
    assert active.invalid_backup_path is not None and active.invalid_backup_path.exists()
    assert not (tmp_path / "wordbook.csv").exists()


def test_기본_단어장도_없으면_단어가_비고_위반이_담긴다(tmp_path):
    active = load_active_wordbook(tmp_path, tmp_path / "none.csv")
    assert active.words == ()
    assert rules(active.issues) == ["V-01"]


def test_기본_단어장_파일을_바꾸지_않는다(tmp_path):
    before = DEFAULT_CSV.read_bytes()
    replace_wordbook(tmp_path, make_words(8))
    load_active_wordbook(tmp_path, DEFAULT_CSV)
    assert DEFAULT_CSV.read_bytes() == before
