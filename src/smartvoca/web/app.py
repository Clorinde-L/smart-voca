#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-25 - smart-voca - Flask 앱: URL 과 화면 전이, AppSession 호출을 한곳에서 관리 (UI/UX 설계서 §4)
# 파일 위치: src/smartvoca/web/app.py
"""PyQt 의 MainWindow 가 하던 일을 URL 로 옮겼다.

- 화면을 보여 주는 요청은 GET, 기록이나 진행 상태를 바꾸는 요청은 POST 다.
- POST 는 처리가 끝나면 GET 화면으로 리다이렉트한다(Post/Redirect/Get).
  그래야 새로고침해도 같은 답이 두 번 제출되지 않는다.
- 판단(카드를 다 봤는가, 제출할 수 있는가)은 모두 여기와 state.py 에서 한다. 템플릿은 그리기만 한다.
"""
from __future__ import annotations

import io
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from ..core.models import (
    DAY_SIZE,
    GRADUATE_STREAK,
    DayStatus,
    NoticeKind,
    WordbookSource,
)
from ..session import AppSession
from .state import (
    CardMode,
    CardStudy,
    ExamMode,
    ExamRun,
    PendingImport,
    ResultView,
    WebState,
    cheer,
    score_tone,
)
from .wordsearch import day_of, filter_words

EXTENSION_KEY = "smartvoca"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ISSUES_SHOWN = 20     # 단어장 검증 오류는 처음 20건만 보여 준다 (DL-02)
MAX_DOTS = 60             # 문제가 이보다 많으면 번호 점 대신 막대로 보여 준다
ALLOWED_HOSTS = ("127.0.0.1", "localhost")

bp = Blueprint("main", __name__)


@dataclass
class WebContext:
    session: AppSession
    state: WebState


def create_app(session: AppSession, secret_key: str | None = None) -> Flask:
    app = Flask(__name__)
    # flash 알림을 쿠키에 담을 때 쓰는 키. 실행할 때마다 새로 만든다 (로그인이 없으므로 보관할 필요가 없다)
    app.secret_key = secret_key or secrets.token_hex(16)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.extensions[EXTENSION_KEY] = WebContext(
        session, WebState(startup_notices=list(session.startup_notices))
    )
    app.register_blueprint(bp)
    app.context_processor(lambda: {"GRADUATE_STREAK": GRADUATE_STREAK, "DayStatus": DayStatus})
    return app


def _session() -> AppSession:
    return current_app.extensions[EXTENSION_KEY].session


def _state() -> WebState:
    return current_app.extensions[EXTENSION_KEY].state


def _save_error(error: OSError) -> None:
    """DL-04 저장 실패."""
    flash(f"학습 기록을 저장하지 못했습니다. ({error})", "error")


# ── 보안: 내 PC 에서만, 이 페이지에서 보낸 요청만 ─────────────────
@bp.before_app_request
def _guard_request():
    """다른 웹사이트가 몰래 이 서버로 요청을 보내 기록을 지우는 일을 막는다.

    - Host 검사: 주소가 127.0.0.1·localhost 가 아니면 거절한다 (DNS 재바인딩 방어).
    - Origin 검사: 브라우저는 폼을 보낼 때 출처(Origin)를 붙인다. 출처가 이 서버가 아니면 거절한다.
      출처가 없는 요청(브라우저가 아닌 테스트 클라이언트 등)은 통과시킨다.
    """
    if request.host.rsplit(":", 1)[0] not in ALLOWED_HOSTS:
        abort(403)
    if request.method == "POST":
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin is not None and not (origin + "/").startswith(request.host_url):
            abort(403)


@bp.app_errorhandler(RequestEntityTooLarge)
def _too_large(error):
    flash(f"파일이 너무 큽니다. {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 이하의 CSV 를 골라 주세요.", "error")
    return redirect(url_for("main.wordbook"))


# ── S-01 메인 ───────────────────────────────────────────────
@bp.get("/")
def home():
    session, state = _session(), _state()
    for notice in state.startup_notices:  # DL-04: 시작할 때의 알림은 첫 화면에서 한 번만
        if notice.kind is NoticeKind.PROGRESS_CORRUPT:
            text = "학습 기록을 읽을 수 없어 처음 상태로 시작합니다."
        else:
            text = "저장된 단어장을 읽을 수 없어 기본 단어장으로 시작합니다."
        flash(f'{text} 기존 파일은 "{notice.backup_path}" 에 보존했습니다.', "warning")
    state.startup_notices.clear()

    summary = session.summary()
    today = None
    if summary.current_day is not None:
        day = session.days[summary.current_day - 1]
        today = {
            "day_no": summary.current_day,
            "start": day.start + 1,
            "end": day.end,
            "count": day.end - day.start,
            "memorized": session.day_status(summary.current_day) is DayStatus.MEMORIZED,
        }
    learned_words = sum(
        day.end - day.start
        for day in session.days
        if session.day_status(day.day_no) is DayStatus.DONE
    )
    return render_template(
        "home.html",
        summary=summary,
        today=today,
        learned_words=learned_words,
        has_past_days=bool(session.reviewable_days()),
        wordbook_label=_wordbook_label(session),
    )


