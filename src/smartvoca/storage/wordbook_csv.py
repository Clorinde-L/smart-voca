#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 단어장 CSV 읽기·검증·쓰기 (PR-01, PR-13, VOCA-FR-003)
# 파일 위치: src/smartvoca/storage/wordbook_csv.py
"""단어장 CSV.

2026-11-25 바뀐 점 (ADR-25, ADR-28)
- 업로드한 파일은 디스크에 저장하지 않고 메모리에서 읽는다 (서버는 /data·/tmp 말고는 쓸 수 없다).
- 헤더는 `word,meaning` 과 과제 제공 CSV 의 `영단어,뜻` 둘 다 받는다.
- 파일 안의 중복 단어는 오류가 아니라 "첫 줄만 쓰고 건너뜀"이다. 건너뛴 줄 번호를 알려 준다.
- 내보내기는 파일 대신 문자열을 돌려준다. 다운로드는 화면이 보낸다.

검증 실패는 예외가 아니라 ValidationIssue 목록으로 돌려준다.
잘못된 파일은 사용자가 흔히 겪는 상황이라 화면이 그대로 목록을 보여 주면 되기 때문이다.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from pathlib import Path

from ..core.models import (
    MAX_MEANING_LENGTH,
    MAX_WORD_LENGTH,
    ParsedWordbook,
    ValidationIssue,
    Word,
    WrongEntry,
)
from ..core.validation import clean_text

CSV_ENCODING = "utf-8-sig"  # 쓸 때는 BOM 을 붙이고(엑셀 한글 깨짐 방지), 읽을 때는 있든 없든 처리한다
FALLBACK_ENCODING = "cp949"  # 엑셀에서 "CSV" 로 저장한 한글 파일
ACCEPTED_HEADERS = (("word", "meaning"), ("영단어", "뜻"))
WORDBOOK_HEADER = ("word", "meaning")
WRONG_LIST_HEADER = ("word", "meaning", "wrong_count")


def decode_csv_bytes(data: bytes) -> tuple[str | None, ValidationIssue | None]:
    """올린 파일의 바이트를 글로 바꾼다. UTF-8(BOM 유무 무관)을 먼저, 안 되면 CP949 로."""
    for encoding in (CSV_ENCODING, FALLBACK_ENCODING):
        try:
            return data.decode(encoding), None
        except UnicodeDecodeError:
            continue
    return None, ValidationIssue("V-01", None, "파일을 읽을 수 없습니다. UTF-8 로 저장한 CSV 를 골라 주세요.")


def parse_wordbook_text(text: str) -> tuple[ParsedWordbook | None, list[ValidationIssue]]:
    """단어장 CSV 글을 읽고 검증한다 (데이터 설계서 §6, 규칙 V-02 ~ V-06).

    위반이 하나라도 있으면 (None, 위반 목록)을 돌려준다 — 일부만 들어가는 일이 없게 한다.
    """
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        rows = [(reader.line_num, row) for row in reader if any(cell.strip() for cell in row)]
    except csv.Error as error:
        return None, [ValidationIssue("V-01", None, f"CSV 형식이 올바르지 않습니다: {error}")]
    if not rows:
        return None, [ValidationIssue("V-02", None, "파일이 비어 있습니다. 첫 줄은 영단어,뜻 이어야 합니다.")]

    header_line, header = rows[0]
    if tuple(cell.strip().lower() for cell in header) not in ACCEPTED_HEADERS:
        return None, [
            ValidationIssue(
                "V-02",
                header_line,
                f"첫 줄은 영단어,뜻 또는 word,meaning 이어야 합니다. (현재: {','.join(header)})",
            )
        ]

    issues: list[ValidationIssue] = []
    entries: list[tuple[str, str]] = []
    duplicate_lines: list[int] = []
    seen: set[str] = set()  # casefold 한 영단어
    for line_no, row in rows[1:]:
        if len(row) != 2:
            issues.append(ValidationIssue("V-03", line_no, f"열이 2개여야 합니다. (현재 {len(row)}개)"))
            continue
        word, meaning = clean_text(row[0]), clean_text(row[1])
        if not word or not meaning:
            column = "영단어" if not word else "뜻"
            issues.append(ValidationIssue("V-04", line_no, f"{column} 칸이 비어 있습니다."))
            continue
        if len(word) > MAX_WORD_LENGTH or len(meaning) > MAX_MEANING_LENGTH:
            issues.append(
                ValidationIssue(
                    "V-04", line_no, f"영단어는 {MAX_WORD_LENGTH}자, 뜻은 {MAX_MEANING_LENGTH}자 이하여야 합니다."
                )
            )
            continue
        key = word.casefold()  # 대소문자만 다른 단어도 같은 단어로 본다
        if key in seen:
            duplicate_lines.append(line_no)
            continue
        seen.add(key)
        entries.append((word, meaning))
    if issues:
        return None, issues
    if not entries:
        return None, [ValidationIssue("V-06", None, "등록할 단어가 없습니다.")]
    return ParsedWordbook(tuple(entries), tuple(duplicate_lines)), []


def read_wordbook_csv(path: Path) -> tuple[ParsedWordbook | None, list[ValidationIssue]]:
    """디스크의 단어장 CSV (기본 단어장 등록에 쓴다, FR-01)."""
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        return None, [ValidationIssue("V-01", None, f"파일을 읽을 수 없습니다: {error}")]
    text, issue = decode_csv_bytes(data)
    if issue is not None:
        return None, [issue]
    return parse_wordbook_text(text)


def _to_csv_text(header: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")  # 쉼표·큰따옴표가 든 값은 csv 모듈이 감싼다
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def wordbook_csv_text(words: Sequence[Word]) -> str:
    """단어장을 word,meaning CSV 글로 (FR-05). 다시 가져오면 같은 단어장이 된다."""
    return _to_csv_text(WORDBOOK_HEADER, [(word.word, word.meaning) for word in words])


def wrong_list_csv_text(entries: Sequence[WrongEntry]) -> str:
    """오답 목록을 word,meaning,wrong_count CSV 글로 (FR-06). 순서는 entries 그대로다."""
    if not entries:
        raise ValueError("내보낼 오답 단어가 없습니다")
    rows = [(entry.word.word, entry.word.meaning, entry.wrong_count) for entry in entries]
    return _to_csv_text(WRONG_LIST_HEADER, rows)


def encode_csv(text: str) -> bytes:
    return text.encode(CSV_ENCODING)
