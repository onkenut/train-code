from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QLabel, QPushButton, QComboBox, QSpinBox, QListWidget,
    QListWidgetItem, QTabWidget, QGroupBox, QSplitter, QCheckBox,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ..db.models import Paper, Annotation
from ..services.library_service import get_library_service
from ..constants import READING_STATUS_LABELS, ANNOTATION_COLORS
from .workers import SummaryWorker, KeywordsWorker
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class DetailPanel(QWidget):
    paper_updated = Signal()
    annotation_clicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.library_service = get_library_service()
        self.current_paper: Paper | None = None
        self.summary_worker: SummaryWorker | None = None
        self.keywords_worker: KeywordsWorker | None = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.tabs = QTabWidget()

        metadata_tab = QWidget()
        self._init_metadata_tab(metadata_tab)
        self.tabs.addTab(metadata_tab, "元数据")

        ai_tab = QWidget()
        self._init_ai_tab(ai_tab)
        self.tabs.addTab(ai_tab, "AI 分析")

        annotations_tab = QWidget()
        self._init_annotations_tab(annotations_tab)
        self.tabs.addTab(annotations_tab, "标注")

        notes_tab = QWidget()
        self._init_notes_tab(notes_tab)
        self.tabs.addTab(notes_tab, "笔记")

        citations_tab = QWidget()
        self._init_citations_tab(citations_tab)
        self.tabs.addTab(citations_tab, "引用")

        layout.addWidget(self.tabs, 1)

    def _init_metadata_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)

        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.editingFinished.connect(self._on_metadata_changed)
        form.addRow("标题:", self.title_edit)

        self.authors_edit = QLineEdit()
        self.authors_edit.editingFinished.connect(self._on_metadata_changed)
        form.addRow("作者:", self.authors_edit)

        self.year_edit = QSpinBox()
        self.year_edit.setRange(1900, 2100)
        self.year_edit.setSpecialValueText(" ")
        self.year_edit.setValue(0)
        self.year_edit.editingFinished.connect(self._on_metadata_changed)
        form.addRow("年份:", self.year_edit)

        self.journal_edit = QLineEdit()
        self.journal_edit.editingFinished.connect(self._on_metadata_changed)
        form.addRow("期刊:", self.journal_edit)

        self.doi_edit = QLineEdit()
        self.doi_edit.editingFinished.connect(self._on_metadata_changed)
        form.addRow("DOI:", self.doi_edit)

        self.url_edit = QLineEdit()
        self.url_edit.editingFinished.connect(self._on_metadata_changed)
        form.addRow("URL:", self.url_edit)

        self.status_combo = QComboBox()
        for status, label in READING_STATUS_LABELS.items():
            self.status_combo.addItem(label, status)
        self.status_combo.currentIndexChanged.connect(self._on_metadata_changed)
        form.addRow("阅读状态:", self.status_combo)

        rating_layout = QHBoxLayout()
        self.rating_combo = QComboBox()
        self.rating_combo.addItems(["0 星", "1 星", "2 星", "3 星", "4 星", "5 星"])
        self.rating_combo.currentIndexChanged.connect(self._on_metadata_changed)
        rating_layout.addWidget(self.rating_combo)
        rating_layout.addStretch()
        form.addRow("评分:", rating_layout)

        layout.addLayout(form)

        self.file_path_label = QLabel()
        self.file_path_label.setStyleSheet("color: gray; font-size: 10px;")
        self.file_path_label.setWordWrap(True)
        layout.addWidget(self.file_path_label)

        layout.addSpacing(10)

        notes_group = QGroupBox("个人备注")
        notes_layout = QVBoxLayout(notes_group)
        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(100)
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group)

        layout.addStretch()

    def _init_ai_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)

        toolbar = QHBoxLayout()
        generate_btn = QPushButton("生成摘要")
        generate_btn.clicked.connect(self._on_generate_summary)
        toolbar.addWidget(generate_btn)

        refresh_btn = QPushButton("重新生成")
        refresh_btn.clicked.connect(lambda: self._on_generate_summary(force=True))
        toolbar.addWidget(refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        summary_group = QGroupBox("AI 摘要")
        summary_layout = QVBoxLayout(summary_group)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("点击上方按钮生成摘要...")
        summary_layout.addWidget(self.summary_text)
        layout.addWidget(summary_group, 1)

        keywords_group = QGroupBox("关键词")
        keywords_layout = QVBoxLayout(keywords_group)

        kw_toolbar = QHBoxLayout()
        kw_count_label = QLabel("数量:")
        kw_toolbar.addWidget(kw_count_label)
        self.kw_count_spin = QSpinBox()
        self.kw_count_spin.setRange(3, 20)
        self.kw_count_spin.setValue(10)
        kw_toolbar.addWidget(self.kw_count_spin)

        generate_kw_btn = QPushButton("提取关键词")
        generate_kw_btn.clicked.connect(self._on_generate_keywords)
        kw_toolbar.addWidget(generate_kw_btn)
        kw_toolbar.addStretch()
        keywords_layout.addLayout(kw_toolbar)

        self.keywords_list = QListWidget()
        keywords_layout.addWidget(self.keywords_list)
        layout.addWidget(keywords_group, 1)

    def _init_annotations_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)

        toolbar = QHBoxLayout()
        export_btn = QPushButton("导出 Markdown")
        export_btn.clicked.connect(self._on_export_annotations)
        toolbar.addWidget(export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.annotations_list = QListWidget()
        self.annotations_list.itemClicked.connect(self._on_annotation_clicked)
        layout.addWidget(self.annotations_list, 1)

    def _init_notes_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)

        toolbar = QHBoxLayout()
        add_note_btn = QPushButton("+ 新建笔记")
        add_note_btn.clicked.connect(self._on_add_note)
        toolbar.addWidget(add_note_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.notes_list = QListWidget()
        layout.addWidget(self.notes_list, 1)

    def _init_citations_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)

        toolbar = QHBoxLayout()
        discover_btn = QPushButton("发现引用关系")
        discover_btn.clicked.connect(self._on_discover_citations)
        toolbar.addWidget(discover_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        layout.addWidget(QLabel("引用的文献:"))
        self.citing_list = QListWidget()
        layout.addWidget(self.citing_list, 1)

        layout.addWidget(QLabel("被引文献:"))
        self.cited_by_list = QListWidget()
        layout.addWidget(self.cited_by_list, 1)

    def set_paper(self, paper: Paper | None):
        self.current_paper = paper
        if paper is None:
            self._clear_fields()
            return

        self._load_metadata(paper)
        self._load_ai_data(paper)
        self._load_annotations(paper)
        self._load_notes(paper)
        self._load_citations(paper)

    def _clear_fields(self):
        self.title_edit.clear()
        self.authors_edit.clear()
        self.year_edit.setValue(0)
        self.journal_edit.clear()
        self.doi_edit.clear()
        self.url_edit.clear()
        self.file_path_label.setText("")
        self.notes_edit.clear()
        self.summary_text.clear()
        self.keywords_list.clear()
        self.annotations_list.clear()
        self.notes_list.clear()
        self.citing_list.clear()
        self.cited_by_list.clear()

    def _load_metadata(self, paper: Paper):
        self.title_edit.blockSignals(True)
        self.title_edit.setText(paper.title or "")
        self.title_edit.blockSignals(False)

        self.authors_edit.blockSignals(True)
        self.authors_edit.setText(paper.authors or "")
        self.authors_edit.blockSignals(False)

        self.year_edit.blockSignals(True)
        self.year_edit.setValue(paper.year or 0)
        self.year_edit.blockSignals(False)

        self.journal_edit.blockSignals(True)
        self.journal_edit.setText(paper.journal or "")
        self.journal_edit.blockSignals(False)

        self.doi_edit.blockSignals(True)
        self.doi_edit.setText(paper.doi or "")
        self.doi_edit.blockSignals(False)

        self.url_edit.blockSignals(True)
        self.url_edit.setText(paper.url or "")
        self.url_edit.blockSignals(False)

        self.status_combo.blockSignals(True)
        idx = self.status_combo.findData(paper.reading_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.status_combo.blockSignals(False)

        self.rating_combo.blockSignals(True)
        self.rating_combo.setCurrentIndex(paper.rating or 0)
        self.rating_combo.blockSignals(False)

        self.file_path_label.setText(f"文件: {paper.file_path}")

        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(paper.notes or "")
        self.notes_edit.blockSignals(False)

    def _load_ai_data(self, paper: Paper):
        if paper.summary:
            self.summary_text.setPlainText(paper.summary)
        else:
            self.summary_text.setPlaceholderText("点击上方按钮生成摘要...")

        self.keywords_list.clear()
        if paper.keywords:
            keywords = paper.keywords.split(",")
            for kw in keywords:
                if kw.strip():
                    item = QListWidgetItem(kw.strip())
                    self.keywords_list.addItem(item)

    def _load_annotations(self, paper: Paper):
        self.annotations_list.clear()
        if paper.id is None:
            return

        annotations = self.library_service.get_annotations(paper.id)
        for ann in annotations:
            type_label = {
                "highlight": "高亮",
                "underline": "下划线",
                "strikethrough": "删除线",
                "text_box": "文本框",
            }.get(ann.annotation_type, ann.annotation_type)

            text = f"第 {ann.page + 1} 页 [{type_label}]"
            if ann.content:
                text += f": {ann.content[:50]}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, ann)
            self.annotations_list.addItem(item)

    def _load_notes(self, paper: Paper):
        self.notes_list.clear()
        if paper.id is None:
            return

        notes = self.library_service.note_repo.get_by_paper(paper.id)
        for note in notes:
            item = QListWidgetItem(note.title)
            item.setData(Qt.UserRole, note.id)
            self.notes_list.addItem(item)

    def _load_citations(self, paper: Paper):
        self.citing_list.clear()
        self.cited_by_list.clear()
        if paper.id is None:
            return

        from ..db.repositories import CitationRepository
        citation_repo = CitationRepository()

        citing = citation_repo.get_citations_by_paper(paper.id)
        for c in citing:
            target = self.library_service.get_paper(c.target_paper_id)
            if target:
                item = QListWidgetItem(target.title or "(无标题)")
                item.setData(Qt.UserRole, target.id)
                self.citing_list.addItem(item)

        cited_by = citation_repo.get_cited_by(paper.id)
        for c in cited_by:
            source = self.library_service.get_paper(c.source_paper_id)
            if source:
                item = QListWidgetItem(source.title or "(无标题)")
                item.setData(Qt.UserRole, source.id)
                self.cited_by_list.addItem(item)

    def _on_metadata_changed(self):
        if self.current_paper is None or self.current_paper.id is None:
            return

        self.current_paper.title = self.title_edit.text()
        self.current_paper.authors = self.authors_edit.text()
        year_val = self.year_edit.value()
        self.current_paper.year = year_val if year_val > 0 else None
        self.current_paper.journal = self.journal_edit.text()
        self.current_paper.doi = self.doi_edit.text()
        self.current_paper.url = self.url_edit.text()
        self.current_paper.reading_status = self.status_combo.currentData()
        self.current_paper.rating = self.rating_combo.currentIndex()

        self.library_service.update_paper(self.current_paper)
        self.paper_updated.emit()

    def _on_notes_changed(self):
        if self.current_paper is None or self.current_paper.id is None:
            return

        self.current_paper.notes = self.notes_edit.toPlainText()
        self.library_service.update_paper(self.current_paper)

    def _on_generate_summary(self, force: bool = False):
        if self.current_paper is None or self.current_paper.id is None:
            return

        self.summary_text.setPlaceholderText("正在生成摘要...")

        self.summary_worker = SummaryWorker(self.current_paper.id, force=force)
        self.summary_worker.finished_summary.connect(self._on_summary_finished)
        self.summary_worker.error.connect(self._on_worker_error)
        self.summary_worker.start()

    def _on_summary_finished(self, paper_id: int, summary: str):
        if self.current_paper and self.current_paper.id == paper_id:
            if summary:
                self.summary_text.setPlainText(summary)
                self.current_paper.summary = summary
            else:
                self.summary_text.setPlaceholderText("无法生成摘要")

    def _on_generate_keywords(self):
        if self.current_paper is None or self.current_paper.id is None:
            return

        self.keywords_list.clear()
        self.keywords_list.addItem("正在提取关键词...")

        self.keywords_worker = KeywordsWorker(self.current_paper.id, force=True)
        self.keywords_worker.finished_keywords.connect(self._on_keywords_finished)
        self.keywords_worker.error.connect(self._on_worker_error)
        self.keywords_worker.start()

    def _on_keywords_finished(self, paper_id: int, keywords: list):
        if self.current_paper and self.current_paper.id == paper_id:
            self.keywords_list.clear()
            for kw in keywords:
                item = QListWidgetItem(kw)
                self.keywords_list.addItem(item)

            if keywords:
                self.current_paper.keywords = ",".join(keywords)

    def _on_worker_error(self, error: str):
        logger.error(f"AI worker error: {error}")

    def _on_annotation_clicked(self, item: QListWidgetItem):
        ann: Annotation = item.data(Qt.UserRole)
        if ann:
            self.annotation_clicked.emit(ann.id, ann.page)

    def _on_export_annotations(self):
        if self.current_paper is None or self.current_paper.id is None:
            return

        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出标注", "annotations.md", "Markdown (*.md)"
        )
        if file_path:
            content = self.library_service.export_annotations_markdown(self.current_paper.id)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _on_add_note(self):
        from PySide6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(self, "新建笔记", "笔记标题:")
        if ok and title and self.current_paper and self.current_paper.id:
            from ..db.models import Note
            note = Note(title=title)
            note = self.library_service.note_repo.create(note)
            self.library_service.note_repo.link_paper(note.id, self.current_paper.id)
            self._load_notes(self.current_paper)

    def _on_discover_citations(self):
        if self.current_paper is None or self.current_paper.id is None:
            return

        from ..services.ai_service import get_ai_service
        ai_service = get_ai_service()
        count = ai_service.discover_citations(self.current_paper.id)
        self._load_citations(self.current_paper)

        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "引用发现", f"发现 {count} 条引用关系")

    def refresh_annotations(self):
        if self.current_paper:
            self._load_annotations(self.current_paper)
