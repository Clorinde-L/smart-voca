#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-18 - smart-voca - 창을 띄우지 않고 7개 화면을 차례로 열어 스크린샷을 남긴다 (UI 개선 전후 비교용)
# 파일 위치: ai-agent/claude/261118_UI개선/script/capture_screens.py
#
# 사용법: QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts \
#         .venv/Scripts/python ai-agent/claude/261118_UI개선/script/capture_screens.py <출력 폴더> [폭 높이]
# 학습 기록은 임시 폴더에 만들어 실제 userdata/ 를 건드리지 않는다.
import random
import sys
import tempfile
from pathlib import Path

from smartvoca import paths
from smartvoca.session import AppSession
from smartvoca.ui import dialogs
from smartvoca.ui.app import create_application
from smartvoca.ui.main_window import MainWindow

out_dir = Path(sys.argv[1])
out_dir.mkdir(parents=True, exist_ok=True)
width, height = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (960, 700)

dialogs.confirm_abort_exam = lambda parent: True
app = create_application([])
session = AppSession.open(Path(tempfile.mkdtemp()) / "userdata", paths.default_wordbook_path(), rng=random.Random(7))
window = MainWindow(session)
window.resize(width, height)
window.show()


def shot(name):
    app.processEvents()
    window.grab().save(str(out_dir / f"{name}.png"))


# 기록을 조금 만들어 둔다: 1·2일차 완료(몇 개 틀림), 3일차 암기 완료
for day_no in (1, 2):
    session.complete_memorize(day_no)
    exam = session.build_day_exam(day_no)
    answers = [q.answer_index if i % 6 else (q.answer_index + 1) % 4 for i, q in enumerate(exam.questions)]
    session.submit_day_exam(day_no, exam, answers)
window.show_home(); shot("01_home")

window.open_day_cards(3); window.card_page.go_next(); shot("02_card")
window.card_page.hide_check.setChecked(True) if hasattr(window.card_page, "hide_check") else None; shot("02b_card_hidden")

session.complete_memorize(3)
window.start_day_exam(3)
window.exam_page.choose(1); window.exam_page.go_next(); shot("03_exam")

exam = window._exam
answers = [q.answer_index if i % 5 else (q.answer_index + 1) % 4 for i, q in enumerate(exam.questions)]
window._on_exam_submitted(answers); shot("04_result")

window.show_day_list(); shot("05_day_list")
window.show_wrong_list(); shot("06_wrong_list")
window.show_wordbook(); shot("07_wordbook")
print("saved", out_dir)
if hasattr(window.wordbook_page, "search_edit"):
    window.wordbook_page.search_edit.setText("account"); shot("07b_wordbook_search")
    window.wordbook_page.search_edit.setText("12"); shot("07c_wordbook_day")
