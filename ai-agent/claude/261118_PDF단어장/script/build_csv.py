#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-18 - smart-voca - 원본 TSV 로 기본 단어장 CSV(data/toeic_words.csv)를 만든다
# 파일 위치: ai-agent/claude/261118_PDF단어장/script/build_csv.py
#
# 사용법: python build_csv.py [--out <출력 CSV 경로>]
# - 입력: ../data/toeic_words.tsv ('#' 줄과 빈 줄은 무시). 줄 순서가 곧 일차 순서다.
# - 검사: 형식(영단어<TAB>뜻), 영단어 중복(대소문자 무시), 뜻이 [품사] 로 시작하는지. 하나라도 어긋나면 만들지 않는다.
# - 출력: 헤더 word,meaning 의 CSV (UTF-8 BOM, 엑셀에서 한글이 깨지지 않도록)
# 뜻을 고칠 때는 TSV 를 고치고 이 스크립트를 다시 돌린다. CSV 는 직접 고치지 않는다.

import argparse
import csv
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_TSV = SCRIPT_DIR.parent / "data" / "toeic_words.tsv"
PROJECT_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "toeic_words.csv"
MEANING_START = re.compile(r"^\[(명|동|형|부|전|접|대|감)\] ")


def read_entries(tsv_path):
    """(영단어, 뜻) 목록과 문제 목록을 돌려준다."""
    entries = []
    problems = []
    seen_words = set()
    for line_number, line in enumerate(tsv_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t")
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            problems.append(f"{line_number}: 형식 오류 — {stripped}")
            continue
        word, meaning = parts[0].strip(), parts[1].strip()
        if word.lower() in seen_words:
            problems.append(f"{line_number}: 중복 — {word}")
            continue
        if not MEANING_START.match(meaning):
            problems.append(f"{line_number}: 뜻이 [품사] 로 시작하지 않음 — {word}")
        seen_words.add(word.lower())
        entries.append((word, meaning))
    return entries, problems


def main():
    parser = argparse.ArgumentParser(description="기본 단어장 CSV 생성")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="출력 CSV 경로")
    args = parser.parse_args()

    entries, problems = read_entries(SOURCE_TSV)
    if problems:
        print(f"문제가 {len(problems)}건 있어 만들지 않습니다:")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["word", "meaning"])
        writer.writerows(entries)
    longest = max(entries, key=lambda entry: len(entry[1]))
    print(f"저장 완료: {args.out} ({len(entries)}개, 최장 뜻 {len(longest[1])}자: {longest[0]})")


if __name__ == "__main__":
    main()
