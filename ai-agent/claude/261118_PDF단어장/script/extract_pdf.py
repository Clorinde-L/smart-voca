#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-18 - smart-voca - 토익 단어목록 PDF 에서 영단어·뜻을 뽑아 원본 TSV 를 만든다 (1회성 도구)
# 파일 위치: ai-agent/claude/261118_PDF단어장/script/extract_pdf.py
#
# 사용법: python extract_pdf.py [--pdf <PDF 경로>] [--out <TSV 경로>]
# - 필요 패키지: pypdf (프로젝트 의존성이 아님. 임시 폴더에 설치해 PYTHONPATH 로 준다)
# - 입력: ai-agent/uploads/토익 단어목록.pdf (2,109개, 쪽마다 25개)
# - 출력: ../data/toeic_words.tsv (번호 순서, 영단어<TAB>뜻)
#
# PDF 의 특이점과 처리:
# 1. 쪽마다 같은 표가 텍스트 층으로 3번 겹쳐 있다. 화면에 보이는 것은 첫 번째 층이고(렌더링으로 확인),
#    나머지 두 층은 일부 단어·뜻이 다른 옛 데이터다. 그래서 번호마다 처음 나온 항목만 쓴다.
# 2. 칸 안에서 줄바꿈된 뜻은 줄 사이 공백 정보가 없다. 기본은 붙이고, 원래 띄어 써야 하는
#    이음매는 SPACED_SEAMS 에 적어 공백을 넣는다(사람이 하나씩 확인한 목록).
# 3. 683번은 영단어(accommodations)가 두 줄로 쪼개져 있어 MANUAL_ENTRIES 로 넣는다.
# 4. 뜻 표기 "(명) A (명) B" 를 단어장 형식 "[명] A; B" 로 바꾼다. 품사가 바뀌면 "[명] A [형] B".

import argparse
import re
import sys
from pathlib import Path

from pypdf import PdfReader

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]
DEFAULT_PDF = PROJECT_ROOT / "ai-agent" / "uploads" / "토익 단어목록.pdf"
DEFAULT_OUTPUT = SCRIPT_DIR.parent / "data" / "toeic_words.tsv"

ENTRY_START = re.compile(r"^(\d+) (\S.*?) \1 (.*)$")
POS_TAG = re.compile(r"\((명|동|형|부|전|접|대|감)\)\s*")
PAGE_DECORATIONS = {
    "토익 독종반", "토익 단어장 앱", "토익 단어 PDF", "토익 단어장", "단어 비교",
    "단어를 클릭하면 자세한 웹 페이지로 이동", "단어 Save 와 단어 Quiz",
    "누구나 자유롭게 이용하고 공유", '구글 검색  "토익 단어" 1위',
}
MANUAL_ENTRIES = {683: ("accommodations", "(명) 숙박 시설")}
# (번호, "앞|뒤") — 줄바꿈 이음매 중 공백이 있어야 하는 곳
SPACED_SEAMS = [
    (32, "픽, 데이터|흐름"),  # traffic
    (38, ", 필수적인|것"),  # imperative
    (79, "는, 신뢰할|수 있는"),  # reliable
    (205, "스트레스를|덜어주다"),  # relieve
    (255, ", 인식하고|있는"),  # aware
    (255, ", 눈치채고|있는"),  # aware
    (465, ", 정신없이|분주한"),  # hectic
    (511, ", 못 하게|하다"),  # discourage
    (594, "불이 붙기|쉬운"),  # flammable
    (702, "다른 것들과|구별되는"),  # distinctive
    (762, "있는, ~할|의무가 있는"),  # bound
    (840, "한, 가치를|매길 수 없"),  # invaluable
    (904, "자동차 엔진|부품)"),  # distributor
    (945, ", 배고파서|고생하다"),  # starve
    (984, ", 흩어지게|하다"),  # scatter
    (1071, "고통스럽게|하다"),  # distress
    (1084, "게 주장하는|능력"),  # assertiveness
    (1103, "다, 외부에|위탁하다"),  # outsource
    (1106, "구조로 된|대형 공연장"),  # amphitheater
    (1163, "론을 이끌어|내다"),  # generalize
    (1209, "피부나 신체|일부)"),  # irritate
    (1214, "등을) 할|여유가 있다"),  # afford
    (1215, "인, 문제를|일으키는"),  # troublesome
    (1250, "고 정직하지|않은"),  # underhanded
    (1270, "확답을 주지|않는"),  # non-committal
    (1284, "다, 조치를|취하다"),  # move
    (1380, "가 변할 수|있는"),  # plastic
    (1455, "기운이 다|빠진"),  # exhausted
    (1486, "또는 종교적|죄악"),  # sin
    (1505, "감옥의 작은|방"),  # cell
    (1551, "지의) 정기|기고란"),  # column
    (1572, "가 목적으로|상점을 방문"),  # shopper
    (1643, ", 돋보이게|하다"),  # distinguish
    (1680, "서) 혐의를|제기하다"),  # allege
    (1777, "만들다, 더|이상 사용되"),  # obsolete
    (1825, ", 우발적인|사건"),  # incidental
    (1831, "비교 대상을|통해 상대적"),  # relatively
    (1985, "수 (수학적|용어)"),  # dividend
    (1992, "좌석 수용|능력"),  # seating
    (2009, ", 튼튼하게|하다"),  # fortify
    (2013, "사용할 수|있는"),  # bilingual
    (2016, "다, 깨끗이|하다"),  # purify
]


