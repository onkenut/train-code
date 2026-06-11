import os
import re
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QTextEdit, QLineEdit, QPushButton, QSplitter, QLabel, QMessageBox,
    QInputDialog, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction, QTextCursor

from ..db.repositories import NoteRepository, PaperRepository
from ..db.models import Note
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class NotePanel(QWidget):
    note_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.note_repo = NoteRepository()
        self.paper_repo = PaperRepository()
        self.current_note: Optional[Note] = None
        self._loading = False

        self._build_ui()
        self.refresh_notes()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索笔记...")
        self.search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_edit, 1)

        self.new_btn = QPushButton("新建")
        self.new_btn.clicked.connect(self._on_new_note)
        toolbar.addWidget(self.new_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self._on_delete_note)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Vertical)

        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)

        list_header = QLabel("笔记列表")
        list_header.setStyleSheet("font-weight: bold; padding: 4px;")
        list_layout.addWidget(list_header)

        self.note_list = QListWidget()
        self.note_list.itemSelectionChanged.connect(self._on_note_selected)
        self.note_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.note_list.customContextMenuRequested.connect(self._on_context_menu)
        list_layout.addWidget(self.note_list, 1)

        self.count_label = QLabel("0 条笔记")
        list_layout.addWidget(self.count_label)

        splitter.addWidget(list_container)

        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("标题:"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("笔记标题...")
        self.title_edit.editingFinished.connect(self._on_title_changed)
        title_row.addWidget(self.title_edit, 1)
        editor_layout.addLayout(title_row)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "在此输入笔记内容...\n\n"
            "支持 Markdown 语法：\n"
            "# 标题    **粗体**    *斜体*\n"
            "- 列表    `代码`    [链接](url)\n"
            "文献引用： [[paper:1]] 或 @DOI\n"
        )
        font = QFont("Consolas")
        font.setPointSize(10)
        self.editor.setFont(font)
        self.editor.textChanged.connect(self._on_text_changed)
        editor_layout.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()

        self.preview_btn = QPushButton("预览")
        self.preview_btn.setCheckable(True)
        self.preview_btn.clicked.connect(self._toggle_preview)
        btn_row.addWidget(self.preview_btn)

        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setEnabled(False)
        btn_row.addWidget(self.save_btn)

        self.undo_btn = QPushButton("撤销")
        self.undo_btn.clicked.connect(self.editor.undo)
        btn_row.addWidget(self.undo_btn)

        btn_row.addStretch()

        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: #888; font-size: 11px;")
        btn_row.addWidget(self.time_label)

        editor_layout.addLayout(btn_row)

        splitter.addWidget(editor_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([200, 400])

        layout.addWidget(splitter, 1)

    def refresh_notes(self, filter_text: str = ""):
        self._loading = True
        try:
            self.note_list.clear()

            notes = self.note_repo.get_all()
            if filter_text:
                ft = filter_text.lower()
                notes = [
                    n for n in notes
                    if ft in n.title.lower() or ft in n.content.lower()
                ]

            for note in notes:
                item = QListWidgetItem()
                title = note.title or "(无标题)"
                preview = note.content[:80].replace("\n", " ") if note.content else ""
                item.setText(f"{title}\n  {preview}")
                item.setData(Qt.UserRole, note.id)
                self.note_list.addItem(item)

            self.count_label.setText(f"{len(notes)} 条笔记")
        finally:
            self._loading = False

    def show_notes_for_paper(self, paper_id: int):
        self._loading = True
        try:
            self.note_list.clear()
            notes = self.note_repo.get_by_paper(paper_id)

            for note in notes:
                item = QListWidgetItem()
                title = note.title or "(无标题)"
                preview = note.content[:80].replace("\n", " ") if note.content else ""
                item.setText(f"{title}\n  {preview}")
                item.setData(Qt.UserRole, note.id)
                self.note_list.addItem(item)

            self.count_label.setText(f"{len(notes)} 条笔记（关联文献）")

            if notes:
                self.note_list.setCurrentRow(0)
        finally:
            self._loading = False

    def create_note_for_paper(self, paper_id: int, title: str = "", content: str = ""):
        note = Note(title=title, content=content)
        note = self.note_repo.create(note)
        self.note_repo.link_paper(note.id, paper_id)
        self.refresh_notes()
        self._select_note_by_id(note.id)
        self.note_updated.emit()
        return note

    def _on_search(self, text: str):
        self.refresh_notes(text)

    def _on_new_note(self):
        title, ok = QInputDialog.getText(self, "新建笔记", "笔记标题:")
        if ok:
            note = Note(title=title, content="")
            note = self.note_repo.create(note)
            self.refresh_notes()
            self._select_note_by_id(note.id)
            self.note_updated.emit()

    def _on_delete_note(self):
        if not self.current_note:
            return

        reply = QMessageBox.question(
            self, "删除笔记",
            f"确定要删除笔记「{self.current_note.title or '无标题'}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.note_repo.delete(self.current_note.id)
            self.current_note = None
            self._clear_editor()
            self.refresh_notes()
            self.note_updated.emit()

    def _on_note_selected(self):
        if self._loading:
            return

        items = self.note_list.selectedItems()
        if not items:
            self.current_note = None
            self._clear_editor()
            return

        note_id = items[0].data(Qt.UserRole)
        note = self.note_repo.get_by_id(note_id)
        if note:
            self.current_note = note
            self._loading = True
            try:
                self.title_edit.setText(note.title)
                self.editor.setPlainText(note.content)
                self._update_time_label(note)
                self._set_editor_enabled(True)
                self.delete_btn.setEnabled(True)
            finally:
                self._loading = False

    def _on_context_menu(self, pos):
        item = self.note_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(lambda: self._rename_note(item.data(Qt.UserRole)))
        menu.addAction(rename_action)

        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self._delete_note_by_id(item.data(Qt.UserRole)))
        menu.addAction(delete_action)

        menu.exec(self.note_list.mapToGlobal(pos))

    def _rename_note(self, note_id: int):
        note = self.note_repo.get_by_id(note_id)
        if not note:
            return

        title, ok = QInputDialog.getText(self, "重命名笔记", "新标题:", text=note.title)
        if ok and title:
            note.title = title
            self.note_repo.update(note)
            self.refresh_notes(self.search_edit.text())
            self._select_note_by_id(note_id)
            self.note_updated.emit()

    def _delete_note_by_id(self, note_id: int):
        reply = QMessageBox.question(self, "删除笔记", "确定要删除这条笔记吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.note_repo.delete(note_id)
            if self.current_note and self.current_note.id == note_id:
                self.current_note = None
                self._clear_editor()
            self.refresh_notes(self.search_edit.text())
            self.note_updated.emit()

    def _select_note_by_id(self, note_id: int):
        for i in range(self.note_list.count()):
            item = self.note_list.item(i)
            if item.data(Qt.UserRole) == note_id:
                self.note_list.setCurrentItem(item)
                break

    def _on_title_changed(self):
        if self._loading or not self.current_note:
            return
        self.current_note.title = self.title_edit.text().strip()
        self._mark_unsaved()

    def _on_text_changed(self):
        if self._loading or not self.current_note:
            return
        self._mark_unsaved()

    def _mark_unsaved(self):
        self.save_btn.setEnabled(True)
        if self.current_note and self.current_note.title:
            self.time_label.setText(
                f"{self.current_note.title} • 未保存"
            )
            self.time_label.setStyleSheet("color: #d33; font-size: 11px;")

    def _on_save(self):
        if not self.current_note:
            return

        self.current_note.title = self.title_edit.text().strip()
        self.current_note.content = self.editor.toPlainText()

        try:
            self.note_repo.update(self.current_note)
            self.save_btn.setEnabled(False)
            self._update_time_label(self.current_note)
            self.refresh_notes(self.search_edit.text())
            self._select_note_by_id(self.current_note.id)
            self.note_updated.emit()
        except Exception as e:
            logger.error(f"Failed to save note: {e}")
            QMessageBox.warning(self, "保存失败", str(e))

    def _toggle_preview(self):
        if self.preview_btn.isChecked():
            html = self._markdown_to_html(self.editor.toPlainText())
            self.editor.setHtml(html)
            self.editor.setReadOnly(True)
            self.undo_btn.setEnabled(False)
            self.preview_btn.setText("编辑")
        else:
            plain = self.editor.toPlainText()
            self.editor.setPlainText(plain)
            self.editor.setReadOnly(False)
            self.undo_btn.setEnabled(True)
            self.preview_btn.setText("预览")

    def _clear_editor(self):
        self.title_edit.clear()
        self.editor.clear()
        self.time_label.setText("")
        self._set_editor_enabled(False)
        self.delete_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

    def _set_editor_enabled(self, enabled: bool):
        self.title_edit.setEnabled(enabled)
        self.editor.setEnabled(enabled)
        self.preview_btn.setEnabled(enabled)
        self.save_btn.setEnabled(False)
        self.undo_btn.setEnabled(enabled)

    def _update_time_label(self, note: Note):
        parts = []
        if note.created_at:
            parts.append(f"创建: {self._fmt_time(note.created_at)}")
        if note.updated_at and note.updated_at != note.created_at:
            parts.append(f"修改: {self._fmt_time(note.updated_at)}")
        self.time_label.setText(" | ".join(parts))
        self.time_label.setStyleSheet("color: #888; font-size: 11px;")

    def _fmt_time(self, dt):
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except Exception:
                return dt
        if isinstance(dt, datetime):
            now = datetime.now()
            delta = now - dt
            if delta.days == 0:
                if delta.seconds < 60:
                    return "刚刚"
                if delta.seconds < 3600:
                    return f"{delta.seconds // 60} 分钟前"
                return f"{delta.seconds // 3600} 小时前"
            if delta.days < 7:
                return f"{delta.days} 天前"
            return dt.strftime("%Y-%m-%d")
        return str(dt)

    def _markdown_to_html(self, md: str) -> str:
        html = md

        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', html)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html)
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        html = re.sub(r'\n', '<br>', html)

        return f"""
        <html><head><style>
            body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; line-height: 1.7; padding: 8px; }}
            h1, h2, h3 {{ margin: 12px 0 6px; }}
            code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: Consolas, monospace; }}
            li {{ margin: 2px 0; }}
            a {{ color: #2563eb; }}
        </style></head><body>{html}</body></html>
        """
