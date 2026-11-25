#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - AppSession 흐름 테스트: 기획서 §10.1 성공 기준을 화면 없이 검증
# 파일 위치: tests/test_session.py
from __future__ import annotations

import random

import pytest
from conftest import DEFAULT_CSV, DEFAULT_DAY_COUNT, DEFAULT_WORD_COUNT, answers_with_wrong, write_csv

from smartvoca.core.cards import CardDeck
from smartvoca.core.models import DayStatus, NoticeKind, WordbookSource
from smartvoca.session import AppSession, WordbookLoadError
from smartvoca.storage.wordbook_csv import write_wordbook_csv


def open_session(base_dir, seed=1) -> AppSession:
    return AppSession.open(base_dir, DEFAULT_CSV, random.Random(seed))


def finish_day(session: AppSession, day_no: int, wrong_words: set[str] = frozenset()):
    """한 일차를 암기하고 시험까지 본다."""
    session.complete_memorize(day_no)
    exam = session.build_day_exam(day_no)
    return session.submit_day_exam(day_no, exam, answers_with_wrong(exam, wrong_words))


# ── 시작 ────────────────────────────────────────────────────
def test_처음_실행하면_기본_단어장과_1일차로_시작한다(tmp_path):
    session = open_session(tmp_path)
    summary = session.summary()
    assert len(session.words) == DEFAULT_WORD_COUNT and len(session.days) == DEFAULT_DAY_COUNT
    assert session.wordbook_source is WordbookSource.DEFAULT
    assert (summary.current_day, summary.done_days, summary.wrong_list_size) == (1, 0, 0)
    assert session.startup_notices == ()
    # 마지막 일차는 남은 단어만으로 구성된다 (FR-07)
    last_day_start = (DEFAULT_DAY_COUNT - 1) * 20
    assert [w.index for w in session.day_words(DEFAULT_DAY_COUNT)] == list(range(last_day_start, DEFAULT_WORD_COUNT))


def test_기본_단어장이_없으면_시작할_수_없다(tmp_path):
    with pytest.raises(WordbookLoadError):
        AppSession.open(tmp_path, tmp_path / "none.csv")


# ── 일차 학습 → 시험 (성공 기준 2) ────────────────────────────
def test_암기_전에는_시험을_볼_수_없다(tmp_path):
    session = open_session(tmp_path)
    with pytest.raises(ValueError):
        session.build_day_exam(1)


def test_카드를_모두_보면_시험이_열리고_결과가_저장된다(tmp_path):
    session = open_session(tmp_path)
    deck = CardDeck(session.day_words(1))
    while deck.next():
        pass
    assert deck.seen_all
    session.complete_memorize(1)
    assert session.day_status(1) is DayStatus.MEMORIZED

    exam = session.build_day_exam(1)
    wrong_words = {exam.questions[0].word, exam.questions[1].word}
    result = session.submit_day_exam(1, exam, answers_with_wrong(exam, wrong_words))

    assert (result.correct_count, result.total) == (18, 20)
    assert session.day_status(1) is DayStatus.DONE
    assert session.day_status(2) is DayStatus.AVAILABLE
    assert {e.word for e in session.wrong_list()} == wrong_words


def test_아무_일차나_먼저_학습할_수_있다(tmp_path):
    """잠금 없음 (ADR-21). 오늘의 학습 추천은 안 끝낸 가장 앞 일차 그대로다."""
    session = open_session(tmp_path)
    finish_day(session, 30)
    assert session.day_status(30) is DayStatus.DONE
    assert session.summary().current_day == 1
    with pytest.raises(ValueError):
        session.complete_memorize(len(session.days) + 1)  # 없는 일차


def test_미응답_답안은_기록을_바꾸지_않는다(tmp_path):
    session = open_session(tmp_path)
    session.complete_memorize(1)
    exam = session.build_day_exam(1)
    with pytest.raises(ValueError):
        session.submit_day_exam(1, exam, [None] * 20)
    assert session.day_status(1) is DayStatus.MEMORIZED
    assert session.wrong_list() == []


# ── 재실행 후 복원 (성공 기준 5) ──────────────────────────────
def test_다시_실행해도_진도와_오답이_복원된다(tmp_path):
    session = open_session(tmp_path)
    first_word = session.day_words(1)[0].word
    finish_day(session, 1, {first_word})
    finish_day(session, 2)
    session.complete_memorize(3)

    reopened = open_session(tmp_path, seed=99)
    summary = reopened.summary()
    assert (summary.current_day, summary.done_days, summary.wrong_list_size) == (3, 2, 1)
    assert reopened.day_status(3) is DayStatus.MEMORIZED
    assert reopened.reviewable_days() == [1, 2, 3]
    assert reopened.wrong_list() == session.wrong_list()


def test_깨진_기록으로_시작하면_알림이_생기고_초기_상태다(tmp_path):
    (tmp_path / "progress.json").write_text("깨짐", encoding="utf-8")
    session = open_session(tmp_path)
    assert [n.kind for n in session.startup_notices] == [NoticeKind.PROGRESS_CORRUPT]
    assert session.startup_notices[0].backup_path.exists()
    assert session.summary().current_day == 1


