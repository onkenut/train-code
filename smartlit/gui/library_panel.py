from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QLabel, QHBoxLayout, QPushButton,
    QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from ..db.models import Paper
from ..services.library_service import get_library_service
from ..constants import READING_STATUS_LABELS
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class LibraryPanel(QWidget):
    paper_selected = Signal(int)
    paper_double_clicked = Signal(int)
    papers_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.library_service = get_library_service()
        self.papers: list[Paper] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()

        add_btn = QPushButton("+ 添加文献")
        add_btn.clicked.connect(self._on_add_paper)
        toolbar.addWidget(add_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("排序:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["添加时间", "标题", "年份", "评分"])
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_combo)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["标题", "作者", "年份", "状态", "评分", "标签"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_clicked)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 60)
        self.table.setColumnWidth(5, 120)

        layout.addWidget(self.table, 1)

        self.status_bar = QLabel("共 0 篇文献")
        layout.addWidget(self.status_bar)

    def load_papers(self, papers: list[Paper] | None = None):
        if papers is None:
            papers = self.library_service.get_all_papers(limit=1000)

        self.papers = papers
        self.table.setRowCount(len(papers))

        for row, paper in enumerate(papers):
            title_item = QTableWidgetItem(paper.title or "(无标题)")
            title_item.setData(Qt.UserRole, paper.id)
            self.table.setItem(row, 0, title_item)

            authors_item = QTableWidgetItem(paper.authors or "")
            self.table.setItem(row, 1, authors_item)

            year_item = QTableWidgetItem(str(paper.year) if paper.year else "")
            year_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, year_item)

            status_label = READING_STATUS_LABELS.get(paper.reading_status, paper.reading_status)
            status_item = QTableWidgetItem(status_label)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, status_item)

            rating_str = "★" * paper.rating + "☆" * (5 - paper.rating)
            rating_item = QTableWidgetItem(rating_str)
            rating_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, rating_item)

            tags_str = ", ".join(paper.tags[:3])
            if len(paper.tags) > 3:
                tags_str += f" (+{len(paper.tags) - 3})"
            tags_item = QTableWidgetItem(tags_str)
            self.table.setItem(row, 5, tags_item)

        self.status_bar.setText(f"共 {len(papers)} 篇文献")

    def _on_selection_changed(self):
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self.papers):
            paper_id = self.papers[current_row].id
            if paper_id:
                self.paper_selected.emit(paper_id)

    def _on_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if row < len(self.papers):
            paper_id = self.papers[row].id
            if paper_id:
                self.paper_double_clicked.emit(paper_id)

    def _on_add_paper(self):
        pass

    def _on_sort_changed(self, index: int):
        sort_map = {
            0: ("added_at", "DESC"),
            1: ("title", "ASC"),
            2: ("year", "DESC"),
            3: ("rating", "DESC"),
        }
        sort_by, sort_order = sort_map.get(index, ("added_at", "DESC"))
        pass

    def _on_context_menu(self, pos):
        current_row = self.table.rowAt(pos.y())
        if current_row < 0 or current_row >= len(self.papers):
            return

        paper = self.papers[current_row]
        if not paper.id:
            return

        menu = QMenu(self)

        open_action = QAction("打开阅读", self)
        open_action.triggered.connect(lambda: self.paper_double_clicked.emit(paper.id))
        menu.addAction(open_action)

        menu.addSeparator()

        status_menu = menu.addMenu("阅读状态")
        for status, label in READING_STATUS_LABELS.items():
            action = QAction(label, self)
            action.triggered.connect(lambda s=status, pid=paper.id: self._update_status(pid, s))
            status_menu.addAction(action)

        rating_menu = menu.addMenu("评分")
        for i in range(0, 6):
            action = QAction(f"{i} 星", self)
            action.triggered.connect(lambda _, r=i, pid=paper.id: self._update_rating(pid, r))
            rating_menu.addAction(action)

        menu.addSeparator()

        archive_action = QAction(
            "取消归档" if paper.is_archived else "归档", self
        )
        archive_action.triggered.connect(lambda: self._toggle_archive(paper.id))
        menu.addAction(archive_action)

        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self._delete_paper(paper.id))
        menu.addAction(delete_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _update_status(self, paper_id: int, status: str):
        self.library_service.update_reading_status(paper_id, status)
        self.papers_updated.emit()

    def _update_rating(self, paper_id: int, rating: int):
        self.library_service.update_rating(paper_id, rating)
        self.papers_updated.emit()

    def _toggle_archive(self, paper_id: int):
        self.library_service.toggle_archive(paper_id)
        self.papers_updated.emit()

    def _delete_paper(self, paper_id: int):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这篇文献吗？\n选择 'Yes' 仅删除记录，\n选择 'Yes to All' 删除记录和文件。",
            QMessageBox.Yes | QMessageBox.YesToAll | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.library_service.delete_paper(paper_id, delete_file=False)
            self.papers_updated.emit()
        elif reply == QMessageBox.YesToAll:
            self.library_service.delete_paper(paper_id, delete_file=True)
            self.papers_updated.emit()

    def get_selected_paper_id(self) -> int | None:
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self.papers):
            return self.papers[current_row].id
        return None

    def refresh(self):
        self.papers_updated.emit()
