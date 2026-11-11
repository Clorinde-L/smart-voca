#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험 결과 반영·오답 목록·정합화 테스트 (PR-07, PR-08, PR-09, PR-11)
# 파일 위치: tests/test_progress.py
from __future__ import annotations

import pytest
from conftest import make_result, make_words

from smartvoca.core.models import DayRecord, DayStatus, Progress, WordRecord
from smartvoca.core.progress import (
    apply_day_exam_result,
    apply_wrong_exam_result,
    mark_memorized,
    reconcile_progress,
    sorted_wrong_list,
)
from smartvoca.core.schedule import day_status


def memorized_day1() -> Progress:
    return Progress(days={1: DayRecord(memorized=True)})


# ── PR-08 일차 시험 결과 반영 (FR-17 ~ FR-19) ─────────────────
def test_처음_틀린_단어가_오답_목록에_오른다():
    progress = memorized_day1()
    apply_day_exam_result(progress, 1, make_result(wrong=["a"]))
    assert progress.words["a"] == WordRecord(wrong_count=1, streak=0, in_wrong_list=True)
    assert progress.days[1].tested


def test_0점이어도_일차가_완료된다():
    progress = memorized_day1()
    apply_day_exam_result(progress, 1, make_result(wrong=[f"w{i}" for i in range(20)]))
    assert day_status(progress, 1) is DayStatus.DONE
    assert day_status(progress, 2) is DayStatus.AVAILABLE


def test_재시험에서_또_틀리면_횟수만_늘어난다():
    progress = Progress(
        days={1: DayRecord(True, True)}, words={"a": WordRecord(1, 2, True)}
    )
    apply_day_exam_result(progress, 1, make_result(wrong=["a"]))
    assert progress.words["a"] == WordRecord(wrong_count=2, streak=0, in_wrong_list=True)
    assert len(progress.words) == 1


def test_일차_시험에서_맞혀도_연속_정답은_그대로다():
    progress = Progress(
        days={1: DayRecord(True, True)}, words={"a": WordRecord(1, 2, True)}
    )
    apply_day_exam_result(progress, 1, make_result(correct=["a"]))
    assert progress.words["a"] == WordRecord(wrong_count=1, streak=2, in_wrong_list=True)


def test_졸업한_단어를_다시_틀리면_재등재된다():
    progress = Progress(
        days={1: DayRecord(True, True)}, words={"a": WordRecord(2, 0, False)}
    )
    apply_day_exam_result(progress, 1, make_result(wrong=["a"]))
    assert progress.words["a"] == WordRecord(wrong_count=3, streak=0, in_wrong_list=True)


def test_맞힌_단어는_기록이_생기지_않는다():
    progress = memorized_day1()
    apply_day_exam_result(progress, 1, make_result(correct=["a", "b"]))
    assert progress.words == {}


def test_암기_전인_일차의_결과는_반영하지_않는다():
    progress = Progress()
    with pytest.raises(ValueError):
        apply_day_exam_result(progress, 1, make_result(wrong=["a"]))
    assert progress.words == {} and progress.days == {}


def test_암기_완료를_기록한다():
    progress = Progress()
    mark_memorized(progress, 1)
    assert day_status(progress, 1) is DayStatus.MEMORIZED


# ── PR-09 오답 시험 결과 반영 (FR-25) ─────────────────────────
def test_3번_연속_맞히면_목록에서_빠진다():
    progress = Progress(words={"a": WordRecord(2, 0, True)})
    assert apply_wrong_exam_result(progress, make_result(correct=["a"])) == []
    assert apply_wrong_exam_result(progress, make_result(correct=["a"])) == []
    assert progress.words["a"].streak == 2 and progress.words["a"].in_wrong_list
    assert apply_wrong_exam_result(progress, make_result(correct=["a"])) == ["a"]
    assert progress.words["a"] == WordRecord(wrong_count=2, streak=0, in_wrong_list=False)


def test_도중에_틀리면_처음부터_다시_센다():
    progress = Progress(words={"a": WordRecord(1, 2, True)})
    assert apply_wrong_exam_result(progress, make_result(wrong=["a"])) == []
    assert progress.words["a"] == WordRecord(wrong_count=2, streak=0, in_wrong_list=True)


def test_단어마다_따로_센다():
    progress = Progress(words={"a": WordRecord(1, 2, True), "b": WordRecord(1, 0, True)})
    assert apply_wrong_exam_result(progress, make_result(correct=["a", "b"])) == ["a"]
    assert not progress.words["a"].in_wrong_list
    assert progress.words["b"].streak == 1 and progress.words["b"].in_wrong_list


def test_오답_시험은_일차_기록을_바꾸지_않는다():
    progress = Progress(days={1: DayRecord(True)}, words={"a": WordRecord(1, 0, True)})
    apply_wrong_exam_result(progress, make_result(correct=["a"]))
    assert progress.days == {1: DayRecord(True, False)}


# ── PR-07 오답 목록 (FR-22) ──────────────────────────────────
def test_오답_횟수가_많은_순으로_나온다():
    words = make_words(4)
    progress = Progress(
        words={
            "w1": WordRecord(3, 0, True),
            "w2": WordRecord(1, 0, True),
            "w3": WordRecord(2, 1, True),
        }
    )
    entries = sorted_wrong_list(progress, words)
    assert [e.word for e in entries] == ["w1", "w3", "w2"]
    assert (entries[1].wrong_count, entries[1].streak) == (2, 1)


def test_횟수가_같으면_단어장_순서다():
    words = make_words(4)
    progress = Progress(words={"w4": WordRecord(2, 0, True), "w2": WordRecord(2, 0, True)})
    assert [e.word for e in sorted_wrong_list(progress, words)] == ["w2", "w4"]


def test_목록에서_빠진_단어는_나오지_않는다():
    words = make_words(4)
    progress = Progress(words={"w1": WordRecord(4, 0, False)})
    assert sorted_wrong_list(progress, words) == []


# ── PR-11 정합화 (데이터 설계서 §5.5) ─────────────────────────
def test_단어장에_없는_단어의_기록은_버린다():
    progress = Progress(words={"zzz": WordRecord(1, 0, True), "w1": WordRecord(2, 1, True)})
    result = reconcile_progress(progress, make_words(4), total_days=1)
    assert result.words == {"w1": WordRecord(2, 1, True)}


def test_범위를_넘는_일차_기록은_버린다():
    progress = Progress(days={1: DayRecord(True, True), 9: DayRecord(True, True)})
    result = reconcile_progress(progress, make_words(40), total_days=2)
    assert result.days == {1: DayRecord(True, True)}


def test_어긋난_값을_고친다():
    progress = Progress(
        days={1: DayRecord(memorized=False, tested=True)},
        words={"w1": WordRecord(2, 2, False)},
    )
    result = reconcile_progress(progress, make_words(40), total_days=2)
    assert result.days[1] == DayRecord(True, True)
    assert result.words["w1"] == WordRecord(2, 0, False)
