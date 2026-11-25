#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - DB 읽기·쓰기: 단어 CRUD, 암기·시험 이력, 오답 목록, 설정, 통계 집계 (ADR-25)
# 파일 위치: src/smartvoca/storage/repository.py
"""SQL 은 이 모듈에만 둔다. 함수는 열린 연결(conn)을 받고, commit 은 부른 쪽(db.transaction)이 한다.

통계 값은 화면에 써 넣지 않고 이력 테이블에서 SQL 로 계산한다 (VOCA-FR-034).
시각은 부른 쪽이 'YYYY-MM-DDTHH:MM:SS' 문자열로 준다 — 테스트에서 시각을 고정하기 위함이다.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence

from ..core.models import (
    Direction,
    ExamKind,
    ExamResult,
    FrequentWrong,
    QuestionFormat,
    Settings,
    StudyCard,
    TrendPoint,
    Word,
    WordStat,
    WrongRecord,
)


class DuplicateWordError(Exception):
    """같은 영단어(대소문자 무시)가 이미 있음."""


class WordNotFoundError(Exception):
    """없는 단어 번호."""


# ── 단어 (VOCA-FR-001 ~ 004) ────────────────────────────────
def list_words(conn: sqlite3.Connection) -> list[Word]:
    """단어장 순서(등록 순 = id 순)로 모든 단어."""
    rows = conn.execute("SELECT id, word, meaning FROM word ORDER BY id").fetchall()
    return [Word(index, row["word"], row["meaning"], row["id"]) for index, row in enumerate(rows)]


def add_word(conn: sqlite3.Connection, word: str, meaning: str, now: str) -> int:
    try:
        cursor = conn.execute(
            "INSERT INTO word (word, meaning, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (word, meaning, now, now),
        )
    except sqlite3.IntegrityError as error:  # word 열의 UNIQUE COLLATE NOCASE
        raise DuplicateWordError(word) from error
    return cursor.lastrowid


def update_word(conn: sqlite3.Connection, word_id: int, word: str, meaning: str, now: str) -> None:
    try:
        cursor = conn.execute(
            "UPDATE word SET word = ?, meaning = ?, updated_at = ? WHERE id = ?",
            (word, meaning, now, word_id),
        )
    except sqlite3.IntegrityError as error:
        raise DuplicateWordError(word) from error
    if cursor.rowcount == 0:
        raise WordNotFoundError(word_id)


def delete_word(conn: sqlite3.Connection, word_id: int) -> None:
    """단어를 지운다. 오답 기록은 함께 지워지고(CASCADE), 암기·시험 이력은 글자로 남는다(SET NULL)."""
    cursor = conn.execute("DELETE FROM word WHERE id = ?", (word_id,))
    if cursor.rowcount == 0:
        raise WordNotFoundError(word_id)


def add_words_skipping_existing(
    conn: sqlite3.Connection, entries: Iterable[tuple[str, str]], now: str
) -> tuple[int, int]:
    """여러 단어를 넣는다. 이미 있는 영단어는 건너뛰고 기존 뜻을 유지한다 (ADR-28). (넣은 수, 건너뛴 수)."""
    added = skipped = 0
    for word, meaning in entries:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO word (word, meaning, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (word, meaning, now, now),
        )
        if cursor.rowcount:
            added += 1
        else:
            skipped += 1
    return added, skipped


def delete_all_words_and_history(conn: sqlite3.Connection) -> None:
    """단어장 바꾸기: 단어와 모든 학습 기록을 지운다 (ADR-03, ADR-28). 설정은 남긴다."""
    conn.execute("DELETE FROM exam_item")
    conn.execute("DELETE FROM exam_session")
    conn.execute("DELETE FROM study_log")
    conn.execute("DELETE FROM wrong_word")
    conn.execute("DELETE FROM word")


# ── 설정 (VOCA-FR-061, 062) ─────────────────────────────────
def get_settings(conn: sqlite3.Connection, user_id: int) -> Settings:
    row = conn.execute(
        "SELECT day_size, review_count, exam_count, exam_direction, exam_format FROM setting WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return Settings()
    try:
        return Settings(
            day_size=row["day_size"],
            review_count=row["review_count"],
            exam_count=row["exam_count"],
            exam_direction=Direction(row["exam_direction"]),
            exam_format=QuestionFormat(row["exam_format"]),
        )
    except ValueError:  # 누가 DB 를 손으로 고쳐 모르는 값이 들어 있으면 기본값으로
        return Settings()


def save_settings(conn: sqlite3.Connection, user_id: int, settings: Settings, now: str) -> None:
    conn.execute(
        "INSERT INTO setting (user_id, day_size, review_count, exam_count, exam_direction, exam_format, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id) DO UPDATE SET day_size = excluded.day_size, review_count = excluded.review_count, "
        "exam_count = excluded.exam_count, exam_direction = excluded.exam_direction, "
        "exam_format = excluded.exam_format, updated_at = excluded.updated_at",
        (
            user_id,
            settings.day_size,
            settings.review_count,
            settings.exam_count,
            settings.exam_direction.value,
            settings.exam_format.value,
            now,
        ),
    )


# ── 암기 이력 (VOCA-FR-014) ─────────────────────────────────
def log_study(
    conn: sqlite3.Connection, user_id: int, cards: Sequence[StudyCard], day_no: int | None, now: str
) -> None:
    """누가·언제·어느 단어·몇 일차를 외웠는지 카드마다 한 줄씩 남긴다.

    word_id 를 하위 쿼리로 넣는 이유: 카드를 보는 사이 다른 화면에서 단어를 지웠으면
    없는 번호가 되어 외래 키 오류가 난다. 그럴 때는 NULL(지운 단어)로 남긴다. save_exam 도 같다.
    """
    conn.executemany(
        "INSERT INTO study_log (user_id, word_id, word, day_no, kind, studied_at) "
        "VALUES (?, (SELECT id FROM word WHERE id = ?), ?, ?, ?, ?)",
        [(user_id, card.word.id, card.word.word, day_no, card.kind.value, now) for card in cards],
    )


def studied_word_ids(conn: sqlite3.Connection, user_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT DISTINCT word_id FROM study_log WHERE user_id = ? AND word_id IS NOT NULL", (user_id,)
    ).fetchall()
    return {row[0] for row in rows}


# ── 시험 이력 (VOCA-FR-026) ─────────────────────────────────
def save_exam(
    conn: sqlite3.Connection,
    user_id: int,
    kind: ExamKind,
    day_no: int | None,
    direction: Direction,
    question_format: QuestionFormat,
    result: ExamResult,
    now: str,
) -> int:
    """시험 1회와 문항마다의 결과(단어, 형식, 방향, 정오, 시각)를 남긴다."""
    cursor = conn.execute(
        "INSERT INTO exam_session (user_id, kind, day_no, direction, format, total, correct, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, kind.value, day_no, direction.value, question_format.value, result.total, result.correct_count, now),
    )
    session_id = cursor.lastrowid
    conn.executemany(
        "INSERT INTO exam_item (session_id, user_id, word_id, word, format, direction, prompt, correct_answer, "
        "given_answer, is_correct, answered_at) VALUES (?, ?, (SELECT id FROM word WHERE id = ?), ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                session_id,
                user_id,
                item.question.target.id,
                item.question.target.word,
                item.question.format.value,
                item.question.direction.value,
                item.question.prompt,
                item.question.answer,
                item.given,
                int(item.correct),
                now,
            )
            for item in result.items
        ],
    )
    return session_id


def day_tested_word_ids(conn: sqlite3.Connection, user_id: int) -> set[int]:
    """일차 시험에 나온 적이 있는 단어 (일차 '완료' 판정, ADR-26)."""
    rows = conn.execute(
        "SELECT DISTINCT i.word_id FROM exam_item i JOIN exam_session s ON s.id = i.session_id "
        "WHERE i.user_id = ? AND s.kind = ? AND i.word_id IS NOT NULL",
        (user_id, ExamKind.DAY.value),
    ).fetchall()
    return {row[0] for row in rows}


def word_stats(conn: sqlite3.Connection, user_id: int, now: str) -> dict[int, WordStat]:
    """단어별 시험 횟수·오답 횟수·마지막 시험 뒤 지난 날 (가중 출제, VOCA-FR-022)."""
    rows = conn.execute(
        "SELECT word_id, COUNT(*) AS test_count, SUM(1 - is_correct) AS wrong_count, "
        "julianday(?) - julianday(MAX(answered_at)) AS days_since FROM exam_item "
        "WHERE user_id = ? AND word_id IS NOT NULL GROUP BY word_id",
        (now, user_id),
    ).fetchall()
    return {
        row["word_id"]: WordStat(row["test_count"], row["wrong_count"], max(row["days_since"], 0.0))
        for row in rows
    }


# ── 오답 목록 (FR-17, FR-22, FR-25) ─────────────────────────
def wrong_records(conn: sqlite3.Connection, user_id: int, word_ids: Iterable[int]) -> dict[int, WrongRecord]:
    ids = sorted(set(word_ids))
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT word_id, wrong_count, streak, in_list FROM wrong_word WHERE user_id = ? AND word_id IN ({placeholders})",
        (user_id, *ids),
    ).fetchall()
    return {row["word_id"]: WrongRecord(row["wrong_count"], row["streak"], bool(row["in_list"])) for row in rows}


def save_wrong_records(conn: sqlite3.Connection, user_id: int, records: Mapping[int, WrongRecord]) -> None:
    conn.executemany(
        "INSERT INTO wrong_word (user_id, word_id, wrong_count, streak, in_list) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (user_id, word_id) DO UPDATE SET wrong_count = excluded.wrong_count, "
        "streak = excluded.streak, in_list = excluded.in_list",
        [(user_id, word_id, r.wrong_count, r.streak, int(r.in_list)) for word_id, r in records.items()],
    )


def wrong_list_rows(conn: sqlite3.Connection, user_id: int) -> list[tuple[int, int, int]]:
    """오답 목록 (단어 번호, 누적 오답, 연속 정답). 오답 많은 순, 같으면 단어장 순서 (FR-22)."""
    rows = conn.execute(
        "SELECT word_id, wrong_count, streak FROM wrong_word WHERE user_id = ? AND in_list = 1 "
        "ORDER BY wrong_count DESC, word_id",
        (user_id,),
    ).fetchall()
    return [(row["word_id"], row["wrong_count"], row["streak"]) for row in rows]


# ── 통계 (VOCA-FR-031 ~ 034) ────────────────────────────────
def exam_totals(conn: sqlite3.Connection, user_id: int) -> tuple[int, int, int]:
    """(시험 횟수, 전체 문항 수, 맞힌 문항 수)."""
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(total), 0), COALESCE(SUM(correct), 0) FROM exam_session WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return row[0], row[1], row[2]


def trend_by_session(conn: sqlite3.Connection, user_id: int, limit: int) -> list[TrendPoint]:
    """회차별 정답률. 최근 limit 회를 오래된 것부터 (VOCA-FR-032)."""
    rows = conn.execute(
        "SELECT id, kind, day_no, total, correct, finished_at FROM exam_session WHERE user_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    points = []
    for row in reversed(rows):
        kind = ExamKind(row["kind"])
        name = f"{row['day_no']}일차" if kind is ExamKind.DAY else kind.label
        label = f"{row['finished_at'][5:10].replace('-', '/')} {name}"
        points.append(TrendPoint(label, row["total"], row["correct"]))
    return points


def trend_by_date(conn: sqlite3.Connection, user_id: int, limit: int) -> list[TrendPoint]:
    """날짜별 정답률. 같은 날의 문항을 모두 합쳐 계산한다. 최근 limit 일을 오래된 것부터."""
    rows = conn.execute(
        "SELECT substr(finished_at, 1, 10) AS day, SUM(total) AS total, SUM(correct) AS correct "
        "FROM exam_session WHERE user_id = ? GROUP BY day ORDER BY day DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [TrendPoint(row["day"], row["total"], row["correct"]) for row in reversed(rows)]


def frequent_wrong(conn: sqlite3.Connection, user_id: int, limit: int) -> list[FrequentWrong]:
    """시험 이력에서 많이 틀린 단어 상위 limit 개 (VOCA-FR-033).

    지운 단어도 이력에 남아 있으면 보여 준다 (뜻은 지금 단어장에 없으면 마지막으로 낸 문제의 정답).
    """
    rows = conn.execute(
        "SELECT i.word AS word, COALESCE(w.meaning, MAX(CASE WHEN i.direction = 'en_ko' THEN i.correct_answer END), '') AS meaning, "
        "SUM(1 - i.is_correct) AS wrong_count, COUNT(*) AS test_count "
        "FROM exam_item i LEFT JOIN word w ON w.id = i.word_id WHERE i.user_id = ? "
        "GROUP BY COALESCE(CAST(i.word_id AS TEXT), 'x' || i.word) HAVING wrong_count > 0 "
        "ORDER BY wrong_count DESC, test_count, i.word LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [FrequentWrong(row["word"], row["meaning"], row["wrong_count"], row["test_count"]) for row in rows]
