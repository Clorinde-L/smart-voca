#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 시험지 생성(형식·방향), 가중 출제, 채점 (PR-05, PR-06)
# 파일 위치: src/smartvoca/core/exam.py
"""시험 로직. 일차 시험·오답 시험·실력 시험이 함께 쓴다.

2026-11-25 형식(4지선다·단답형·OX)과 방향(영→한·한→영·섞기), 가중 출제를 넣었다 (ADR-27,
VOCA-FR-021~024). 난수는 인자로 받은 random.Random 으로만 쓴다.
같은 시드와 같은 입력이면 같은 시험지가 나오므로 테스트에서 결과를 재현할 수 있다 (NFR-04).
"""
from __future__ import annotations

import random
import re
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence

from .models import (
    CHOICE_COUNT,
    Answer,
    Direction,
    Exam,
    ExamResult,
    ItemResult,
    Question,
    QuestionFormat,
    Word,
    WordStat,
)

OX_CHOICES = ("O", "X")


# ── 시험지 만들기 ───────────────────────────────────────────
def resolve_direction(direction: Direction, rng: random.Random) -> Direction:
    """섞기면 문제마다 영→한·한→영 중 하나를 고른다 (VOCA-FR-023)."""
    if direction is Direction.MIX:
        return rng.choice((Direction.EN_KO, Direction.KO_EN))
    return direction


def _distractors(
    pool: Sequence[str], count: int, excluded: Collection[str], rng: random.Random
) -> list[str]:
    """pool 에서 excluded 가 아닌 것을 count 개 뽑는다.

    count + len(excluded) 개를 뽑아 걸러 내면, 다시 뽑는 반복 없이 늘 count 개가 남는다.
    """
    sample_size = min(len(pool), count + len(excluded))
    picked = [item for item in rng.sample(pool, sample_size) if item not in excluded][:count]
    if len(picked) < count:
        raise ValueError(f"보기를 만들 단어가 부족합니다 (서로 다른 뜻·단어가 {count + 1}개 이상 필요)")
    return picked


class _Pools:
    """보기 후보. 뜻은 중복 없이, 단어는 뜻이 같은 단어끼리 묶어 둔다.

    오답 보기를 "다른 단어"가 아니라 "다른 뜻"에서 뽑는 이유: 뜻이 같은 단어가 있어도
    보기에 같은 문장이 두 번 나오거나 정답이 둘이 되지 않게 하기 위함이다 (ADR-04).
    """

    def __init__(self, wordbook: Sequence[Word]):
        self.meanings = list(dict.fromkeys(word.meaning for word in wordbook))
        self.words = [word.word for word in wordbook]
        self.words_by_meaning: dict[str, set[str]] = defaultdict(set)
        for word in wordbook:
            self.words_by_meaning[word.meaning].add(word.word)

    def for_question(self, target: Word, direction: Direction) -> tuple[list[str], set[str]]:
        """(보기 후보, 정답과 같은 것으로 칠 값들)."""
        if direction is Direction.EN_KO:
            return self.meanings, {target.meaning}
        return self.words, self.words_by_meaning[target.meaning] | {target.word}


def build_exam(
    targets: Sequence[Word],
    wordbook: Sequence[Word],
    rng: random.Random,
    direction: Direction = Direction.EN_KO,
    question_format: QuestionFormat = QuestionFormat.CHOICE,
) -> Exam:
    """targets 의 단어마다 문제를 하나씩 만든다. 문제 순서는 섞는다 (FR-14, VOCA-FR-023·024)."""
    if not targets:
        raise ValueError("출제할 단어가 없습니다")
    pools = _Pools(wordbook)
    questions = []
    for target in rng.sample(list(targets), len(targets)):  # 문제 순서 섞기 (원본은 그대로)
        actual = resolve_direction(direction, rng)
        if actual is Direction.EN_KO:
            prompt, answer = target.word, target.meaning
        else:
            prompt, answer = target.meaning, target.word
        pool, same_as_answer = pools.for_question(target, actual)

        if question_format is QuestionFormat.CHOICE:
            choices = [answer, *_distractors(pool, CHOICE_COUNT - 1, same_as_answer, rng)]
            rng.shuffle(choices)
            question = Question(
                target, actual, question_format, prompt, answer,
                choices=tuple(choices), answer_index=choices.index(answer),
            )
        elif question_format is QuestionFormat.OX:
            # 절반은 맞는 짝, 절반은 다른 뜻(단어)을 보여 준다
            is_match = rng.random() < 0.5
            shown = answer if is_match else _distractors(pool, 1, same_as_answer, rng)[0]
            question = Question(
                target, actual, question_format, prompt, answer,
                choices=OX_CHOICES, answer_index=0 if is_match else 1, shown=shown,
            )
        else:
            question = Question(target, actual, question_format, prompt, answer)
        questions.append(question)
    return Exam(tuple(questions))