def _wordbook_label(session: AppSession) -> str:
    kind = "기본 토익" if session.wordbook_source is WordbookSource.DEFAULT else "사용자 단어장"
    return f"{kind} {len(session.words):,} 단어"


# ── S-02 카드 ───────────────────────────────────────────────
@bp.post("/study/today")
def study_today():
    day_no = _session().summary().current_day
    if day_no is None:
        return redirect(url_for("main.home"))
    return _start_day_cards(day_no)


@bp.post("/study/day/<int:day_no>")
def study_day(day_no: int):
    return _start_day_cards(day_no)


def _start_day_cards(day_no: int):
    session = _session()
    if not 1 <= day_no <= len(session.days) or session.day_status(day_no) is DayStatus.LOCKED:
        flash(f"{day_no}일차는 아직 열리지 않았습니다.", "error")
        return redirect(url_for("main.home"))
    already_memorized = session.day_status(day_no) is not DayStatus.AVAILABLE
    study = CardStudy.start(
        CardMode.DAY, f"{day_no}일차 학습", session.day_words(day_no), day_no, already_memorized
    )
    return _open_cards(study)


@bp.post("/study/review/<int:day_no>")
def study_review(day_no: int):
    session = _session()
    if day_no not in session.reviewable_days():
        flash(f"{day_no}일차는 아직 복습할 수 없습니다.", "error")
        return redirect(url_for("main.days"))
    study = CardStudy.start(
        CardMode.REVIEW, f"{day_no}일차 복습", session.day_words(day_no), day_no
    )
    return _open_cards(study)


@bp.post("/study/wrong")
def study_wrong():
    session = _session()
    words = session.wrong_words()
    if not words:
        flash("틀린 단어가 없습니다.", "info")
        return redirect(url_for("main.wrong_list"))
    wrong_info = {entry.word: entry for entry in session.wrong_list()}
    return _open_cards(CardStudy.start(CardMode.WRONG, "오답 학습", words, wrong_info=wrong_info))


def _open_cards(study: CardStudy):
    _state().cards = study
    _after_card_move(study)  # 카드가 1장뿐이면 열자마자 모두 본 것이다
    return redirect(url_for("main.cards"))


def _after_card_move(study: CardStudy) -> None:
    """일차 학습에서 카드를 모두 본 순간 암기 완료를 저장한다 (FR-12). 복습·오답은 기록하지 않는다."""
    if not study.unlock_if_seen_all() or study.mode is not CardMode.DAY:
        return
    session = _session()
    if session.day_status(study.day_no) is DayStatus.AVAILABLE:
        try:
            session.complete_memorize(study.day_no)
        except OSError as error:
            _save_error(error)


@bp.get("/cards")
def cards():
    study = _state().cards
    if study is None:
        return redirect(url_for("main.home"))
    back_url = {
        CardMode.REVIEW: url_for("main.days"),
        CardMode.WRONG: url_for("main.wrong_list"),
    }.get(study.mode, url_for("main.home"))
    return render_template(
        "cards.html",
        study=study,
        deck=study.deck,
        word=study.deck.current,
        entry=study.wrong_info.get(study.deck.current.word),
        hide_meaning=_state().hide_meaning,
        back_url=back_url,
    )


@bp.post("/cards/next")
def cards_next():
    return _move_card(forward=True)


@bp.post("/cards/prev")
def cards_prev():
    return _move_card(forward=False)


def _move_card(forward: bool):
    study = _state().cards
    if study is None:
        return redirect(url_for("main.home"))
    moved = study.deck.next() if forward else study.deck.prev()
    if moved:
        _after_card_move(study)
    return redirect(url_for("main.cards"))


@bp.post("/cards/hide")
def cards_hide():
    _state().hide_meaning = request.form.get("hide") == "on"
    return redirect(url_for("main.cards"))


