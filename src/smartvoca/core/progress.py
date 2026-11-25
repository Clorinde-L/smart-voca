#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험 결과를 오답 목록에 반영하는 규칙 (PR-07, PR-08)
# 파일 위치: src/smartvoca/core/progress.py
"""오답 목록 규칙 (FR-17, FR-25).

이 모듈의 함수는 새 기록을 계산하기만 하고 저장하지 않는다.
저장은 부른 쪽(AppSession → storage.repository)이 한다 — 그래야 규칙을 DB 없이 테스트할 수 있다.
2026-11-25 기록이 JSON 에서 SQLite 로 옮겨 가면서(ADR-25) 일차 기록 규칙은 schedule.py 의 계산으로 바뀌었다.
"""
from __future__ import annotations

from collections.abc import Mapping

from .models import GRADUATE_STREAK, ExamKind, ExamResult, WrongRecord


def apply_exam_to_wrong_records(
    records: Mapping[int, WrongRecord], result: ExamResult, kind: ExamKind
) -> tuple[dict[int, WrongRecord], list[int]]:
    """시험 결과로 바뀐 오답 기록과, 이번에 오답 목록에서 빠진 단어 번호를 돌려준다.

    - 틀린 단어: 누적 오답 +1, 연속 정답 0, 목록에 올림 (모든 시험)
    - 맞힌 단어: 오답 시험에서, 목록에 있는 단어만 연속 정답 +1. 3 이 되면 목록에서 뺀다.
      일차·실력 시험에서 맞힌 것은 연속 정답으로 세지 않는다 (요구사항 명세서 D-05)
    - 목록에서 빠져도 누적 오답 횟수는 유지한다 (D-06)
    돌려주는 dict 에는 바뀐 단어만 들어 있다.
    """
    changed: dict[int, WrongRecord] = {}
    graduated: list[int] = []

    def current(word_id: int) -> WrongRecord:
        return changed.get(word_id) or records.get(word_id) or WrongRecord()

    if kind is ExamKind.WRONG:
        for word_id in result.correct_word_ids:
            record = current(word_id)
            if not record.in_list:
                continue
            streak = record.streak + 1
            if streak >= GRADUATE_STREAK:
                changed[word_id] = WrongRecord(record.wrong_count, 0, False)
                graduated.append(word_id)
            else:
                changed[word_id] = WrongRecord(record.wrong_count, streak, True)
    for word_id in result.wrong_word_ids:
        record = current(word_id)
        changed[word_id] = WrongRecord(record.wrong_count + 1, 0, True)
    return changed, graduated
