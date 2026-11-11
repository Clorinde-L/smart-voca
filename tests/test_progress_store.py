#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 학습 기록 저장·복원·손상 처리 테스트 (PR-10, PR-11)
# 파일 위치: tests/test_progress_store.py
from __future__ import annotations

import json

import pytest

from smartvoca.core.models import DayRecord, LoadStatus, Progress, WordRecord
from smartvoca.storage import fileutil
from smartvoca.storage.progress_store import ProgressStore


def sample_progress() -> Progress:
    return Progress(
        days={1: DayRecord(True, True), 2: DayRecord(True, False)},
        words={"accommodate": WordRecord(2, 1, True), "agenda": WordRecord(1, 0, False)},
    )


def valid_data() -> dict:
    return {
        "schema_version": 1,
        "saved_at": "2026-11-11T14:30:00",
        "days": {"1": {"memorized": True, "tested": True}},
        "words": {"a": {"wrong_count": 1, "streak": 0, "in_wrong_list": True}},
    }


def test_저장한_기록을_다시_읽으면_같다(tmp_path):
    store = ProgressStore(tmp_path)
    store.save(sample_progress())
    loaded = store.load()
    assert loaded.status is LoadStatus.OK
    assert loaded.progress == sample_progress()


def test_저장_형식이_설계와_같다(tmp_path):
    store = ProgressStore(tmp_path)
    store.save(sample_progress())
    data = json.loads(store.path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["days"]["2"] == {"memorized": True, "tested": False}
    assert data["words"]["accommodate"] == {
        "wrong_count": 2,
        "streak": 1,
        "in_wrong_list": True,
    }
    assert "saved_at" in data
    assert not store.path.with_name("progress.json.tmp").exists()


def test_폴더가_없어도_저장한다(tmp_path):
    store = ProgressStore(tmp_path / "userdata")
    store.save(Progress())
    assert store.path.exists()


def test_기록이_없으면_초기_상태다(tmp_path):
    loaded = ProgressStore(tmp_path).load()
    assert loaded.status is LoadStatus.NEW
    assert loaded.progress == Progress()


def test_쓰는_도중_실패해도_직전_기록이_남는다(tmp_path, monkeypatch):
    store = ProgressStore(tmp_path)
    before = Progress(days={1: DayRecord(True, True)})
    store.save(before)

    def fail_replace(src, dst):
        raise OSError("교체 직전에 꺼짐")

    monkeypatch.setattr(fileutil.os, "replace", fail_replace)
    with pytest.raises(OSError):
        store.save(Progress(days={1: DayRecord(True, True), 2: DayRecord(True, True)}))
    monkeypatch.undo()

    assert store.load().progress == before


def test_깨진_기록은_보존하고_초기_상태로_시작한다(tmp_path):
    store = ProgressStore(tmp_path)
    store.path.write_text("{ 깨진 내용", encoding="utf-8")
    loaded = store.load()
    assert loaded.status is LoadStatus.CORRUPT
    assert loaded.progress == Progress()
    assert loaded.backup_path.name.startswith("progress.corrupt-")
    assert loaded.backup_path.read_text(encoding="utf-8") == "{ 깨진 내용"
    assert not store.path.exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema_version=2),
        lambda d: d.update(days=[]),
        lambda d: d.pop("words"),
        lambda d: d["days"].update({"x": {"memorized": True, "tested": True}}),
        lambda d: d["days"].update({"0": {"memorized": True, "tested": True}}),
        lambda d: d["days"]["1"].update(tested="yes"),
        lambda d: d["words"]["a"].update(streak=5),
        lambda d: d["words"]["a"].update(wrong_count=-1),
        lambda d: d["words"]["a"].update(wrong_count=True),
        lambda d: d["words"]["a"].pop("in_wrong_list"),
    ],
)
def test_형식을_벗어난_기록은_손상이다(tmp_path, mutate):
    data = valid_data()
    mutate(data)
    store = ProgressStore(tmp_path)
    store.path.write_text(json.dumps(data), encoding="utf-8")
    assert store.load().status is LoadStatus.CORRUPT


def test_최상위가_객체가_아니면_손상이다(tmp_path):
    store = ProgressStore(tmp_path)
    store.path.write_text("[1, 2, 3]", encoding="utf-8")
    assert store.load().status is LoadStatus.CORRUPT


def test_올바른_기록은_손상이_아니다(tmp_path):
    store = ProgressStore(tmp_path)
    store.path.write_text(json.dumps(valid_data()), encoding="utf-8")
    loaded = store.load()
    assert loaded.status is LoadStatus.OK
    assert loaded.progress.days == {1: DayRecord(True, True)}