@bp.post("/cards/action")
def cards_action():
    """시험 보기 / 오답 시험. 카드를 모두 봐야 켜진다 (FR-12, FR-24)."""
    study = _state().cards
    if study is None or not study.has_action or not study.unlocked:
        return redirect(url_for("main.cards") if study else url_for("main.home"))
    if study.mode is CardMode.DAY:
        return _start_day_exam(study.day_no, url_for("main.cards"))
    return _start_wrong_exam(url_for("main.cards"))


# ── S-03 시험 응시 ──────────────────────────────────────────
@bp.post("/exam/day/<int:day_no>")
def exam_day(day_no: int):
    """지난 일차 화면의 '시험' 버튼 (FR-13, FR-19)."""
    return _start_day_exam(day_no, url_for("main.days"))


def _start_day_exam(day_no: int, return_url: str):
    try:
        exam = _session().build_day_exam(day_no)
    except ValueError as error:
        flash(f"{error}.", "error")
        return redirect(return_url)
    return _begin_exam(ExamRun(ExamMode.DAY, f"{day_no}일차 시험", exam, return_url, day_no))


def _start_wrong_exam(return_url: str):
    try:
        exam = _session().build_wrong_exam()
    except ValueError as error:
        flash(f"{error}.", "error")
        return redirect(return_url)
    return _begin_exam(ExamRun(ExamMode.WRONG, "오답 시험", exam, return_url))


def _begin_exam(run: ExamRun):
    state = _state()
    state.exam, state.result = run, None
    return redirect(url_for("main.exam"))


@bp.get("/exam")
def exam():
    run = _state().exam
    if run is None:  # 제출했거나 그만둔 뒤 브라우저 '뒤로'로 돌아온 경우
        return redirect(url_for("main.home"))
    return render_template(
        "exam.html",
        run=run,
        question=run.exam.questions[run.position],
        selected=run.answers[run.position],
        unanswered=run.unanswered_numbers(),
        use_dots=run.total <= MAX_DOTS,
    )


@bp.post("/exam/answer")
def exam_answer():
    run = _state().exam
    if run is None:
        return redirect(url_for("main.home"))
    try:
        run.choose(int(request.form["choice"]))
    except (KeyError, ValueError):
        abort(400)
    return redirect(url_for("main.exam"))


@bp.post("/exam/goto")
def exam_goto():
    run = _state().exam
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
    state = _state()
    run, state.exam = state.exam, None
    return redirect(run.return_url if run else url_for("main.home"))


@bp.post("/exam/submit")
def exam_submit():
    """채점 → 기록 반영 → 저장은 AppSession 이 한 번에 한다 (FR-16 ~ FR-19, FR-26)."""
    session, state = _session(), _state()
    run = state.exam
    if run is None:
        return redirect(url_for("main.home"))
    if not run.complete:
        flash("모든 문제에 답해야 제출할 수 있습니다.", "error")
        return redirect(url_for("main.exam"))
    state.exam = None
    try:
        if run.mode is ExamMode.DAY:
            state.result = _submit_day_exam(session, run)
        else:
            result, graduated = session.submit_wrong_exam(run.exam, run.answers)
            remaining = session.summary().wrong_list_size
            state.result = ResultView(
                title="오답 시험 결과",
                status=f"오답 목록에서 빠진 단어 {len(graduated)}개 · 남은 오답 {remaining}개",
                result=result,
                wrong_note="연속 정답이 0 으로 돌아갑니다",
                graduated=tuple(graduated),
                is_wrong_exam=True,
            )
    except OSError as error:
        _save_error(error)
        return redirect(url_for("main.home"))
    return redirect(url_for("main.result"))


def _submit_day_exam(session: AppSession, run: ExamRun) -> ResultView:
    day_no = run.day_no
    is_retest = session.day_status(day_no) is DayStatus.DONE
    result = session.submit_day_exam(day_no, run.exam, run.answers)
    next_day = day_no + 1 if day_no < len(session.days) else None
    if is_retest:
        status = f"{day_no}일차 재시험"
    elif next_day is None:
        status = "모든 일차를 완료했습니다"
    else:
        status = f"{day_no}일차 완료 · {next_day}일차가 열렸습니다"
    return ResultView(
        title=f"{day_no}일차 시험 결과",
        status=status,
        result=result,
        wrong_note="오답 목록에 추가되었습니다",
        next_day=None if is_retest else next_day,
    )


# ── S-04 시험 결과 ──────────────────────────────────────────
@bp.get("/result")
def result():
    view = _state().result
    if view is None:
        return redirect(url_for("main.home"))
    correct, total = view.result.correct_count, view.result.total
    return render_template(
        "result.html",
        view=view,
        cheer=cheer(correct, total),
        tone=score_tone(correct, total),
        ratio=correct / total if total else 0,
    )


