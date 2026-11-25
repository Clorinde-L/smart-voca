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
from urllib.parse import urlsplit

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

bp = Blueprint("main", __name__)


@dataclass
class WebContext:
    session: AppSession
    state: WebState


def create_app(session: AppSession, secret_key: str | None = None) -> Flask:
    app = Flask(__name__)
    # 쿠키(flash 알림)에 서명할 때 쓰는 키. 환경변수 SECRET_KEY 로 받고, 없으면 기동할 때 무작위로 만든다 (NFR-004, R-08)
    app.secret_key = secret_key or secrets.token_hex(32)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.extensions[EXTENSION_KEY] = WebContext(
        session, WebState(startup_notices=list(session.startup_notices))
    )
    app.register_blueprint(bp)
    app.context_processor(_template_globals)
    return app


# 메뉴 막대의 항목: (이름, 엔드포인트, 이 항목을 켜 둘 화면들)
NAV_ITEMS = (
    ("홈", "main.home", {"main.home"}),
    ("일차", "main.days", {"main.days", "main.day_detail", "main.cards"}),
    ("오답 학습", "main.wrong_list", {"main.wrong_list"}),
    ("단어 목록", "main.wordbook", {"main.wordbook", "main.import_wordbook"}),
)


def _nav_endpoint() -> str | None:
    """메뉴에서 켤 항목을 고를 때 쓰는 엔드포인트. 오답 카드 학습은 '오답 학습'에 속한다."""
    endpoint = request.endpoint
    if endpoint == "main.cards":
        study = _state().cards
        if study is not None and study.mode is CardMode.WRONG:
            return "main.wrong_list"
    return endpoint


def _template_globals() -> dict:
    """모든 템플릿이 쓰는 값. 메뉴 막대의 오답 수는 화면마다 세션에서 새로 읽는다."""
    return {
        "GRADUATE_STREAK": GRADUATE_STREAK,
        "DayStatus": DayStatus,
        "nav_items": NAV_ITEMS,
        "nav_endpoint": _nav_endpoint(),
        "nav_wrong_count": _session().summary().wrong_list_size,
    }


def _session() -> AppSession:
    return current_app.extensions[EXTENSION_KEY].session


def _state() -> WebState:
    return current_app.extensions[EXTENSION_KEY].state


def _save_error(error: OSError) -> None:
    """DL-04 저장 실패."""
    flash(f"학습 기록을 저장하지 못했습니다. ({error})", "error")


