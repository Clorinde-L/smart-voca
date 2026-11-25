#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - SQLite 연결, 테이블 자동 생성, 기본 단어장 등록 (VOCA-NFR-002, 003, ADR-25)
# 파일 위치: src/smartvoca/storage/db.py
"""DB 파일 위치는 부르는 쪽이 준다 (paths.db_path → 환경변수 DB_PATH, 서버는 /data/voca.db).

처음 실행하면 테이블을 스스로 만들고(NFR-003), 빈 DB 에는 기본 단어장을 넣는다.
기본 단어장은 DB 를 "처음 만들 때 한 번만" 넣는다. 사용자가 단어를 모두 지운 뒤 다시 켰을 때
지운 단어가 되살아나면 안 되기 때문이다. 그래서 PRAGMA user_version 으로 처음인지를 기록한다.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from ..core.models import DEFAULT_USER_ID, Settings
from .wordbook_csv import read_wordbook_csv

SCHEMA_VERSION = 1
DEFAULT_USER_NAME = "guest"

# 테이블 정의 (데이터 설계서 §4). 이력 테이블은 영단어 글자도 함께 둔다:
# 단어를 지워도 "그때 무엇을 외우고 틀렸는지"가 남아야 통계가 바뀌지 않는다 (word_id 는 NULL 이 된다)
SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL
);


CREATE TABLE IF NOT EXISTS word (
    id          INTEGER PRIMARY KEY,
    word        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    meaning     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);


CREATE TABLE IF NOT EXISTS setting (
    user_id         INTEGER PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    day_size        INTEGER NOT NULL,
    review_count    INTEGER NOT NULL,
    exam_count      INTEGER NOT NULL,
    exam_direction  TEXT    NOT NULL,
    exam_format     TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);


CREATE TABLE IF NOT EXISTS study_log (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    word_id     INTEGER REFERENCES word(id) ON DELETE SET NULL,
    word        TEXT    NOT NULL,
    day_no      INTEGER,
    kind        TEXT    NOT NULL,
    studied_at  TEXT    NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_study_log_user_word ON study_log (user_id, word_id);


CREATE TABLE IF NOT EXISTS exam_session (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    kind        TEXT    NOT NULL,
    day_no      INTEGER,
    direction   TEXT    NOT NULL,
    format      TEXT    NOT NULL,
    total       INTEGER NOT NULL,
    correct     INTEGER NOT NULL,
    finished_at TEXT    NOT NULL
);


CREATE TABLE IF NOT EXISTS exam_item (
    id              INTEGER PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES exam_session(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    word_id         INTEGER REFERENCES word(id) ON DELETE SET NULL,
    word            TEXT    NOT NULL,
    format          TEXT    NOT NULL,
    direction       TEXT    NOT NULL,
    prompt          TEXT    NOT NULL,
    correct_answer  TEXT    NOT NULL,
    given_answer    TEXT    NOT NULL,
    is_correct      INTEGER NOT NULL,
    answered_at     TEXT    NOT NULL
);


CREATE INDEX IF NOT EXISTS idx_exam_item_user_word ON exam_item (user_id, word_id);


CREATE TABLE IF NOT EXISTS wrong_word (
    user_id     INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    word_id     INTEGER NOT NULL REFERENCES word(id) ON DELETE CASCADE,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    streak      INTEGER NOT NULL DEFAULT 0,
    in_list     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, word_id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)  # 로컬 실행에서 userdata/ 가 없을 때
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite 는 연결마다 켜야 외래 키(ON DELETE)가 동작한다
    return conn


@contextmanager
def transaction(db_path: Path) -> Iterator[sqlite3.Connection]:
    """연결 하나를 열어 한 트랜잭션으로 쓰고 닫는다. 도중에 예외가 나면 모두 되돌린다.

    요청마다 새로 여는 이유: 연결을 스레드끼리 나눠 쓰면 안 되고, SQLite 는 여는 비용이 작다.
    """
    with closing(connect(db_path)) as conn:
        with conn:  # 성공하면 commit, 예외면 rollback
            yield conn


def init_db(db_path: Path, default_csv_path: Path | None, now: str) -> int:
    """테이블을 만들고 기본 사용자·설정을 넣는다. 처음 만든 DB 면 기본 단어장도 넣는다.

    넣은 기본 단어 수를 돌려준다 (이미 있던 DB 면 0).
    """
    with transaction(db_path) as conn:
        first_time = conn.execute("PRAGMA user_version").fetchone()[0] == 0
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO app_user (id, name, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_USER_NAME, now),
        )
        defaults = Settings()
        conn.execute(
            "INSERT OR IGNORE INTO setting (user_id, day_size, review_count, exam_count, exam_direction, exam_format, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                DEFAULT_USER_ID,
                defaults.day_size,
                defaults.review_count,
                defaults.exam_count,
                defaults.exam_direction.value,
                defaults.exam_format.value,
                now,
            ),
        )
        seeded = 0
        if first_time and default_csv_path is not None:
            parsed, issues = read_wordbook_csv(default_csv_path)
            if parsed is None:
                raise ValueError("기본 단어장을 읽을 수 없습니다: " + "; ".join(i.message for i in issues))
            conn.executemany(
                "INSERT OR IGNORE INTO word (word, meaning, created_at, updated_at) VALUES (?, ?, ?, ?)",
                [(word, meaning, now, now) for word, meaning in parsed.entries],
            )
            seeded = len(parsed.entries)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return seeded
