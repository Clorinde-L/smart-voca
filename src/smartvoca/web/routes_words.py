#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - 단어 관리 화면 라우트: 목록·검색·등록·수정·삭제, CSV 가져오기·내보내기 (S-07)
# 파일 위치: src/smartvoca/web/routes_words.py
"""VOCA-FR-001 ~ 004. 입력 검사와 중복 판정은 AppSession(→ core.validation, DB 의 UNIQUE)이 한다."""
from __future__ import annotations

import io
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, send_file, url_for

from ..core.models import ImportMode
from ..session import WordInputError
from .common import all_web_states, app_session, bp, save_error, web_state
from .state import PendingImport
from .wordsearch import filter_words

MAX_ISSUES_SHOWN = 20     # 단어장 검증 오류는 처음 20건만 보여 준다 (DL-02)
MAX_ROWS_SHOWN = 500      # 검색하지 않았을 때 한 번에 그리는 행 수 (2,000행을 다 그리면 화면이 무거워진다)


@bp.get("/wordbook")
def wordbook():
    session = app_session()
    query = request.args.get("q", "")
    show_all = request.args.get("all") == "1"
    words = session.words()
    settings = session.settings()
    shown = filter_words(words, query, settings.day_size)
    hidden = 0
    if not query and not show_all and len(shown) > MAX_ROWS_SHOWN:
        hidden = len(shown) - MAX_ROWS_SHOWN
        shown = shown[:MAX_ROWS_SHOWN]
    return render_template(
        "wordbook.html",
        query=query,
        rows=[(word.index // settings.day_size + 1, word) for word in shown],
        hidden_count=hidden,
        total=len(words),
        day_count=-(-len(words) // settings.day_size),  # 올림 나눗셈
        wrong_count=len(session.wrong_list()),
        form=request.args,
    )


# ── 등록·수정·삭제 (VOCA-FR-001, 002) ───────────────────────
@bp.post("/words")
def word_add():
    word, meaning = request.form.get("word", ""), request.form.get("meaning", "")
    try:
        added = app_session().add_word(word, meaning)
    except WordInputError as error:
        for problem in error.problems:
            flash(problem, "error")
        return redirect(url_for("main.wordbook", word=word, meaning=meaning) + "#add")
    except Exception as error:  # noqa: BLE001
        save_error(error)
        return redirect(url_for("main.wordbook"))
    flash(f'"{added.word}" 을(를) 등록했습니다. ({added.index + 1}번째 단어)', "info")
    return redirect(url_for("main.wordbook", q=added.word))


@bp.get("/words/<int:word_id>/edit")
def word_edit(word_id: int):
    word = app_session().get_word(word_id)
    if word is None:
        abort(404)
    return render_template("word_edit.html", word=word, back_url=url_for("main.wordbook", q=word.word))


@bp.post("/words/<int:word_id>/edit")
def word_update(word_id: int):
    word, meaning = request.form.get("word", ""), request.form.get("meaning", "")
    try:
        app_session().update_word(word_id, word, meaning)
    except LookupError:
        abort(404)
    except WordInputError as error:
        for problem in error.problems:
            flash(problem, "error")
        return redirect(url_for("main.word_edit", word_id=word_id))
    except Exception as error:  # noqa: BLE001
        save_error(error)
        return redirect(url_for("main.wordbook"))
    flash("단어를 고쳤습니다.", "info")
    return redirect(url_for("main.wordbook", q=" ".join(word.split())))


@bp.post("/words/<int:word_id>/delete")
def word_delete(word_id: int):
    """지운 단어의 오답 기록은 함께 지워지고, 암기·시험 이력은 통계를 위해 남는다 (데이터 설계서 §4)."""
    session = app_session()
    word = session.get_word(word_id)
    if word is None:
        abort(404)
    try:
        session.delete_word(word_id)
    except LookupError:
        abort(404)
    except Exception as error:  # noqa: BLE001
        save_error(error)
        return redirect(url_for("main.wordbook"))
    flash(f'"{word.word}" 을(를) 지웠습니다.', "info")
    return redirect(url_for("main.wordbook", q=request.form.get("q", "")))


# ── 내보내기 (FR-05, FR-06) ─────────────────────────────────
@bp.get("/export/wordbook.csv")
def export_wordbook():
    return _send_csv(app_session().export_wordbook_csv(), "wordbook.csv")


@bp.get("/export/wrong_words.csv")
def export_wrong_list():
    session = app_session()
    if not session.wrong_list():
        flash("내보낼 오답 단어가 없습니다.", "info")
        return redirect(url_for("main.wrong_list"))
    return _send_csv(session.export_wrong_list_csv(), "wrong_words.csv")


def _send_csv(content: bytes, download_name: str):
    """파일을 디스크에 쓰지 않고 바로 다운로드로 보낸다 (서버는 /data·/tmp 말고는 쓸 수 없다)."""
    return send_file(io.BytesIO(content), mimetype="text/csv", as_attachment=True, download_name=download_name)


# ── 가져오기 (VOCA-FR-003, DL-01, DL-02) ───────────────────
@bp.post("/wordbook/import")
def import_wordbook():
    """파일 받기 → 메모리에서 검증 → 확인 페이지. 아직 아무것도 바꾸지 않는다 (FR-02)."""
    session, state = app_session(), web_state()
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("가져올 CSV 파일을 골라 주세요.", "error")
        return redirect(url_for("main.wordbook"))
    file_name = Path(upload.filename).name
    parsed, issues = session.check_wordbook_upload(upload.read())
    if issues:  # DL-02
        state.pending_import = None
        return render_template(
            "import_confirm.html",
            file_name=file_name,
            issues=issues[:MAX_ISSUES_SHOWN],
            hidden_issue_count=max(len(issues) - MAX_ISSUES_SHOWN, 0),
            issue_count=len(issues),
        )
    state.pending_import = PendingImport(file_name, parsed)
    existing = {word.word.casefold() for word in session.words()}
    already = sum(word.casefold() in existing for word, _ in parsed.entries)
    summary = session.summary()
    return render_template(  # DL-01
        "import_confirm.html",
        file_name=file_name,
        issues=None,
        word_count=len(parsed.entries),
        already_count=already,
        new_count=len(parsed.entries) - already,
        duplicate_lines=parsed.duplicate_lines,
        current_total=summary.total_words,
        memorized_words=summary.memorized_words,
        wrong_count=summary.wrong_list_size,
    )


@bp.post("/wordbook/import/confirm")
def import_confirm():
    """'추가' 또는 '바꾸기'를 눌렀을 때만 반영한다 (ADR-28)."""
    state = web_state()
    pending, state.pending_import = state.pending_import, None
    if pending is None:
        return redirect(url_for("main.wordbook"))
    try:
        mode = ImportMode(request.form.get("mode", ""))
    except ValueError:
        abort(400)
    try:
        report = app_session().import_wordbook(pending.parsed, mode)
    except Exception as error:  # noqa: BLE001
        save_error(error)
        return redirect(url_for("main.wordbook"))
    if mode is ImportMode.REPLACE:
        # 옛 단어장의 카드·시험·결과가 어느 브라우저에도 남아 있으면 안 된다
        for other in all_web_states():
            other.clear_progress()
        flash(f"단어장을 바꿨습니다. 단어 {report.added:,}개로 새로 시작합니다.", "info")
        return redirect(url_for("main.home"))
    message = f"단어 {report.added:,}개를 등록했습니다."
    skipped = report.skipped_existing + report.skipped_in_file
    if skipped:
        message += f" 이미 있거나 파일 안에서 겹친 {skipped:,}개는 건너뛰었습니다."
    flash(message, "info")
    return redirect(url_for("main.wordbook"))


@bp.post("/wordbook/import/cancel")
def import_cancel():
    web_state().pending_import = None
    return redirect(url_for("main.wordbook"))
