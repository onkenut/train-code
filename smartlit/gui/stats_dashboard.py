from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QGroupBox
)
from PySide6.QtCore import Qt
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import platform
import os


def _setup_chinese_font():
    system = platform.system()
    if system == "Windows":
        font_candidates = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi", "FangSong"]
    elif system == "Darwin":
        font_candidates = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"]
    else:
        font_candidates = ["WenQuanYi Micro Hei", "Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei"]

    for font in font_candidates:
        try:
            matplotlib.rcParams["font.sans-serif"] = [font] + matplotlib.rcParams["font.sans-serif"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue


_setup_chinese_font()

from ..services.library_service import get_library_service
from ..constants import READING_STATUS_LABELS


class StatsDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.library_service = get_library_service()
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("<h2>文献统计仪表盘</h2>")
        layout.addWidget(title)

        stats_row = QHBoxLayout()

        total_box, self.total_value_label = self._create_stat_box("总文献数", "0")
        stats_row.addWidget(total_box)

        unread_box, self.unread_value_label = self._create_stat_box("未读", "0")
        stats_row.addWidget(unread_box)

        read_box, self.read_value_label = self._create_stat_box("已读", "0")
        stats_row.addWidget(read_box)

        deep_box, self.deep_read_value_label = self._create_stat_box("精读", "0")
        stats_row.addWidget(deep_box)

        layout.addLayout(stats_row)

        charts_row = QHBoxLayout()

        tag_group = QGroupBox("标签分布")
        tag_layout = QVBoxLayout(tag_group)
        self.tag_canvas = FigureCanvas(Figure(figsize=(4, 3)))
        tag_layout.addWidget(self.tag_canvas)
        charts_row.addWidget(tag_group)

        year_group = QGroupBox("年度发表分布")
        year_layout = QVBoxLayout(year_group)
        self.year_canvas = FigureCanvas(Figure(figsize=(4, 3)))
        year_layout.addWidget(self.year_canvas)
        charts_row.addWidget(year_group)

        layout.addLayout(charts_row, 1)

        status_group = QGroupBox("阅读状态分布")
        status_layout = QVBoxLayout(status_group)
        self.status_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        status_layout.addWidget(self.status_canvas)
        layout.addWidget(status_group)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignRight)

    def _create_stat_box(self, label: str, value: str) -> tuple[QGroupBox, QLabel]:
        box = QGroupBox(label)
        box_layout = QVBoxLayout(box)
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        value_label.setAlignment(Qt.AlignCenter)
        box_layout.addWidget(value_label)
        return box, value_label

    def refresh(self):
        stats = self.library_service.get_statistics()

        self.total_value_label.setText(str(stats["total"]))

        status_dist = stats.get("status_distribution", {})
        self.unread_value_label.setText(str(status_dist.get("unread", 0)))
        self.read_value_label.setText(str(status_dist.get("read", 0)))
        self.deep_read_value_label.setText(str(status_dist.get("deep_read", 0)))

        self._plot_tag_distribution(stats.get("tag_distribution", {}))
        self._plot_year_distribution(stats.get("year_distribution", {}))
        self._plot_status_distribution(status_dist)

    def _plot_tag_distribution(self, tag_dist: dict):
        fig = self.tag_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if tag_dist:
            tags = list(tag_dist.keys())[:10]
            counts = list(tag_dist.values())[:10]
            ax.pie(counts, labels=tags, autopct="%1.0f%%", startangle=90)
            ax.set_title("")
        else:
            ax.text(0.5, 0.5, "暂无标签数据", ha="center", va="center",
                   transform=ax.transAxes)
            ax.axis("off")

        fig.tight_layout()
        self.tag_canvas.draw()

    def _plot_year_distribution(self, year_dist: dict):
        fig = self.year_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if year_dist:
            years = sorted(year_dist.keys())
            counts = [year_dist[y] for y in years]
            ax.bar(years, counts, color="#4CAF50")
            ax.set_xlabel("年份")
            ax.set_ylabel("文献数")
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.text(0.5, 0.5, "暂无年份数据", ha="center", va="center",
                   transform=ax.transAxes)
            ax.axis("off")

        fig.tight_layout()
        self.year_canvas.draw()

    def _plot_status_distribution(self, status_dist: dict):
        fig = self.status_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if status_dist:
            labels = []
            values = []
            colors = ["#9E9E9E", "#2196F3", "#4CAF50"]

            for i, (status, count) in enumerate(status_dist.items()):
                label = READING_STATUS_LABELS.get(status, status)
                labels.append(label)
                values.append(count)

            ax.bar(labels, values, color=colors[:len(labels)])
            ax.set_ylabel("文献数")
            for i, v in enumerate(values):
                ax.text(i, v, str(v), ha="center", va="bottom")
        else:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                   transform=ax.transAxes)
            ax.axis("off")

        fig.tight_layout()
        self.status_canvas.draw()