# ── S-05 지난 일차 ──────────────────────────────────────────
@bp.get("/days")
def days():
    session = _session()
    rows = []
    for day_no in session.reviewable_days():
        words = session.day_words(day_no)
        rows.append(
            {
                "day_no": day_no,
                "range": f"{words[0].word} ~ {words[-1].word}",
                "status": session.day_status(day_no),
            }
        )
    return render_template("day_list.html", rows=rows)


# ── S-06 오답 목록 ──────────────────────────────────────────
@bp.get("/wrong")
def wrong_list():
    session = _session()
    meaning_of = {word.word: word.meaning for word in session.wrong_words()}
    rows = [(entry, meaning_of[entry.word]) for entry in session.wrong_list()]
    return render_template("wrong_list.html", rows=rows)


# ── S-07 단어 목록 ──────────────────────────────────────────
@bp.get("/wordbook")
def wordbook():
    session = _session()
    query = request.args.get("q", "")
    shown = filter_words(session.words, query)
    return render_template(
        "wordbook.html",
        query=query,
        rows=[(day_of(word), word) for word in shown],
        total=len(session.words),
        day_count=len(session.days),
        wordbook_label=_wordbook_label(session),
        wrong_count=session.summary().wrong_list_size,
    )


@bp.get("/export/wordbook.csv")
def export_wordbook():
    return _export_csv(lambda path: _session().export_wordbook(path), "wordbook.csv")


@bp.get("/export/wrong_words.csv")
def export_wrong_list():
    if not _session().wrong_list():
        flash("내보낼 오답 단어가 없습니다.", "info")
        return redirect(request.referrer or url_for("main.wrong_list"))
    return _export_csv(lambda path: _session().export_wrong_list(path), "wrong_words.csv")


def _export_csv(write, download_name: str):
    """세션이 임시 파일에 쓰게 한 뒤 그 내용을 다운로드로 보낸다 (FR-05, FR-06).

    세션의 내보내기는 경로를 받으므로 그대로 두고, 웹에서는 임시 폴더를 거친다.
    """
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / download_name
        try:
            write(path)
        except OSError as error:
            flash(f"파일을 만들지 못했습니다. ({error})", "error")
            return redirect(url_for("main.wordbook"))
        content = path.read_bytes()
    return send_file(
        io.BytesIO(content), mimetype="text/csv", as_attachment=True, download_name=download_name
    )


@bp.post("/wordbook/import")
def import_wordbook():
    """파일 받기 → 검증 → 확인 페이지 (UI/UX 설계서 §6.3). 아직 아무것도 바꾸지 않는다 (FR-02)."""
    session, state = _session(), _state()
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("불러올 CSV 파일을 골라 주세요.", "error")
        return redirect(url_for("main.wordbook"))
    file_name = Path(upload.filename).name
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "upload.csv"
        upload.save(path)
        words, issues = session.check_wordbook_file(path)
    if issues:  # DL-02
        state.pending_import = None
        return render_template(
            "import_confirm.html",
            file_name=file_name,
            issues=issues[:MAX_ISSUES_SHOWN],
            hidden_issue_count=max(len(issues) - MAX_ISSUES_SHOWN, 0),
            issue_count=len(issues),
        )
    state.pending_import = PendingImport(file_name, tuple(words))
    summary = session.summary()
    return render_template(  # DL-01
        "import_confirm.html",
        file_name=file_name,
        issues=None,
        word_count=len(words),
        day_count=-(-len(words) // DAY_SIZE),  # 올림 나눗셈
        done_days=summary.done_days,
        wrong_count=summary.wrong_list_size,
    )


@bp.post("/wordbook/import/confirm")
def import_confirm():
    """'바꾸기'를 눌렀을 때만 단어장을 바꾸고 기록을 지운다 (FR-03, FR-04, ADR-03)."""
    state = _state()
    pending, state.pending_import = state.pending_import, None
    if pending is None:
        return redirect(url_for("main.wordbook"))
    try:
        _session().replace_wordbook(pending.words)
    except OSError as error:
        _save_error(error)
        return redirect(url_for("main.wordbook"))
    # 옛 단어장의 카드·시험·결과가 남아 있으면 안 된다
    state.cards = state.exam = state.result = None
    day_count = -(-len(pending.words) // DAY_SIZE)
    flash(f"단어장을 바꿨습니다. ({len(pending.words):,} 단어, {day_count}일차)", "info")
    return redirect(url_for("main.home"))


@bp.post("/wordbook/import/cancel")
def import_cancel():
    _state().pending_import = None
    return redirect(url_for("main.wordbook"))
