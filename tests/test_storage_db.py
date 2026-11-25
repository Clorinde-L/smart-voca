#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - SQLite 저장소 테스트: 테이블 자동 생성, 기본 단어장 등록, CRUD, 외래 키 (VOCA-NFR-002, 003)
# 파일 위치: tests/test_storage_db.py
from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest
from conftest import DEFAULT_CSV, DEFAULT_WORD_COUNT, small_csv

from smartvoca.core.models import Direction, QuestionFormat, Settings, StudyCard
from smartvoca.storage import db, repository

NOW = "2026-11-25T09:00:00"
TABLES = {"app_user", "word", "setting", "study_log", "exam_session", "exam_item", "wrong_word"}


def table_names(path) -> set[str]:
    with closing(sqlite3.connect(path)) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_빈_DB_에서_테이블을_만들고_기본_단어장을_넣는다(tmp_path):
    path = tmp_path / "sub" / "voca.db"  # 폴더가 없어도 만든다
    assert db.init_db(path, DEFAULT_CSV, NOW) == DEFAULT_WORD_COUNT
    assert TABLES <= table_names(path)
    with db.transaction(path) as conn:
        words = repository.list_words(conn)
        assert len(words) == DEFAULT_WORD_COUNT
        assert words[0].index == 0 and words[0].word == "executive"
        assert repository.get_settings(conn, 1) == Settings()


def test_기본_단어장은_처음_한_번만_넣는다(tmp_path):
    """사용자가 단어를 모두 지운 뒤 다시 켜도 되살아나지 않는다."""
    path = tmp_path / "voca.db"
    db.init_db(path, small_csv(tmp_path / "s.csv", 5), NOW)
    with db.transaction(path) as conn:
        repository.delete_all_words_and_history(conn)
    assert db.init_db(path, small_csv(tmp_path / "s.csv", 5), NOW) == 0
    with db.transaction(path) as conn:
        assert repository.list_words(conn) == []


def test_기본_단어장이_망가졌으면_시작하지_않는다(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("단어,의미\n", encoding="utf-8")
    with pytest.raises(ValueError):
        db.init_db(tmp_path / "voca.db", bad, NOW)


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "voca.db"
    db.init_db(path, small_csv(tmp_path / "s.csv", 5), NOW)
    with db.transaction(path) as connection:
        yield connection


def test_영단어는_대소문자를_무시하고_중복을_막는다(conn):
    with pytest.raises(repository.DuplicateWordError):
        repository.add_word(conn, "W1", "다른 뜻", NOW)
    new_id = repository.add_word(conn, "agenda", "안건", NOW)
    with pytest.raises(repository.DuplicateWordError):
        repository.update_word(conn, new_id, "w2", "x", NOW)
    with pytest.raises(repository.WordNotFoundError):
        repository.update_word(conn, 999, "zzz", "x", NOW)
    with pytest.raises(repository.WordNotFoundError):
        repository.delete_word(conn, 999)


def test_여러_단어를_넣을_때_있는_단어는_건너뛴다(conn):
    added, skipped = repository.add_words_skipping_existing(conn, [("w1", "새 뜻"), ("new", "새")], NOW)
    assert (added, skipped) == (1, 1)
    assert repository.list_words(conn)[0].meaning == "뜻1"  # 기존 뜻 유지 (ADR-28)


def test_단어를_지우면_오답_기록은_지워지고_이력은_글자로_남는다(conn):
    word = repository.list_words(conn)[0]
    repository.log_study(conn, 1, [StudyCard(word)], 1, NOW)
    repository.save_wrong_records(conn, 1, {word.id: repository.WrongRecord(2, 0, True)})
    repository.delete_word(conn, word.id)
    assert repository.wrong_list_rows(conn, 1) == []
    row = conn.execute("SELECT word_id, word FROM study_log").fetchone()
    assert (row["word_id"], row["word"]) == (None, "w1")


def test_없는_단어의_이력은_번호_없이_남긴다(conn):
    word = repository.list_words(conn)[0]
    repository.delete_word(conn, word.id)
    repository.log_study(conn, 1, [StudyCard(word)], 1, NOW)  # 외래 키 오류가 나지 않는다
    assert conn.execute("SELECT word_id FROM study_log").fetchone()[0] is None


def test_설정을_저장하고_다시_읽는다(conn):
    settings = Settings(10, 0, 30, Direction.MIX, QuestionFormat.SHORT)
    repository.save_settings(conn, 1, settings, NOW)
    assert repository.get_settings(conn, 1) == settings
