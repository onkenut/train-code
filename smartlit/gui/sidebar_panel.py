from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QComboBox, QSpinBox, QCheckBox, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ..services.library_service import get_library_service
from ..db.models import Tag
from ..constants import READING_STATUS_LABELS, DEFAULT_TAG_COLORS
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class SidebarPanel(QWidget):
    search_text_changed = Signal(str)
    semantic_search_triggered = Signal(str)
    tag_filter_changed = Signal(list)
    reading_status_filter_changed = Signal(str)
    tag_logic_changed = Signal(str)
    stats_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.library_service = get_library_service()
        self.selected_tag_ids: list[int] = []

        self._init_ui()
        self._load_tags()
        self._update_stats()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        search_group = QGroupBox("搜索")
        search_layout = QVBoxLayout(search_group)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("全文搜索...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        self.semantic_search_input = QLineEdit()
        self.semantic_search_input.setPlaceholderText("语义搜索...")
        self.semantic_search_input.returnPressed.connect(self._on_semantic_search)
        search_layout.addWidget(self.semantic_search_input)

        semantic_btn = QPushButton("语义搜索")
        semantic_btn.clicked.connect(self._on_semantic_search)
        search_layout.addWidget(semantic_btn)

        layout.addWidget(search_group)

        filter_group = QGroupBox("筛选")
        filter_layout = QVBoxLayout(filter_group)

        status_label = QLabel("阅读状态:")
        filter_layout.addWidget(status_label)

        self.status_combo = QComboBox()
        self.status_combo.addItem("全部", "")
        for status, label in READING_STATUS_LABELS.items():
            self.status_combo.addItem(label, status)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        filter_layout.addWidget(self.status_combo)

        year_layout = QHBoxLayout()
        year_layout.addWidget(QLabel("年份:"))
        self.year_min = QSpinBox()
        self.year_min.setRange(1900, 2100)
        self.year_min.setValue(1990)
        year_layout.addWidget(self.year_min)
        year_layout.addWidget(QLabel("-"))
        self.year_max = QSpinBox()
        self.year_max.setRange(1900, 2100)
        self.year_max.setValue(2030)
        year_layout.addWidget(self.year_max)
        filter_layout.addLayout(year_layout)

        rating_layout = QHBoxLayout()
        rating_layout.addWidget(QLabel("最低评分:"))
        self.rating_spin = QSpinBox()
        self.rating_spin.setRange(0, 5)
        self.rating_spin.setValue(0)
        rating_layout.addWidget(self.rating_spin)
        filter_layout.addLayout(rating_layout)

        layout.addWidget(filter_group)

        tag_group = QGroupBox("标签")
        tag_layout = QVBoxLayout(tag_group)

        logic_layout = QHBoxLayout()
        logic_layout.addWidget(QLabel("逻辑:"))
        self.tag_logic_combo = QComboBox()
        self.tag_logic_combo.addItems(["AND", "OR"])
        self.tag_logic_combo.currentTextChanged.connect(self._on_tag_logic_changed)
        logic_layout.addWidget(self.tag_logic_combo)
        tag_layout.addLayout(logic_layout)

        self.tag_list = QListWidget()
        self.tag_list.setSelectionMode(QListWidget.MultiSelection)
        self.tag_list.itemSelectionChanged.connect(self._on_tag_selection_changed)
        tag_layout.addWidget(self.tag_list)

        add_tag_layout = QHBoxLayout()
        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("新标签名")
        add_tag_layout.addWidget(self.new_tag_input)
        add_tag_btn = QPushButton("+")
        add_tag_btn.clicked.connect(self._on_add_tag)
        add_tag_layout.addWidget(add_tag_btn)
        tag_layout.addLayout(add_tag_layout)

        layout.addWidget(tag_group)

        stats_group = QGroupBox("统计概览")
        stats_layout = QVBoxLayout(stats_group)

        self.total_label = QLabel("总文献: 0")
        stats_layout.addWidget(self.total_label)

        self.unread_label = QLabel("未读: 0")
        stats_layout.addWidget(self.unread_label)

        stats_btn = QPushButton("查看仪表盘")
        stats_btn.clicked.connect(self.stats_clicked.emit)
        stats_layout.addWidget(stats_btn)

        layout.addWidget(stats_group)

        layout.addStretch()

    def _load_tags(self):
        self.tag_list.clear()
        tags = self.library_service.get_tags()
        for tag in tags:
            item = QListWidgetItem(tag.name)
            item.setData(Qt.UserRole, tag.id)
            if tag.color:
                item.setForeground(QColor(tag.color))
            self.tag_list.addItem(item)

    def _update_stats(self):
        stats = self.library_service.get_statistics()
        self.total_label.setText(f"总文献: {stats['total']}")

        status_dist = stats.get("status_distribution", {})
        unread = status_dist.get("unread", 0)
        self.unread_label.setText(f"未读: {unread}")

    def _on_search_changed(self, text: str):
        self.search_text_changed.emit(text)

    def _on_semantic_search(self):
        query = self.semantic_search_input.text().strip()
        if query:
            self.semantic_search_triggered.emit(query)

    def _on_status_changed(self, index: int):
        status = self.status_combo.currentData()
        self.reading_status_filter_changed.emit(status or "")

    def _on_tag_selection_changed(self):
        selected = self.tag_list.selectedItems()
        self.selected_tag_ids = [item.data(Qt.UserRole) for item in selected]
        self.tag_filter_changed.emit(self.selected_tag_ids)

    def _on_tag_logic_changed(self, logic: str):
        self.tag_logic_changed.emit(logic)

    def _on_add_tag(self):
        name = self.new_tag_input.text().strip()
        if not name:
            return

        color_idx = self.tag_list.count() % len(DEFAULT_TAG_COLORS)
        color = DEFAULT_TAG_COLORS[color_idx]

        try:
            tag = self.library_service.create_tag(name, color)
            self._load_tags()
            self.new_tag_input.clear()
        except Exception as e:
            logger.error(f"Failed to create tag: {e}")

    def refresh(self):
        self._load_tags()
        self._update_stats()

    def get_filter_params(self) -> dict:
        return {
            "tag_ids": self.selected_tag_ids or None,
            "tag_logic": self.tag_logic_combo.currentText(),
            "reading_status": self.status_combo.currentData() or None,
            "year_min": self.year_min.value(),
            "year_max": self.year_max.value(),
            "rating_min": self.rating_spin.value(),
        }
