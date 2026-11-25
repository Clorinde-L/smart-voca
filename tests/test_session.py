#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - AppSession 흐름 테스트: 암기·시험·오답·단어 관리·가져오기·통계가 DB 에 남는가
# 파일 위치: tests/test_session.py
# 2026-11-25 SQLite 전환(ADR-25)과 VOCA-FR 기능에 맞춰 다시 씀
from __future__ import annotations

import random
import sqlite3
from contextlib import closing

import pytest
from conftest import DEFAULT_CSV, DEFAULT_DAY_COUNT, DEFAULT_WORD_COUNT, right_answers

from smartvoca.core.models import (
    DayStatus,
    Direction,
    ExamKind,
    ImportMode,
    QuestionFormat,
    Settings,
    StudyKind,
)
from smartvoca.session import AppSession, WordInputError

EN_KO, CHOICE = Direction.EN_KO, QuestionFormat.CHOICE


def rows(session: AppSession, sql: str, *params):
    with closing(sqlite3.connect(session.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def memorize(session: AppSession, day_no: int) -> None:
    session.complete_memorize(day_no, session.day_cards(day_no))


def take_day_exam(session, day_no, wrong=frozenset(), fmt=CHOICE, direction=EN_KO):
    exam = session.build_exam(ExamKind.DAY, direction, fmt, day_no=day_no)
    return session.submit_exam(ExamKind.DAY, exam, right_answers(exam, set(wrong)), direction, fmt, day_no)


# ── 시작 (VOCA-NFR-003) ─────────────────────────────────────
def test_처음_실행하면_테이블과_기본_단어장으로_시작한다(session):
    summary = session.summary()
    assert (summary.total_words, summary.total_days) == (DEFAULT_WORD_COUNT, DEFAULT_DAY_COUNT)
    assert summary.current_day == 1 and summary.done_days == 0 and summary.memorized_words == 0


def test_다시_열어도_기록이_남는다(tmp_path, clock):
    path = tmp_path / "voca.db"
    first = AppSession.open(path, DEFAULT_CSV, random.Random(1), clock)
    memorize(first, 1)
    take_day_exam(first, 1, wrong={"executive"})
    again = AppSession.open(path, DEFAULT_CSV, random.Random(2), clock)
    assert again.day(1)[0] is DayStatus.DONE
    assert [e.word.word for e in again.wrong_list()] == ["executive"]
    assert len(again.words()) == DEFAULT_WORD_COUNT  # 기본 단어장을 두 번 넣지 않는다


# ── 암기 (VOCA-FR-011 ~ 014) ────────────────────────────────
def test_카드를_모두_보면_암기_이력이_남고_시험을_볼_수_있다(session, clock):
    with pytest.raises(ValueError):
        session.build_exam(ExamKind.DAY, EN_KO, CHOICE, day_no=1)
    memorize(session, 1)
    assert session.day(1)[0] is DayStatus.MEMORIZED
    logged = rows(session, "SELECT user_id, word, day_no, kind, studied_at FROM study_log")
    assert len(logged) == 20
    assert {(r["user_id"], r["day_no"], r["kind"], r["studied_at"]) for r in logged} == {(1, 1, "new", "2026-11-25T09:00:00")}


def test_일차_학습에_전날_단어와_틀린_단어가_섞인다(session):
    memorize(session, 1)
    take_day_exam(session, 1, wrong={"executive", "inventory"})
    cards = session.day_cards(2)
    assert [c.kind for c in cards[:20]] == [StudyKind.NEW] * 20
    extra = cards[20:]
    assert len(extra) == Settings().review_count
    day1 = {w.word for w in session.day(1)[1]}
    assert all(c.word.word in day1 for c in extra)
    assert {c.word.word for c in extra} >= {"executive", "inventory"}  # 틀린 단어는 반드시 들어간다
    assert any(c.kind is StudyKind.WRONG for c in extra)


def test_하루_학습량을_바꾸면_일차를_다시_나누고_외운_단어는_그대로다(session):
    memorize(session, 1)  # 단어 1~20
    session.save_settings(Settings(day_size=10))
    summary = session.summary()
    assert summary.total_days == -(-DEFAULT_WORD_COUNT // 10)
    assert session.day(1)[0] is DayStatus.MEMORIZED and session.day(2)[0] is DayStatus.MEMORIZED
    assert session.day(3)[0] is DayStatus.AVAILABLE
    assert summary.memorized_words == 20


# ── 시험 (VOCA-FR-021 ~ 026) ────────────────────────────────
@pytest.mark.parametrize("fmt", list(QuestionFormat))
def test_시험_문항마다_형식_방향_정오_시각이_DB_에_남는다(session, fmt):
    memorize(session, 1)
    outcome = take_day_exam(session, 1, wrong={"executive"}, fmt=fmt, direction=Direction.MIX)
    assert (outcome.result.correct_count, outcome.result.total) == (19, 20)
    [exam_row] = rows(session, "SELECT kind, day_no, direction, format, total, correct FROM exam_session")
    assert tuple(exam_row) == ("day", 1, "mix", fmt.value, 20, 19)
    items = rows(session, "SELECT word, format, direction, is_correct, answered_at FROM exam_item")
    assert len(items) == 20
    assert {r["direction"] for r in items} <= {"en_ko", "ko_en"}
    assert [r["word"] for r in items if not r["is_correct"]] == ["executive"]
    assert all(r["format"] == fmt.value and r["answered_at"] for r in items)
    assert session.day(1)[0] is DayStatus.DONE


def test_실력_시험은_문제_수만큼_외운_단어에서_낸다(session):
    exam = session.build_exam(ExamKind.RANDOM, EN_KO, CHOICE, count=7)  # 외운 단어가 없으면 전체에서
    assert len(exam.questions) == 7
    memorize(session, 3)
    day3 = {w.id for w in session.day(3)[1]}
    exam = session.build_exam(ExamKind.RANDOM, EN_KO, CHOICE, count=30)
    assert len(exam.questions) == 20  # 외운 단어가 20개뿐
    assert {q.target.id for q in exam.questions} == day3
    outcome = session.submit_exam(ExamKind.RANDOM, exam, right_answers(exam), EN_KO, CHOICE)
    assert outcome.result.correct_count == 20
    assert session.day(3)[0] is DayStatus.MEMORIZED  # 실력 시험은 일차를 완료하지 않는다


def test_오답이_횟수_순으로_나오고_오답_시험_3번_연속_맞히면_빠진다(session):
    memorize(session, 1)
    take_day_exam(session, 1, wrong={"executive", "inventory"})
    take_day_exam(session, 1, wrong={"inventory"})
    assert [(e.word.word, e.wrong_count) for e in session.wrong_list()] == [("inventory", 2), ("executive", 1)]
    graduated = []
    for _ in range(3):
        exam = session.build_exam(ExamKind.WRONG, EN_KO, CHOICE)
        graduated = session.submit_exam(ExamKind.WRONG, exam, right_answers(exam), EN_KO, CHOICE).graduated
    assert set(graduated) == {"executive", "inventory"}
    assert session.wrong_list() == []
    with pytest.raises(ValueError):
        session.build_exam(ExamKind.WRONG, EN_KO, CHOICE)


def test_답하지_않은_시험은_아무것도_남기지_않는다(session):
    memorize(session, 1)
    exam = session.build_exam(ExamKind.DAY, EN_KO, CHOICE, day_no=1)
    with pytest.raises(ValueError):
        session.submit_exam(ExamKind.DAY, exam, [None] * 20, EN_KO, CHOICE, 1)
    assert rows(session, "SELECT * FROM exam_session") == []


# ── 단어 관리 (VOCA-FR-001 ~ 003) ───────────────────────────
def test_단어를_등록_수정_삭제한다(small_session):
    word = small_session.add_word("  agenda ", "[명]  안건 ")
    assert (word.word, word.meaning, word.index) == ("agenda", "[명] 안건", 45)
    with pytest.raises(WordInputError, match="이미 등록"):
        small_session.add_word("AGENDA", "x")
    with pytest.raises(WordInputError):
        small_session.add_word("", "")
    small_session.update_word(word.id, "agendas", "안건들")
    assert small_session.get_word(word.id).word == "agendas"
    small_session.delete_word(word.id)
    assert small_session.get_word(word.id) is None
    with pytest.raises(LookupError):
        small_session.delete_word(word.id)


def test_단어를_더하면_마지막_일차가_다시_학습_전이_된다(small_session):
    memorize(small_session, 3)  # 3일차 = 단어 41~45 (5개)
    assert small_session.day(3)[0] is DayStatus.MEMORIZED
    small_session.add_word("new", "새")
    assert small_session.day(3)[0] is DayStatus.AVAILABLE


def test_CSV_추가는_있는_단어를_건너뛰고_바꾸기는_기록을_지운다(small_session):
    data = "영단어,뜻\nw1,다른 뜻\nnew1,새1\nnew2,새2\nNEW1,중복\n".encode("utf-8-sig")
    parsed, issues = small_session.check_wordbook_upload(data)
    assert issues == []
    report = small_session.import_wordbook(parsed, ImportMode.ADD)
    assert (report.added, report.skipped_existing, report.skipped_in_file) == (2, 1, 1)
    assert len(small_session.words()) == 47
    assert small_session.words()[0].meaning == "뜻1"

    memorize(small_session, 1)
    report = small_session.import_wordbook(parsed, ImportMode.REPLACE)
    assert report.added == 3
    assert [w.word for w in small_session.words()] == ["w1", "new1", "new2"]
    assert small_session.summary().memorized_words == 0
    assert rows(small_session, "SELECT * FROM study_log") == []


def test_내보내기(small_session):
    assert small_session.export_wordbook_csv().decode("utf-8-sig").startswith("word,meaning\r\nw1,뜻1")
    memorize(small_session, 1)
    take_day_exam(small_session, 1, wrong={"w3"})
    assert "w3,뜻3,1" in small_session.export_wrong_list_csv().decode("utf-8-sig")


# ── 통계 (VOCA-FR-031 ~ 034) ────────────────────────────────
def test_통계는_DB_이력에서_계산한다(session, clock):
    memorize(session, 1)
    take_day_exam(session, 1, wrong={"executive", "inventory"})      # 18/20
    clock.advance(days=1)
    take_day_exam(session, 1, wrong={"executive"})                   # 19/20
    exam = session.build_exam(ExamKind.WRONG, EN_KO, CHOICE)
    session.submit_exam(ExamKind.WRONG, exam, right_answers(exam, {"executive"}), EN_KO, CHOICE)  # 1/2

    stats = session.stats()
    assert stats.summary.current_day == 2 and stats.summary.memorized_words == 20
    assert stats.exam_count == 3
    assert stats.overall_ratio == pytest.approx((18 + 19 + 1) / 42)
    assert [(p.correct, p.total) for p in stats.by_session] == [(18, 20), (19, 20), (1, 2)]
    assert [(p.label, p.correct, p.total) for p in stats.by_date] == [
        ("2026-11-25", 18, 20),
        ("2026-11-26", 20, 22),
    ]
    assert [(f.word, f.wrong_count) for f in stats.frequent_wrong] == [("executive", 3), ("inventory", 1)]


def test_지운_단어도_통계_이력에는_남는다(small_session):
    memorize(small_session, 1)
    take_day_exam(small_session, 1, wrong={"w2"})
    small_session.delete_word(small_session.words()[1].id)
    stats = small_session.stats()
    assert stats.frequent_wrong[0].word == "w2" and stats.frequent_wrong[0].meaning == "뜻2"
    assert stats.by_session[0].total == 20
