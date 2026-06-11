from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QPushButton, QSlider, QSpinBox, QComboBox, QToolBar,
    QStatusBar, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QMouseEvent

from ..services.pdf_service import get_pdf_service
from ..db.models import Annotation
from ..services.library_service import get_library_service
from ..constants import AnnotationType, ANNOTATION_COLORS
from .workers import PDFRenderWorker
from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class PDFViewer(QWidget):
    page_changed = Signal(int)
    annotation_added = Signal(Annotation)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pdf_service = get_pdf_service()
        self.library_service = get_library_service()

        self.file_path = ""
        self.current_page = 0
        self.total_pages = 0
        self.scale = 2.0
        self.paper_id: int | None = None
        self.annotations: list[Annotation] = []
        self.render_workers: list[PDFRenderWorker] = []

        self.annotation_mode: str | None = None
        self.annotation_color = ANNOTATION_COLORS[0]
        self.selection_start: QPoint | None = None
        self.selection_end: QPoint | None = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar("阅读工具栏")
        toolbar.setMovable(False)

        prev_btn = QPushButton("◀ 上一页")
        prev_btn.clicked.connect(self.prev_page)
        toolbar.addWidget(prev_btn)

        toolbar.addWidget(QLabel(" 第 "))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        toolbar.addWidget(self.page_spin)

        toolbar.addWidget(QLabel(" / "))
        self.total_pages_label = QLabel("0")
        toolbar.addWidget(self.total_pages_label)
        toolbar.addWidget(QLabel(" 页 "))

        next_btn = QPushButton("下一页 ▶")
        next_btn.clicked.connect(self.next_page)
        toolbar.addWidget(next_btn)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" 缩放: "))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "300%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        toolbar.addWidget(self.zoom_combo)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" 标注: "))
        self.highlight_btn = QPushButton("高亮")
        self.highlight_btn.setCheckable(True)
        self.highlight_btn.clicked.connect(lambda: self._set_annotation_mode("highlight"))
        toolbar.addWidget(self.highlight_btn)

        self.underline_btn = QPushButton("下划线")
        self.underline_btn.setCheckable(True)
        self.underline_btn.clicked.connect(lambda: self._set_annotation_mode("underline"))
        toolbar.addWidget(self.underline_btn)

        self.textbox_btn = QPushButton("文本框")
        self.textbox_btn.setCheckable(True)
        self.textbox_btn.clicked.connect(lambda: self._set_annotation_mode("text_box"))
        toolbar.addWidget(self.textbox_btn)

        self.color_combo = QComboBox()
        for color in ANNOTATION_COLORS:
            self.color_combo.addItem(color)
            self.color_combo.setItemData(self.color_combo.count() - 1, color, Qt.BackgroundRole)
        self.color_combo.setFixedWidth(60)
        self.color_combo.currentTextChanged.connect(self._on_color_changed)
        toolbar.addWidget(self.color_combo)

        layout.addWidget(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.page_label = PDFPageLabel()
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("background-color: #f0f0f0;")
        self.page_label.selection_made.connect(self._on_selection_made)

        self.scroll_area.setWidget(self.page_label)
        layout.addWidget(self.scroll_area, 1)

    def load_pdf(self, file_path: str, paper_id: int | None = None):
        self.file_path = file_path
        self.paper_id = paper_id

        try:
            self.total_pages = self.pdf_service.get_page_count(file_path)
            self.page_spin.setMaximum(self.total_pages)
            self.total_pages_label.setText(str(self.total_pages))

            self.current_page = 0
            self._render_page()

            if paper_id is not None:
                self.annotations = self.library_service.get_annotations(paper_id)

            if paper_id is not None:
                self.library_service.update_last_read(paper_id)

        except Exception as e:
            logger.error(f"Failed to load PDF: {e}")
            self.page_label.setText(f"无法加载 PDF: {e}")

    def _render_page(self):
        if not self.file_path:
            return

        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)

        worker = PDFRenderWorker(self.file_path, self.current_page, self.scale)
        worker.finished_render.connect(self._on_render_finished)
        worker.error.connect(self._on_render_error)
        self.render_workers.append(worker)
        worker.start()

        self.page_label.setText("加载中...")

    def _on_render_finished(self, page_num: int, image_bytes: bytes):
        if page_num != self.current_page:
            return

        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        self.page_label.setPixmap(pixmap)
        self.page_label.setFixedSize(pixmap.size())

        self.page_label.set_annotations(
            [a for a in self.annotations if a.page == self.current_page]
        )

    def _on_render_error(self, error: str):
        self.page_label.setText(f"渲染错误: {error}")

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()
            self.page_changed.emit(self.current_page)

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._render_page()
            self.page_changed.emit(self.current_page)

    def go_to_page(self, page_num: int):
        if 0 <= page_num < self.total_pages:
            self.current_page = page_num
            self._render_page()
            self.page_changed.emit(self.current_page)

    def _on_page_spin_changed(self, value: int):
        self.go_to_page(value - 1)

    def _on_zoom_changed(self, text: str):
        percent = int(text.rstrip("%"))
        self.scale = percent / 100.0 * 2.0
        self._render_page()

    def _on_color_changed(self, color: str):
        self.annotation_color = color

    def _set_annotation_mode(self, mode: str):
        if self.annotation_mode == mode:
            self.annotation_mode = None
            self.highlight_btn.setChecked(False)
            self.underline_btn.setChecked(False)
            self.textbox_btn.setChecked(False)
            self.page_label.set_selection_mode(False)
        else:
            self.annotation_mode = mode
            self.highlight_btn.setChecked(mode == "highlight")
            self.underline_btn.setChecked(mode == "underline")
            self.textbox_btn.setChecked(mode == "text_box")
            self.page_label.set_selection_mode(True)

    def _on_selection_made(self, rect: QRectF):
        if not self.annotation_mode or self.paper_id is None:
            return

        import json
        rect_data = {
            "x": rect.x(),
            "y": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        }

        annotation = Annotation(
            paper_id=self.paper_id,
            page=self.current_page,
            annotation_type=self.annotation_mode,
            color=self.annotation_color,
            rects=json.dumps([rect_data]),
            content="",
        )

        annotation = self.library_service.add_annotation(annotation)
        self.annotations.append(annotation)
        self.page_label.set_annotations(
            [a for a in self.annotations if a.page == self.current_page]
        )
        self.annotation_added.emit(annotation)

    def refresh_annotations(self):
        if self.paper_id is not None:
            self.annotations = self.library_service.get_annotations(self.paper_id)
            self.page_label.set_annotations(
                [a for a in self.annotations if a.page == self.current_page]
            )


