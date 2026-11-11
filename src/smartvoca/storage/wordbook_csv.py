#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 단어장 CSV 읽기·검증·쓰기, 단어장 사본 관리 (PR-01, PR-12, PR-13)
# 파일 위치: src/smartvoca/storage/wordbook_csv.py
"""단어장 CSV 저장소.

검증 실패는 예외가 아니라 ValidationIssue 목록으로 돌려준다.
잘못된 파일은 사용자가 흔히 겪는 상황이라 화면이 그대로 목록을 보여 주면 되기 때문이다.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from ..core.models import (
    CHOICE_COUNT,
    ActiveWordbook,
    ValidationIssue,
    Word,
    WordbookSource,
    WrongEntry,
)
from .fileutil import atomic_write_text, move_aside

CSV_ENCODING = "utf-8-sig"  # 쓸 때는 BOM 을 붙이고(엑셀 한글 깨짐 방지), 읽을 때는 있든 없든 처리한다
WORDBOOK_HEADER = ("word", "meaning")
WRONG_LIST_HEADER = ("word", "meaning", "wrong_count")
WORDBOOK_FILENAME = "wordbook.csv"

Row = tuple[int, list[str]]  # (파일의 줄 번호, 열 목록)


def _read_rows(path: Path) -> tuple[list[Row], ValidationIssue | None]:
    """CSV 를 (줄 번호, 열 목록)으로 읽는다. 완전히 빈 줄은 건너뛴다."""
    try:
        with open(path, encoding=CSV_ENCODING, newline="") as file:
            reader = csv.reader(file)
            rows = [(reader.line_num, row) for row in reader if row]
    except UnicodeDecodeError:
        return [], ValidationIssue(
            "V-01", None, "파일을 UTF-8 로 읽을 수 없습니다. UTF-8 로 저장해 주세요."
        )
    except (OSError, csv.Error) as error:
        return [], ValidationIssue("V-01", None, f"파일을 읽을 수 없습니다: {error}")
    return rows, None


def validate_wordbook_rows(rows: Sequence[Row]) -> list[ValidationIssue]:
    """단어장 검증 규칙 V-02 ~ V-07 (데이터 설계서 §6). rows 의 첫 항목이 헤더다."""
    if not rows:
        return [ValidationIssue("V-02", None, "파일이 비어 있습니다. 첫 줄은 word,meaning 이어야 합니다.")]

    header_line, header = rows[0]
    if tuple(cell.strip().lower() for cell in header) != WORDBOOK_HEADER:
        return [
            ValidationIssue(
                "V-02",
                header_line,
                f"첫 줄은 word,meaning 이어야 합니다. (현재: {','.join(header)})",
            )
        ]

    issues = []
    first_line_of = {}  # casefold 한 영단어 → 처음 나온 줄 번호
    for line_no, row in rows[1:]:
        if len(row) != 2:
            issues.append(
                ValidationIssue("V-03", line_no, f"열이 2개여야 합니다. (현재 {len(row)}개)")
            )
            continue
        word, meaning = row[0].strip(), row[1].strip()
        if not word or not meaning:
            empty_column = "word" if not word else "meaning"
            issues.append(ValidationIssue("V-04", line_no, f"{empty_column} 칸이 비어 있습니다."))
            continue
        key = word.casefold()  # 대소문자만 다른 단어도 중복으로 본다
        if key in first_line_of:
            issues.append(
                ValidationIssue(
                    "V-05",
                    line_no,
                    f'단어 "{word}" 가 {first_line_of[key]}번째 줄과 중복됩니다.',
                )
            )
        else:
            first_line_of[key] = line_no
    if issues:
        return issues

    # 4지선다를 만들 수 있는 최소 크기인지 본다
    word_count = len(rows) - 1
    if word_count < CHOICE_COUNT:
        return [
            ValidationIssue(
                "V-06", None, f"단어가 {CHOICE_COUNT}개 이상 있어야 합니다. (현재 {word_count}개)"
            )
        ]
    distinct_meaning_count = len({row[1].strip() for _, row in rows[1:]})
    if distinct_meaning_count < CHOICE_COUNT:
        return [
            ValidationIssue(
                "V-07",
                None,
                f"서로 다른 뜻이 {CHOICE_COUNT}개 이상 있어야 합니다. (현재 {distinct_meaning_count}개)",
            )
        ]
    return []


def read_wordbook_csv(path: Path) -> tuple[list[Word], list[ValidationIssue]]:
    """단어장 CSV 를 읽고 검증한다. 위반이 있으면 ([], 위반 목록)을 돌려준다 (FR-01, FR-02)."""
    rows, read_issue = _read_rows(Path(path))
    if read_issue is not None:
        return [], [read_issue]
    issues = validate_wordbook_rows(rows)
    if issues:
        return [], issues
    words = [
        Word(index=index, word=row[0].strip(), meaning=row[1].strip())
        for index, (_, row) in enumerate(rows[1:])
    ]
    return words, []


def _to_csv_text(header: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)  # 쉼표·큰따옴표가 든 값은 csv 모듈이 알아서 감싼다
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def write_wordbook_csv(path: Path, words: Sequence[Word]) -> None:
    """단어장을 word,meaning CSV 로 쓴다 (FR-05)."""
    text = _to_csv_text(WORDBOOK_HEADER, [(word.word, word.meaning) for word in words])
    atomic_write_text(Path(path), text, CSV_ENCODING)


def write_wrong_list_csv(
    path: Path, entries: Sequence[WrongEntry], wordbook: Sequence[Word]
) -> None:
    """오답 목록을 word,meaning,wrong_count CSV 로 쓴다. 순서는 entries 그대로다 (FR-06)."""
    if not entries:
        raise ValueError("내보낼 오답 단어가 없습니다")
    meaning_of = {word.word: word.meaning for word in wordbook}
    rows = [(entry.word, meaning_of[entry.word], entry.wrong_count) for entry in entries]
    atomic_write_text(Path(path), _to_csv_text(WRONG_LIST_HEADER, rows), CSV_ENCODING)


def replace_wordbook(base_dir: Path, words: Sequence[Word]) -> None:
    """검증을 통과한 단어 목록을 사용자 단어장 사본으로 저장한다 (FR-03).

    사용자가 고른 원본 파일을 계속 읽지 않고 사본을 두는 이유:
    원본이 옮겨지거나 지워져도 다음 실행 때 같은 단어장이 열려야 하기 때문이다.
    """
    write_wordbook_csv(Path(base_dir) / WORDBOOK_FILENAME, words)


def load_active_wordbook(base_dir: Path, default_csv_path: Path) -> ActiveWordbook:
    """시작할 때 쓸 단어장을 고른다: 사용자 단어장 사본이 있으면 그것, 없으면 기본 단어장."""
    custom_path = Path(base_dir) / WORDBOOK_FILENAME
    invalid_backup_path = None
    if custom_path.exists():
        words, issues = read_wordbook_csv(custom_path)
        if not issues:
            return ActiveWordbook(tuple(words), WordbookSource.CUSTOM)
        # 사본이 망가졌으면 보존해 두고 기본 단어장으로 넘어간다 (데이터 설계서 §6.3)
        invalid_backup_path = move_aside(custom_path, "invalid")

    words, issues = read_wordbook_csv(Path(default_csv_path))
    return ActiveWordbook(
        words=tuple(words),
        source=WordbookSource.DEFAULT,
        issues=tuple(issues),
        invalid_backup_path=invalid_backup_path,
    )
