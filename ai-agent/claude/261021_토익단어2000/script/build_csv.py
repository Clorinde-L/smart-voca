#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-10-21 - smart-voca - 주제별 TSV 단어 목록을 합쳐 토익 단어 CSV(2,000개)를 만든다
# 파일 위치: ai-agent/claude/261021_토익단어2000/script/build_csv.py
#
# 사용법: python build_csv.py [--target 2000] [--out <출력 CSV 경로>]
# - 입력: ../data/*.tsv (파일명 순서대로 읽음, '#' 줄과 빈 줄은 무시)
# - 처리: 영단어 기준(대소문자 무시) 중복 제거, 먼저 나온 항목 유지
# - 출력: 헤더 word,meaning 의 CSV (UTF-8 BOM, 엑셀에서 한글이 깨지지 않도록)

import argparse
import csv
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
PROJECT_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "toeic_words_2000.csv"


def read_word_entries(tsv_path):
    """TSV 한 파일에서 (영단어, 뜻) 목록과 형식 오류 줄 목록을 돌려준다."""
    entries = []
    format_errors = []
    for line_number, line in enumerate(tsv_path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split("\t", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            format_errors.append(f"{tsv_path.name}:{line_number}: {stripped}")
            continue
        entries.append((parts[0].strip(), parts[1].strip()))
    return entries, format_errors


def main():
    parser = argparse.ArgumentParser(description="토익 단어 CSV 생성")
    parser.add_argument("--target", type=int, default=2000, help="최종 단어 수")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="출력 CSV 경로")
    args = parser.parse_args()

    unique_entries = []
    seen_words = set()
    duplicate_words = []
    all_format_errors = []

    for tsv_path in sorted(DATA_DIR.glob("*.tsv")):
        entries, format_errors = read_word_entries(tsv_path)
        all_format_errors.extend(format_errors)
        added_count = 0
        for word, meaning in entries:
            word_key = word.lower()
            if word_key in seen_words:
                duplicate_words.append(f"{tsv_path.name}: {word}")
                continue
            seen_words.add(word_key)
            unique_entries.append((word, meaning))
            added_count += 1
        print(f"{tsv_path.name}: {len(entries)}개 읽음, {added_count}개 추가")

    print(f"중복 제거: {len(duplicate_words)}개")
    for duplicate in duplicate_words:
        print(f"  - {duplicate}")
    print(f"고유 단어 합계: {len(unique_entries)}개")

    if all_format_errors:
        print("형식 오류가 있습니다:")
        for error in all_format_errors:
            print(f"  - {error}")
        sys.exit(1)

    if len(unique_entries) < args.target:
        print(f"목표 {args.target}개에 {args.target - len(unique_entries)}개 부족합니다.")
        sys.exit(1)

    final_entries = unique_entries[:args.target]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["word", "meaning"])
        writer.writerows(final_entries)

    print(f"저장 완료: {args.out} ({len(final_entries)}개, 잘라낸 단어 {len(unique_entries) - args.target}개)")


if __name__ == "__main__":
    main()