class PDFPageLabel(QLabel):
    selection_made = Signal(QRectF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._selection_mode = False
        self._selecting = False
        self._selection_start = QPoint()
        self._selection_end = QPoint()
        self._annotations: list[Annotation] = []

    def set_selection_mode(self, enabled: bool):
        self._selection_mode = enabled
        if enabled:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def set_annotations(self, annotations: list[Annotation]):
        self._annotations = annotations
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if self._selection_mode and event.button() == Qt.LeftButton:
            self._selecting = True
            self._selection_start = event.position().toPoint()
            self._selection_end = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._selecting:
            self._selection_end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._selecting and event.button() == Qt.LeftButton:
            self._selecting = False
            rect = QRectF(self._selection_start, self._selection_end).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.selection_made.emit(rect)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)

        import json
        for ann in self._annotations:
            try:
                rects = json.loads(ann.rects or "[]")
                color = QColor(ann.color)

                if ann.annotation_type == "highlight":
                    color.setAlpha(80)
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.NoPen)
                    for r in rects:
                        painter.drawRect(QRectF(r["x"], r["y"], r["width"], r["height"]))
                elif ann.annotation_type == "underline":
                    color.setAlpha(200)
                    pen = QPen(color, 2)
                    painter.setPen(pen)
                    for r in rects:
                        painter.drawLine(
                            int(r["x"]), int(r["y"] + r["height"]),
                            int(r["x"] + r["width"]), int(r["y"] + r["height"])
                        )
                elif ann.annotation_type == "strikethrough":
                    color.setAlpha(200)
                    pen = QPen(color, 2)
                    painter.setPen(pen)
                    for r in rects:
                        mid_y = int(r["y"] + r["height"] / 2)
                        painter.drawLine(
                            int(r["x"]), mid_y,
                            int(r["x"] + r["width"]), mid_y
                        )
                elif ann.annotation_type == "text_box":
                    color.setAlpha(120)
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(QColor(ann.color), 2))
                    for r in rects:
                        painter.drawRect(QRectF(r["x"], r["y"], r["width"], r["height"]))
            except Exception:
                pass

        if self._selecting:
            rect = QRectF(self._selection_start, self._selection_end).normalized()
            painter.setBrush(QBrush(QColor(255, 235, 59, 80)))
            painter.setPen(QPen(QColor(255, 193, 7), 2, Qt.DashLine))
            painter.drawRect(rect)

        painter.end()
