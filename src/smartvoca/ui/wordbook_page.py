#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2026-11-11 - smart-voca - 단어 목록 화면 (S-07): 전체 단어 검색표, 단어장 불러오기·내보내기, 오답 목록 내보내기
# 파일 위치: src/smartvoca/ui/wordbook_page.py
"""단어장 전체를 표로 보여 주고 검색한다 (UD-06).

2,000개 넘는 행을 칸마다 위젯(QTableWidgetItem)으로 만들면 화면을 열 때마다 느려지므로,
표는 데이터 모델(WordTableModel) + 거르개(WordFilterProxy) + QTableView 로 만든다.
모델은 글자를 그릴 때만 꺼내 주므로 행 수가 많아도 가볍다.
"""
from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..core.models import DAY_SIZE, Word, WordbookSource
from ..session import AppSession
from .widgets import (
    PAGE_MARGIN,
    SPACING,
    KeyHints,
    PageHeader,
    add_shortcut,
    hint_label,
    make_button,
    set_font,
    text_label,
)

DAY_COLUMN, WORD_COLUMN, MEANING_COLUMN = range(3)


def day_of(word: Word) -> int:
    """단어가 속한 일차. 일차 편성(FR-07)과 같은 규칙이다."""
    return word.index // DAY_SIZE + 1