# ── 오답 학습·오답 시험 (성공 기준 3, 4) ───────────────────────
def test_오답이_횟수_순으로_나오고_3번_연속_맞히면_빠진다(tmp_path):
    session = open_session(tmp_path)
    day1 = [w.word for w in session.day_words(1)]
    finish_day(session, 1, {day1[0], day1[5]})
    finish_day(session, 1, {day1[5]})  # 재시험: day1[5] 를 한 번 더 틀린다

    entries = session.wrong_list()
    assert [(e.word, e.wrong_count) for e in entries] == [(day1[5], 2), (day1[0], 1)]
    assert [w.word for w in session.wrong_words()] == [day1[5], day1[0]]

    graduated_log = []
    for _ in range(3):
        exam = session.build_wrong_exam()
        assert len(exam.questions) == 2
        _, graduated = session.submit_wrong_exam(exam, answers_with_wrong(exam, set()))
        graduated_log.append(sorted(graduated))
    assert graduated_log == [[], [], sorted([day1[0], day1[5]])]
    assert session.wrong_list() == []

    # 졸업한 단어를 일차 재시험에서 다시 틀리면 재등재되고 누적 횟수가 이어진다
    finish_day(session, 1, {day1[5]})
    assert [(e.word, e.wrong_count, e.streak) for e in session.wrong_list()] == [
        (day1[5], 3, 0)
    ]


def test_오답_시험에서_틀리면_연속_정답이_0_으로_돌아간다(tmp_path):
    session = open_session(tmp_path)
    target = session.day_words(1)[0].word
    finish_day(session, 1, {target})
    for wrong in (set(), set(), {target}):
        exam = session.build_wrong_exam()
        session.submit_wrong_exam(exam, answers_with_wrong(exam, wrong))
    entry = session.wrong_list()[0]
    assert (entry.wrong_count, entry.streak) == (2, 0)

    reopened = open_session(tmp_path)
    assert reopened.wrong_list() == session.wrong_list()


def test_오답이_없으면_오답_시험을_만들_수_없다(tmp_path):
    with pytest.raises(ValueError):
        open_session(tmp_path).build_wrong_exam()


# ── 단어장 불러오기·내보내기 (FR-02 ~ FR-06) ───────────────────
def test_단어장을_바꾸면_기록이_초기화되고_재실행해도_유지된다(tmp_path):
    session = open_session(tmp_path / "userdata")
    finish_day(session, 1, {session.day_words(1)[0].word})

    source = tmp_path / "mine.csv"
    write_csv(source, ["word,meaning"] + [f"w{i},뜻{i}" for i in range(45)])
    words, issues = session.check_wordbook_file(source)
    assert issues == [] and len(words) == 45
    assert session.summary().done_days == 1  # 검증만으로는 아무것도 바뀌지 않는다

    session.replace_wordbook(words)
    summary = session.summary()
    assert (summary.total_days, summary.current_day, summary.done_days) == (3, 1, 0)
    assert summary.wrong_list_size == 0
    assert len(session.day_words(3)) == 5
    assert session.wordbook_source is WordbookSource.CUSTOM

    source.unlink()  # 원본을 지워도 사본으로 열린다
    reopened = open_session(tmp_path / "userdata")
    assert len(reopened.words) == 45
    assert reopened.wordbook_source is WordbookSource.CUSTOM
    assert reopened.summary().done_days == 0


def test_검증에_실패한_파일은_단어를_돌려주지_않는다(tmp_path):
    session = open_session(tmp_path / "userdata")
    bad = write_csv(tmp_path / "bad.csv", ["word,meaning", "a,1", "A,2", "c,3", "d,4"])
    words, issues = session.check_wordbook_file(bad)
    assert words == [] and [i.rule for i in issues] == ["V-05"]
    assert len(session.words) == DEFAULT_WORD_COUNT


def test_단어장과_오답_목록을_내보낸다(tmp_path):
    session = open_session(tmp_path / "userdata")
    target = session.day_words(1)[3]
    finish_day(session, 1, {target.word})

    wordbook_path, wrong_path = tmp_path / "wb.csv", tmp_path / "wrong.csv"
    session.export_wordbook(wordbook_path)
    session.export_wrong_list(wrong_path)

    words, issues = session.check_wordbook_file(wordbook_path)
    assert issues == [] and tuple(words) == session.words
    lines = wrong_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "word,meaning,wrong_count" and len(lines) == 2
    assert lines[1].startswith(target.word + ",") and lines[1].endswith(",1")


def test_단어장이_바뀌어_없어진_단어의_기록은_시작할_때_걸러진다(tmp_path):
    base = tmp_path / "userdata"
    session = open_session(base)
    day1 = [w.word for w in session.day_words(1)]
    finish_day(session, 1, {day1[0], day1[1]})

    # 기본 단어장에서 day1[0] 만 뺀 파일을 기본 단어장으로 삼아 다시 연다 (검수 후 수정 상황)
    edited = tmp_path / "edited.csv"
    write_wordbook_csv(edited, [w for w in session.words if w.word != day1[0]])
    reopened = AppSession.open(base, edited, random.Random(1))
    assert [e.word for e in reopened.wrong_list()] == [day1[1]]
    assert reopened.summary().done_days == 1
