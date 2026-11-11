#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 4지선다 시험지 생성과 채점 (PR-05, PR-06)
# 파일 위치: src/smartvoca/core/exam.py
"""시험 로직. 일차 시험과 오답 시험이 함께 쓴다.

난수는 인자로 받은 random.Random 으로만 쓴다.
같은 시드와 같은 입력이면 같은 시험지가 나오므로 테스트에서 결과를 재현할 수 있다 (NFR-04).
"""
from __future__ import annotations

import random
from collections.abc import Sequence

from .models import CHOICE_COUNT, Exam, ExamResult, Question, Word, WrongItem


def _distinct_meanings(wordbook: Sequence[Word]) -> list[str]:
    # dict 는 넣은 순서를 지키므로 "등장 순서대로 중복 없이"를 한 줄로 얻는다
    return list(dict.fromkeys(word.meaning for word in wordbook))


def build_exam(
    targets: Sequence[Word], wordbook: Sequence[Word], rng: random.Random
) -> Exam:
    """targets 의 단어마다 4지선다 문제를 만든다 (FR-14).

    오답 보기는 "다른 단어"가 아니라 "다른 뜻"에서 뽑는다.
    뜻이 같은 단어가 있어도 보기에 같은 문장이 두 번 나오지 않게 하기 위함이다 (ADR-04).
    """
    if not targets:
        raise ValueError("출제할 단어가 없습니다")
    pool = _distinct_meanings(wordbook)
    if len(pool) < CHOICE_COUNT:
        raise ValueError(f"서로 다른 뜻이 {CHOICE_COUNT}개 이상 있어야 합니다")

    questions = []
    for word in rng.sample(list(targets), len(targets)):  # 문제 순서 섞기 (원본은 그대로)
        picked = rng.sample(pool, CHOICE_COUNT)
        # 4개를 뽑아 하나를 뺀다: 정답이 섞여 있으면 정답을, 없으면 마지막 것을.
        # 다시 뽑는 반복 없이 "정답과 다른 뜻 3개"를 한 번에 얻는다.
        if word.meaning in picked:
            picked.remove(word.meaning)
        else:
            picked.pop()
        choices = [word.meaning, *picked]
        rng.shuffle(choices)
        questions.append(
            Question(
                word=word.word,
                choices=tuple(choices),
                answer_index=choices.index(word.meaning),
            )
        )
    return Exam(tuple(questions))


def grade_exam(exam: Exam, answers: Sequence[int | None]) -> ExamResult:
    """채점한다. 답하지 않은 문제가 있으면 채점하지 않는다 (FR-15, FR-16).

    학습 기록은 바꾸지 않는다. 반영은 core.progress 의 apply_* 함수가 한다.
    """
    if len(answers) != len(exam.questions):
        raise ValueError("답의 수가 문제 수와 다릅니다")
    correct_words = []
    wrong_items = []
    for number, (question, answer) in enumerate(zip(exam.questions, answers), start=1):
        if answer is None or not 0 <= answer < len(question.choices):
            raise ValueError(f"{number}번 문제에 답하지 않았습니다")
        if answer == question.answer_index:
            correct_words.append(question.word)
        else:
            wrong_items.append(
                WrongItem(
                    word=question.word,
                    correct_meaning=question.choices[question.answer_index],
                    chosen_meaning=question.choices[answer],
                )
            )
    return ExamResult(
        total=len(exam.questions),
        correct_count=len(correct_words),
        correct_words=tuple(correct_words),
        wrong_items=tuple(wrong_items),
    )