# ── 보안: 이 페이지에서 보낸 요청만 ─────────────────────────────
@bp.before_app_request
def _guard_request():
    """다른 웹사이트가 몰래 이 서버로 폼을 보내 기록을 지우는 일을 막는다.

    브라우저는 폼을 보낼 때 출처(Origin, 없으면 Referer)를 붙인다. 출처의 호스트가 이 서버가 아니면 거절한다.
    호스트만 비교하는 이유: 학교 서버에서는 앞단 프록시가 https 를 받고 앱에는 http 로 넘기므로
    주소 전체(http://… 와 https://…)를 비교하면 정상 요청도 막힌다 (ADR-30).
    2026-11-25 Host 허용 목록(127.0.0.1)은 없앴다. 서버 주소는 배포 환경이 정한다.
    출처가 없는 요청(브라우저가 아닌 테스트 클라이언트 등)은 통과시킨다.
    """
    if request.method == "POST":
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin is not None and urlsplit(origin).netloc != request.host:
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
    statuses = [(day.day_no, session.day_status(day.day_no)) for day in session.days]
    learned_words = sum(
        day.end - day.start
        for day, (_, status) in zip(session.days, statuses)
        if status is DayStatus.DONE
    )
    return render_template(
        "home.html",
        summary=summary,
        today=today,
        learned_words=learned_words,
        day_map=statuses,  # '일차 한눈에': 전체 일차를 작은 칸으로
        memorized_days=sum(status is DayStatus.MEMORIZED for _, status in statuses),
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
    """어느 일차든 학습할 수 있다 (ADR-21). 이미 끝낸 일차를 다시 보면 복습이다 — 기록은 바뀌지 않는다."""
    session = _session()
    if not _day_exists(day_no):
        flash(f"{day_no}일차는 없습니다.", "error")
        return redirect(url_for("main.days"))
    already_memorized = session.day_status(day_no) is not DayStatus.AVAILABLE
    study = CardStudy.start(
        CardMode.DAY, f"{day_no}일차 학습", session.day_words(day_no), day_no, already_memorized
    )
    return _open_cards(study)


def _day_exists(day_no: int) -> bool:
    return 1 <= day_no <= len(_session().days)


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
    if study.mode is CardMode.WRONG:
        back_url = url_for("main.wrong_list")
    else:
        back_url = url_for("main.day_detail", day_no=study.day_no)
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
    if study is None or not study.unlocked:
        return redirect(url_for("main.cards") if study else url_for("main.home"))
    if study.mode is CardMode.DAY:
        return _start_day_exam(study.day_no, url_for("main.cards"))
    return _start_wrong_exam(url_for("main.cards"))


# ── S-03 시험 응시 ──────────────────────────────────────────
@bp.post("/exam/day/<int:day_no>")
def exam_day(day_no: int):
    """일차 상세 화면의 '시험 보기' 버튼 (FR-13, FR-19)."""
    if not _day_exists(day_no):
        abort(404)
    return _start_day_exam(day_no, url_for("main.day_detail", day_no=day_no))


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
    # 잠금이 없으므로 '다음 일차'는 N+1 이 아니라 안 끝낸 가장 앞 일차(오늘의 학습 추천)다 (ADR-21)
    next_day = session.summary().current_day
    if is_retest:
        status = f"{day_no}일차 재시험"
    elif next_day is None:
        status = "모든 일차를 완료했습니다"
    else:
        status = f"{day_no}일차 완료 · 다음 추천은 {next_day}일차입니다"
    return ResultView(
        title=f"{day_no}일차 시험 결과",
        status=status,
        result=result,
        wrong_note="오답 목록에 추가되었습니다",
        next_day=next_day,
        day_no=day_no,
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


# ── S-05 일차 목록 · S-08 일차 상세 ─────────────────────────
# 거르기 탭: (쿼리 값, 이름, 남길 상태들). None 은 전체
DAY_FILTERS = (
    ("all", "전체", None),
    ("todo", "학습 전", {DayStatus.AVAILABLE}),
    ("memorized", "시험 남음", {DayStatus.MEMORIZED}),
    ("done", "완료", {DayStatus.DONE}),
)


@bp.get("/days")
def days():
    """전체 일차를 격자로 보여 준다. 골라서 상세로 들어간다 (ADR-22)."""
    session = _session()
    show = request.args.get("show", "all")
    wanted = dict((key, statuses) for key, _, statuses in DAY_FILTERS).get(show)
    if show not in {key for key, _, _ in DAY_FILTERS}:
        show = "all"
    cards, counts = [], {key: 0 for key, _, _ in DAY_FILTERS}
    current = session.summary().current_day
    for day in session.days:
        status = session.day_status(day.day_no)
        for key, _, statuses in DAY_FILTERS:
            if statuses is None or status in statuses:
                counts[key] += 1
        if wanted is not None and status not in wanted:
            continue
        words = session.words[day.start : day.end]
        cards.append(
            {
                "day_no": day.day_no,
                "first": words[0].word,
                "last": words[-1].word,
                "count": len(words),
                "status": status,
                "is_current": day.day_no == current,
            }
        )
    return render_template(
        "day_list.html", cards=cards, show=show, filters=DAY_FILTERS, counts=counts
    )


@bp.get("/days/<int:day_no>")
def day_detail(day_no: int):
    """한 일차의 단어를 먼저 훑어보고 학습·시험을 고른다."""
    session = _session()
    if not _day_exists(day_no):
        abort(404)
    status = session.day_status(day_no)
    wrong_words = {entry.word for entry in session.wrong_list()}
    return render_template(
        "day_detail.html",
        day_no=day_no,
        total_days=len(session.days),
        status=status,
        words=session.day_words(day_no),
        wrong_words=wrong_words,
        can_exam=status is not DayStatus.AVAILABLE,
        is_current=day_no == session.summary().current_day,
    )


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