def is_decoration(stripped_line):
    """쪽 머리글·바닥글·쪽 번호처럼 단어 항목이 아닌 줄인지."""
    return (
        not stripped_line
        or stripped_line in PAGE_DECORATIONS
        or stripped_line.isdigit()
        or not re.search(r"[가-힣]", stripped_line)
    )


def read_visible_entries(pdf_path):
    """번호 → (영단어, 원문 뜻). 번호마다 처음 나온 항목(화면에 보이는 층)만 남긴다."""
    lines = []
    for page in PdfReader(pdf_path).pages:
        lines.extend((page.extract_text() or "").splitlines())
        lines.append("")  # 쪽 경계에서 항목을 끊는다

    entries = {}
    current = None  # (번호, 영단어, [뜻 조각들])

    def flush():
        if current and current[0] not in entries:
            number, word, pieces = current
            entries[number] = (word, "".join(pieces))

    for line in lines:
        match = ENTRY_START.match(line)
        if match:
            flush()
            current = (int(match.group(1)), match.group(2).strip(), [match.group(3).strip()])
            continue
        stripped = line.strip()
        if is_decoration(stripped):
            flush()
            current = None
        elif current:
            pieces = current[2]
            # 품사 표시 앞, 쉼표·괄호 뒤는 원래 띄어 쓴 자리다
            joiner = " " if pieces[-1].endswith((")", ",")) or stripped.startswith("(") else ""
            pieces.append(joiner + stripped)
    flush()
    entries.update(MANUAL_ENTRIES)
    return entries


def apply_spaced_seams(entries):
    for number, seam in SPACED_SEAMS:
        word, text = entries[number]
        glued = seam.replace("|", "")
        if text.count(glued) != 1:
            raise ValueError(f"{number} {word}: 이음매 '{seam}' 를 찾을 수 없습니다")
        entries[number] = (word, text.replace(glued, seam.replace("|", " ")))


def to_wordbook_meaning(raw_meaning):
    """'(명) A (명) B (형) C' → '[명] A; B [형] C'"""
    parts = POS_TAG.split(re.sub(r"\s+", " ", raw_meaning).strip())[1:]
    groups = []  # [(품사, [뜻들])]
    for pos, body in zip(parts[0::2], parts[1::2]):
        body = body.strip().rstrip(".").strip()
        if not body:
            continue
        if groups and groups[-1][0] == pos:
            groups[-1][1].append(body)
        else:
            groups.append((pos, [body]))
    return " ".join(f"[{pos}] " + "; ".join(bodies) for pos, bodies in groups)


def main():
    parser = argparse.ArgumentParser(description="토익 단어목록 PDF → 원본 TSV")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    entries = read_visible_entries(args.pdf)
    numbers = sorted(entries)
    missing = [n for n in range(1, numbers[-1] + 1) if n not in entries]
    if missing:
        print(f"빠진 번호가 있습니다: {missing}")
        sys.exit(1)
    apply_spaced_seams(entries)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as tsv_file:
        tsv_file.write("# 토익 단어목록 PDF (ai-agent/uploads/토익 단어목록.pdf) 번호 순서 (영단어<TAB>뜻)\n")
        for number in numbers:
            word, raw_meaning = entries[number]
            meaning = to_wordbook_meaning(raw_meaning)
            if not meaning:
                print(f"{number} {word}: 뜻이 비어 있습니다")
                sys.exit(1)
            tsv_file.write(f"{word}\t{meaning}\n")
    print(f"저장 완료: {args.out} ({len(numbers)}개)")


if __name__ == "__main__":
    main()
