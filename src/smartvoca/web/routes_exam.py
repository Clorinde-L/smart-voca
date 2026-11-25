#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 시험 화면 라우트: 시험 설정(S-09), 응시(S-03), 결과(S-04) (VOCA-FR-021~026)
# 파일 위치: src/smartvoca/web/routes_exam.py
"""시험은 세 종류다: 일차 시험, 오답 시험, 실력 시험(문제 수를 정하고 가중 무작위 출제).

어느 시험이든 먼저 시험 설정 화면에서 방향·형식(실력 시험은 문제 수도)을 고른다.
기본값은 설정 화면에서 저장한 값이다 (VOCA-FR-061).
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for

from ..core.models import EXAM_COUNT_RANGE, DayStatus, ExamKind, QuestionFormat
from ..core.validation import parse_direction, parse_format
from .common import app_session, bp, save_error, web_state
from .state import ExamRun, ResultView, cheer, score_tone

MAX_DOTS = 60             # 문제가 이보다 많으면 번호 점 대신 막대로 보여 준다


def _parse_kind(raw: str | None) -> ExamKind:
    try:
        return ExamKind(raw or ExamKind.RANDOM.value)
    except ValueError:
        abort(400)


def _parse_day(raw: str | None) -> int | None:
    try:
        return int(raw) if raw else None
    except ValueError:
        abort(400)


def _return_url(kind: ExamKind, day_no: int | None) -> str:
    """그만두거나 시작할 수 없을 때 돌아갈 화면. 주소를 요청에서 받지 않고 여기서 정한다 (열린 리다이렉트 방지)."""
    if kind is ExamKind.DAY and day_no is not None:
        return url_for("main.day_detail", day_no=day_no)
    if kind is ExamKind.WRONG:
        return url_for("main.wrong_list")
    return url_for("main.home")


def _title(kind: ExamKind, day_no: int | None) -> str:
    return f"{day_no}일차 시험" if kind is ExamKind.DAY else kind.label


# ── S-09 시험 설정 ──────────────────────────────────────────
@bp.post("/exam/day/<int:day_no>")
def exam_day(day_no: int):
    """일차 상세 화면의 '시험 보기' 버튼 (FR-13, FR-19)."""
    return redirect(url_for("main.exam_setup", kind=ExamKind.DAY.value, day=day_no))


@bp.get("/exam/setup")
def exam_setup():
    session = app_session()
    kind = _parse_kind(request.args.get("kind"))
    day_no = _parse_day(request.args.get("day"))
    settings = session.settings()
    summary = session.summary()
    target_count = None      # 일차·오답 시험은 문제 수가 정해져 있다
    problem = None           # 시작할 수 없는 이유
    if kind is ExamKind.DAY:
        found = session.day(day_no) if day_no else None
        if found is None:
            abort(404)
        status, words = found
        target_count = len(words)
        if status is DayStatus.AVAILABLE:
            problem = "카드를 모두 본 뒤에 시험을 볼 수 있습니다."
    elif kind is ExamKind.WRONG:
        target_count = summary.wrong_list_size
        if not target_count:
            problem = "오답 목록이 비어 있습니다."
    elif not summary.total_words:
        problem = "단어장에 단어가 없습니다. 단어 관리에서 단어를 등록해 주세요."
    return render_template(
        "exam_setup.html",
        kind=kind,
        day_no=day_no,
        title=_title(kind, day_no),
        settings=settings,
        target_count=target_count,
        pool_size=summary.memorized_words or summary.total_words,
        uses_memorized=summary.memorized_words > 0,
        count_range=EXAM_COUNT_RANGE,
        problem=problem,
        back_url=_return_url(kind, day_no),
    )


@bp.post("/exam/start")
def exam_start():
    session, state = app_session(), web_state()
    kind = _parse_kind(request.form.get("kind"))
    day_no = _parse_day(request.form.get("day"))
    direction = parse_direction(request.form.get("direction"))
    question_format = parse_format(request.form.get("format"))
    setup_url = url_for("main.exam_setup", kind=kind.value, day=day_no)
    if direction is None or question_format is None:
        flash("출제 방향과 형식을 골라 주세요.", "error")
        return redirect(setup_url)
    count = None
    if kind is ExamKind.RANDOM:
        low, high = EXAM_COUNT_RANGE
        try:
            count = int(request.form.get("count", ""))
        except ValueError:
            count = 0
        if not low <= count <= high:
            flash(f"문제 수는 {low}~{high} 사이로 입력해 주세요.", "error")
            return redirect(setup_url)
    try:
        exam = session.build_exam(kind, direction, question_format, day_no=day_no, count=count)
    except ValueError as error:
        flash(f"{error}.", "error")
        return redirect(setup_url)
    state.exam = ExamRun(
        kind, _title(kind, day_no), exam, direction, question_format, _return_url(kind, day_no), day_no
    )
    state.result = None
    return redirect(url_for("main.exam"))


# ── S-03 시험 응시 ──────────────────────────────────────────
@bp.get("/exam")
def exam():
    run = web_state().exam
    if run is None:  # 제출했거나 그만둔 뒤 브라우저 '뒤로'로 돌아온 경우
        return redirect(url_for("main.home"))
    return render_template(
        "exam.html",
        run=run,
        question=run.question,
        selected=run.answers[run.position],
        unanswered=run.unanswered_numbers(),
        use_dots=run.total <= MAX_DOTS,
    )


@bp.post("/exam/answer")
def exam_answer():
    """보기 번호(choice) 또는 단답형 글(text)을 받는다."""
    run = web_state().exam
    if run is None:
        return redirect(url_for("main.home"))
    try:
        if run.question.format is QuestionFormat.SHORT:
            run.write(request.form["text"])
        else:
            run.choose(int(request.form["choice"]))
    except (KeyError, ValueError):
        abort(400)
    return redirect(url_for("main.exam"))


@bp.post("/exam/goto")
def exam_goto():
    run = web_state().exam
    if run is None:
        return redirect(url_for("main.home"))
    try:
        run.go_to(int(request.form["position"]))
    except (KeyError, ValueError):
        abort(400)
    return redirect(url_for("main.exam"))


@bp.post("/exam/abort")
def exam_abort():
    """시험을 그만두면 아무것도 반영하지 않고 들어온 화면으로 돌아간다 (ADR-12, DL-03)."""
    state = web_state()
    run, state.exam = state.exam, None
    return redirect(run.return_url if run else url_for("main.home"))


@bp.post("/exam/submit")
def exam_submit():
    """채점 → 문항 이력 저장 → 오답 목록 반영은 AppSession 이 한 번에 한다 (FR-16 ~ FR-19, VOCA-FR-026)."""
    session, state = app_session(), web_state()
    run = state.exam
    if run is None:
        return redirect(url_for("main.home"))
    if not run.complete:
        flash("모든 문제에 답해야 제출할 수 있습니다.", "error")
        return redirect(url_for("main.exam"))
    found = session.day(run.day_no) if run.kind is ExamKind.DAY else None
    was_done = found is not None and found[0] is DayStatus.DONE
    try:
        outcome = session.submit_exam(
            run.kind, run.exam, run.answers, run.direction, run.question_format, run.day_no
        )
    except Exception as error:  # noqa: BLE001  저장 실패는 알리고, 푼 답은 그대로 둔다
        save_error(error)
        return redirect(url_for("main.exam"))
    state.exam = None
    summary = session.summary()
    wrong_note = "오답 목록에 추가되었습니다"
    if run.kind is ExamKind.DAY:
        if was_done:
            status = f"{run.day_no}일차 재시험"
        elif summary.current_day is None:
            status = "모든 일차를 완료했습니다"
        else:
            status = f"{run.day_no}일차 완료 · 다음 추천은 {summary.current_day}일차입니다"
    elif run.kind is ExamKind.WRONG:
        status = f"오답 목록에서 빠진 단어 {len(outcome.graduated)}개 · 남은 오답 {summary.wrong_list_size}개"
        wrong_note = "연속 정답이 0 으로 돌아갑니다"
    else:
        status = f"{run.direction.label} · {run.question_format.label} · {outcome.result.total}문제"
    state.result = ResultView(
        title=f"{run.title} 결과",
        status=status,
        items=outcome.result.items,
        wrong_note=wrong_note,
        kind=run.kind,
        direction=run.direction,
        question_format=run.question_format,
        graduated=outcome.graduated,
        next_day=summary.current_day,
        day_no=run.day_no,
    )
    return redirect(url_for("main.result"))


# ── S-04 시험 결과 ──────────────────────────────────────────
@bp.get("/result")
def result():
    view = web_state().result
    if view is None:
        return redirect(url_for("main.home"))
    correct, total = view.correct_count, view.total
    return render_template(
        "result.html",
        view=view,
        cheer=cheer(correct, total),
        tone=score_tone(correct, total),
        ratio=correct / total if total else 0,
    )