class WordTableModel(QAbstractTableModel):
    """일차 · 영단어 · 뜻 세 칸짜리 읽기 전용 표 데이터."""

    HEADERS = ("일차", "영단어", "뜻")

    def __init__(self):
        super().__init__()
        self._words: tuple[Word, ...] = ()

    def set_words(self, words: tuple[Word, ...]) -> None:
        self.beginResetModel()
        self._words = tuple(words)
        self.endResetModel()

    @property
    def words(self) -> tuple[Word, ...]:
        return self._words

    def word_at(self, row: int) -> Word:
        return self._words[row]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._words)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        word = self._words[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (f"{day_of(word)}일차", word.word, word.meaning)[column]
        if role == Qt.ItemDataRole.FontRole and column == WORD_COLUMN:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.ToolTipRole and column == MEANING_COLUMN:
            return word.meaning  # 칸이 좁아 뜻이 잘리면 마우스를 올려 전부 본다
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None


class WordFilterProxy(QSortFilterProxyModel):
    """검색어가 영단어나 뜻에 들어 있으면 남긴다. 숫자만 넣으면 그 일차의 단어를 보여 준다.

    대소문자는 가리지 않는다. 검색어 앞뒤 공백과 '일차' 글자는 무시한다 ('12일차' = '12').
    """

    def __init__(self):
        super().__init__()
        self._query = ""

    def set_query(self, text: str) -> None:
        self._query = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._query:
            return True
        word = self.sourceModel().word_at(source_row)
        day_query = self._query.removesuffix("일차").strip()
        if day_query.isdigit():
            return day_of(word) == int(day_query)
        return self._query in word.word.lower() or self._query in word.meaning.lower()


class WordbookPage(QWidget):
    """버튼을 누르면 시그널만 내보낸다. 파일 선택·확인·교체는 MainWindow 가 한다."""

    back_clicked = pyqtSignal()
    import_clicked = pyqtSignal()
    export_wordbook_clicked = pyqtSignal()
    export_wrong_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACING)
        self.header = PageHeader("단어 목록")
        self.header.back_clicked.connect(self.back_clicked)
        layout.addWidget(self.header)

        # 현재 단어장 + 파일 작업 버튼을 한 줄에 둔다. 자주 쓰지 않는 일이라 작게 둔다
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        self.current_label = text_label("", 13, bold=True)
        self.import_button = self._file_button("불러오기", "단어장 불러오기", self.import_clicked)
        self.export_wordbook_button = self._file_button(
            "단어장 내보내기", "단어장 내보내기", self.export_wordbook_clicked
        )
        self.export_wrong_button = self._file_button(
            "오답 내보내기", "오답 목록 내보내기", self.export_wrong_clicked
        )
        info_row.addWidget(self.current_label, 1)
        for button in (self.import_button, self.export_wordbook_button, self.export_wrong_button):
            info_row.addWidget(button)
        layout.addLayout(info_row)
        layout.addWidget(
            hint_label(
                "다른 단어장(CSV: word,meaning)을 불러오면 학습 기록이 모두 지워집니다. "
                "기본 단어장으로 되돌리려면 data/toeic_words.csv 를 불러오세요."
            )
        )

        search_row = QHBoxLayout()
        search_row.setSpacing(12)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("search")
        self.search_edit.setPlaceholderText("영단어나 뜻으로 검색  ·  숫자를 넣으면 그 일차의 단어")
        self.search_edit.setClearButtonEnabled(True)
        set_font(self.search_edit, 12)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.result_label = text_label("", 11, role="muted")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.result_label)
        layout.addLayout(search_row)

        self.model = WordTableModel()
        self.proxy = WordFilterProxy()
        self.proxy.setSourceModel(self.model)
        self.table = self._make_table()
        layout.addWidget(self.table, 1)

        self.empty_label = text_label("검색 결과가 없습니다", 12, role="muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label, 1)

        layout.addWidget(KeyHints([("Ctrl F", "검색"), ("Esc", "검색 지우기·뒤로")]))

        add_shortcut(self, "Ctrl+F", self._focus_search)
        add_shortcut(self, Qt.Key.Key_Escape, self._press_escape)

    def _file_button(self, text: str, accessible_name: str, signal):
        button = make_button(text)
        button.setMinimumHeight(36)
        button.setAccessibleName(accessible_name)
        button.clicked.connect(signal)
        return button

    def _make_table(self) -> QTableView:
        table = QTableView()
        table.setModel(self.proxy)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setFrameShape(QFrame.Shape.NoFrame)
        # 행 높이를 고정해 두면 2,000개 넘는 행의 높이를 하나하나 재지 않아도 된다
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.verticalHeader().setDefaultSectionSize(40)
        header = table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(DAY_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(WORD_COLUMN, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(MEANING_COLUMN, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(DAY_COLUMN, 84)
        table.setColumnWidth(WORD_COLUMN, 190)
        return table

    # ── 검색 ────────────────────────────────────────────────
    def _on_search_changed(self, text: str) -> None:
        self.proxy.set_query(text)
        self._update_result_count()
        self.table.scrollToTop()

    def _update_result_count(self) -> None:
        shown, total = self.proxy.rowCount(), self.model.rowCount()
        self.result_label.setText(f"{total:,}개" if shown == total else f"{shown:,} / {total:,}개")
        self.table.setVisible(shown > 0)
        self.empty_label.setVisible(shown == 0)

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _press_escape(self) -> None:
        # 검색어가 있으면 먼저 지우고, 없으면 메인으로 돌아간다
        if self.search_edit.text():
            self.search_edit.clear()
        else:
            self.back_clicked.emit()

    def visible_words(self) -> list[str]:
        """지금 표에 보이는 영단어 (검색 결과)."""
        return [
            self.proxy.data(self.proxy.index(row, WORD_COLUMN))
            for row in range(self.proxy.rowCount())
        ]

    # ── 갱신 ────────────────────────────────────────────────
    def refresh(self, session: AppSession) -> None:
        kind = (
            "기본 토익"
            if session.wordbook_source is WordbookSource.DEFAULT
            else "사용자 단어장"
        )
        self.current_label.setText(
            f"현재 단어장: {kind} {len(session.words):,} 단어 ({len(session.days)}일차)"
        )
        self.header.set_info(f"{len(session.words):,} 단어")
        # 단어장이 바뀌었을 때만 표를 다시 채운다 (화면을 열 때마다 2,000개를 다시 넣지 않도록)
        if tuple(session.words) != self.model.words:
            self.model.set_words(session.words)
            self.search_edit.clear()
        self._update_result_count()

        wrong_count = session.summary().wrong_list_size
        self.export_wrong_button.setEnabled(wrong_count > 0)
        self.export_wrong_button.setToolTip(
            f"오답 단어 {wrong_count}개를 CSV 파일로 저장합니다."
            if wrong_count
            else "내보낼 오답 단어가 없습니다."
        )