# ── 가중 출제 (VOCA-FR-022) ─────────────────────────────────
def word_weight(stat: WordStat | None) -> float:
    """출제 가중치. 시험 본 적 없는 단어·오래된 단어·자주 틀린 단어일수록 크다 (ADR-27).

    1 + 3·(본 적 없음) + min(지난 날, 30)/10 + 2·min(누적 오답, 5)
    """
    stat = stat or WordStat()
    weight = 1.0
    if stat.test_count == 0:
        weight += 3.0
    elif stat.days_since_test is not None:
        weight += min(stat.days_since_test, 30.0) / 10.0
    weight += 2.0 * min(stat.wrong_count, 5)
    return weight


def pick_weighted(
    words: Sequence[Word], stats: Mapping[int, WordStat], count: int, rng: random.Random
) -> list[Word]:
    """가중치에 비례해 겹치지 않게 count 개를 뽑는다.

    Efraimidis–Spirakis 방법: 단어마다 u^(1/가중치) (u 는 0~1 난수)를 열쇠로 매겨 큰 순으로 고른다.
    가중치가 큰 단어일수록 열쇠가 1 에 가까워져 뽑힐 가능성이 커지지만, 작은 단어도 뽑힐 수 있다.
    """
    if count < 1:
        raise ValueError("문제 수는 1 이상이어야 합니다")
    keys = [rng.random() ** (1.0 / word_weight(stats.get(word.id))) for word in words]
    order = sorted(range(len(words)), key=lambda i: keys[i], reverse=True)
    return [words[i] for i in order[: min(count, len(words))]]


# ── 채점 ───────────────────────────────────────────────────
_POS_TAG = re.compile(r"\[[^\]]*\]")       # [명] [동] 같은 품사 표시
_PARENTHESES = re.compile(r"\([^)]*\)")    # (잡지의) 같은 덧붙임
_SEPARATORS = re.compile(r"[;,/·]")
_IGNORED = re.compile(r"[\s()~.\-]")


def _squash(text: str) -> str:
    """비교용으로 띄어쓰기·괄호·물결표를 지우고 소문자로."""
    return _IGNORED.sub("", text).casefold()


def meaning_parts(meaning: str) -> set[str]:
    """뜻 칸을 정답으로 받을 조각들로 나눈다.

    "[명] 문제, 쟁점; (잡지의) 호 [동] 발행하다" → {문제, 쟁점, 잡지의호, 호, 발행하다}
    """
    parts = set()
    for piece in _SEPARATORS.split(_POS_TAG.sub(";", meaning)):
        for variant in (piece, _PARENTHESES.sub("", piece)):
            key = _squash(variant)
            if key:
                parts.add(key)
    return parts


def is_short_answer_correct(question: Question, given: str) -> bool:
    """단답형 채점 (ADR-27).

    - 한→영: 대소문자·앞뒤 공백을 무시하고 영단어와 같으면 정답
    - 영→한: 뜻 조각 중 하나와 같거나 뜻 칸 전체와 같으면 정답 (띄어쓰기·괄호 무시)
    """
    if not given.strip():
        return False
    if question.direction is Direction.KO_EN:
        return " ".join(given.split()).casefold() == question.answer.casefold()
    key = _squash(given)
    return key in meaning_parts(question.answer) or key == _squash(question.answer)


def grade_exam(exam: Exam, answers: Sequence[Answer]) -> ExamResult:
    """채점한다. 답하지 않은 문제가 있으면 채점하지 않는다 (FR-15, FR-16, VOCA-FR-025).

    학습 기록은 바꾸지 않는다. 반영은 부른 쪽(AppSession)이 한다.
    """
    if len(answers) != len(exam.questions):
        raise ValueError("답의 수가 문제 수와 다릅니다")
    items = []
    for number, (question, answer) in enumerate(zip(exam.questions, answers), start=1):
        if question.format is QuestionFormat.SHORT:
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError(f"{number}번 문제에 답하지 않았습니다")
            given = answer.strip()
            correct = is_short_answer_correct(question, given)
        else:
            if not isinstance(answer, int) or not 0 <= answer < len(question.choices):
                raise ValueError(f"{number}번 문제에 답하지 않았습니다")
            given = question.choices[answer]
            correct = answer == question.answer_index
        items.append(ItemResult(question, given, correct))
    return ExamResult(tuple(items))
