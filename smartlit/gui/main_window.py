import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFileDialog, QMessageBox, QStatusBar, QToolBar, QLabel,
    QStackedWidget, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QAction, QIcon, QDragEnterEvent, QDropEvent

from ..services.library_service import get_library_service
from ..services.search_service import get_search_service
from ..services.ai_service import get_ai_service
from ..infrastructure.logger import get_logger, setup_logger
from ..config import get_config

from .sidebar_panel import SidebarPanel
from .library_panel import LibraryPanel
from .detail_panel import DetailPanel
from .pdf_viewer import PDFViewer
from .stats_dashboard import StatsDashboard
from .note_panel import NotePanel
from .dialogs import ProgressDialog, AboutDialog, SettingsDialog
from .workers import ImportWorker, AIWorker, SemanticSearchWorker
from .. import __app_name__, __version__

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library_service = get_library_service()
        self.search_service = get_search_service()
        self.ai_service = get_ai_service()
        self.config = get_config()

        self.current_paper_id: int | None = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

        self._workers = []
        self._progress_dialogs = []

        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_statusbar()
        self._setup_drag_drop()

        self.setAcceptDrops(True)

        self._refresh_library()

    def _init_ui(self):
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(1400, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(120)
        self.nav_list.addItem(QListWidgetItem("📚 文献库"))
        self.nav_list.addItem(QListWidgetItem("📊 仪表盘"))
        self.nav_list.addItem(QListWidgetItem("📝 笔记"))
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        self.stacked_widget = QStackedWidget()

        library_page = QWidget()
        library_layout = QHBoxLayout(library_page)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(0)

        self.sidebar = SidebarPanel()
        self.sidebar.search_text_changed.connect(self._on_search_text_changed)
        self.sidebar.semantic_search_triggered.connect(self._on_semantic_search)
        self.sidebar.tag_filter_changed.connect(self._on_filter_changed)
        self.sidebar.reading_status_filter_changed.connect(self._on_filter_changed)
        self.sidebar.tag_logic_changed.connect(self._on_filter_changed)
        self.sidebar.stats_clicked.connect(lambda: self.nav_list.setCurrentRow(1))

        self.library_panel = LibraryPanel()
        self.library_panel.paper_selected.connect(self._on_paper_selected)
        self.library_panel.paper_double_clicked.connect(self._on_paper_double_clicked)
        self.library_panel.papers_updated.connect(self._refresh_library)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.library_panel)

        self.detail_panel = DetailPanel()
        self.detail_panel.paper_updated.connect(self._refresh_library)
        self.detail_panel.annotation_clicked.connect(self._on_annotation_clicked)
        right_splitter.addWidget(self.detail_panel)
        right_splitter.setSizes([400, 500])

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([280, 900])

        library_layout.addWidget(main_splitter)
        self.stacked_widget.addWidget(library_page)

        dashboard_page = StatsDashboard()
        self.stacked_widget.addWidget(dashboard_page)

        notes_page = NotePanel()
        notes_page.note_updated.connect(self._refresh_library)
        self.stacked_widget.addWidget(notes_page)

        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.addWidget(self.nav_list)
        nav_layout.addWidget(self.stacked_widget, 1)

        main_layout.addLayout(nav_layout, 1)

        self.reader_window: PDFViewer | None = None

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")

        add_action = QAction("添加文献...", self)
        add_action.setShortcut("Ctrl+O")
        add_action.triggered.connect(self._on_add_papers)
        file_menu.addAction(add_action)

        add_folder_action = QAction("添加文件夹...", self)
        add_folder_action.triggered.connect(self._on_add_folder)
        file_menu.addAction(add_folder_action)

        file_menu.addSeparator()

        export_action = QAction("导出文献...", self)
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menubar.addMenu("工具(&T)")

        ai_process_action = QAction("AI 处理全部文献", self)
        ai_process_action.triggered.connect(self._on_ai_process_all)
        tools_menu.addAction(ai_process_action)

        tools_menu.addSeparator()

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self._on_settings)
        tools_menu.addAction(settings_action)

        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _init_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        add_action = QAction("添加文献", self)
        add_action.triggered.connect(self._on_add_papers)
        toolbar.addAction(add_action)

        toolbar.addSeparator()

        import_ai_action = QAction("导入并 AI 处理", self)
        import_ai_action.triggered.connect(self._on_import_and_ai)
        toolbar.addAction(import_ai_action)

        toolbar.addSeparator()

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh_library)
        toolbar.addAction(refresh_action)

    def _init_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    def _setup_drag_drop(self):
        pass

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        file_paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                file_paths.append(path)
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    for f in files:
                        if f.lower().endswith(".pdf"):
                            file_paths.append(os.path.join(root, f))

        if file_paths:
            self._import_files(file_paths)

    def _on_nav_changed(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        if index == 1:
            self.stacked_widget.widget(1).refresh()

    def _on_add_papers(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 PDF 文件", "", "PDF 文件 (*.pdf)"
        )
        if file_paths:
            self._import_files(file_paths)

    def _on_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            file_paths = []
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(".pdf"):
                        file_paths.append(os.path.join(root, f))
            if file_paths:
                self._import_files(file_paths)
            else:
                QMessageBox.information(self, "提示", "该文件夹中没有找到 PDF 文件")

    def _register_worker(self, worker, progress=None):
        self._workers.append(worker)
        if progress:
            self._progress_dialogs.append(progress)

    def _cleanup_worker(self, worker, progress=None):
        try:
            worker.wait(100)
        except Exception:
            pass
        if worker in self._workers:
            self._workers.remove(worker)
        if progress and progress in self._progress_dialogs:
            self._progress_dialogs.remove(progress)

    def _import_files(self, file_paths: list[str]):
        progress = ProgressDialog("导入文献", self)
        progress.show()

        worker = ImportWorker(file_paths)
        self._register_worker(worker, progress)

        worker.progress.connect(progress.update_progress)

        def _on_finished(papers):
            try:
                progress.accept()
                self._refresh_library()
                if papers:
                    QMessageBox.information(
                        self, "导入完成",
                        f"成功导入 {len(papers)} 篇文献"
                    )
            finally:
                self._cleanup_worker(worker, progress)

        def _on_error(error):
            try:
                progress.reject()
                QMessageBox.critical(self, "导入失败", f"导入过程中发生错误:\n{error}")
            finally:
                self._cleanup_worker(worker, progress)

        worker.finished_import.connect(_on_finished)
        worker.error.connect(_on_error)
        worker.start()

    def _on_import_finished(self, papers, progress):
        progress.accept()
        self._refresh_library()
        if papers:
            QMessageBox.information(
                self, "导入完成",
                f"成功导入 {len(papers)} 篇文献"
            )

    def _on_import_error(self, error: str, progress):
        progress.reject()
        QMessageBox.critical(self, "导入失败", f"导入过程中发生错误:\n{error}")

    def _on_import_and_ai(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 PDF 文件", "", "PDF 文件 (*.pdf)"
        )
        if file_paths:
            self._import_with_ai(file_paths)

    def _import_with_ai(self, file_paths: list[str]):
        progress = ProgressDialog("导入并 AI 处理", self)
        progress.show()

        state = {"import_worker": None, "ai_worker": None}

        def on_imported(papers):
            if not papers:
                try:
                    progress.accept()
                finally:
                    self._cleanup_worker(state["import_worker"], progress)
                return

            paper_ids = [p.id for p in papers if p.id]
            ai_worker = AIWorker(paper_ids)
            state["ai_worker"] = ai_worker
            self._register_worker(ai_worker)

            ai_worker.progress.connect(progress.update_progress)

            def _on_ai_done():
                try:
                    progress.accept()
                    self._refresh_library()
                    QMessageBox.information(self, "完成", "AI 处理完成")
                finally:
                    self._cleanup_worker(state["import_worker"], progress)
                    self._cleanup_worker(ai_worker)

            def _on_ai_err(error):
                try:
                    progress.reject()
                    QMessageBox.critical(self, "处理失败", f"AI 处理失败:\n{error}")
                finally:
                    self._cleanup_worker(state["import_worker"], progress)
                    self._cleanup_worker(ai_worker)

            ai_worker.finished_ai.connect(_on_ai_done)
            ai_worker.error.connect(_on_ai_err)
            ai_worker.start()

        import_worker = ImportWorker(file_paths)
        state["import_worker"] = import_worker
        self._register_worker(import_worker)

        import_worker.progress.connect(lambda c, t, s: progress.update_progress(c, t, f"导入: {s}"))
        import_worker.finished_import.connect(on_imported)

        def _on_import_err(error):
            try:
                progress.reject()
                QMessageBox.critical(self, "导入失败", f"导入过程中发生错误:\n{error}")
            finally:
                self._cleanup_worker(import_worker, progress)

        import_worker.error.connect(_on_import_err)
        import_worker.start()

    def _on_ai_finished(self, progress):
        progress.accept()
        self._refresh_library()
        QMessageBox.information(self, "完成", "AI 处理完成")

    def _on_ai_error(self, error: str, progress):
        progress.reject()
        QMessageBox.critical(self, "处理失败", f"AI 处理失败:\n{error}")

    def _on_ai_process_all(self):
        papers = self.library_service.get_all_papers(limit=10000)
        paper_ids = [p.id for p in papers if p.id]

        if not paper_ids:
            QMessageBox.information(self, "提示", "没有可处理的文献")
            return

        reply = QMessageBox.question(
            self, "确认",
            f"将对 {len(paper_ids)} 篇文献进行 AI 处理，是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            progress = ProgressDialog("AI 处理", self)
            progress.show()

            worker = AIWorker(paper_ids)
            self._register_worker(worker, progress)
            worker.progress.connect(progress.update_progress)

            def _on_done():
                try:
                    progress.accept()
                    self._refresh_library()
                    QMessageBox.information(self, "完成", "AI 处理完成")
                finally:
                    self._cleanup_worker(worker, progress)

            def _on_err(error):
                try:
                    progress.reject()
                    QMessageBox.critical(self, "处理失败", f"AI 处理失败:\n{error}")
                finally:
                    self._cleanup_worker(worker, progress)

            worker.finished_ai.connect(_on_done)
            worker.error.connect(_on_err)
            worker.start()

    def _refresh_library(self):
        papers = self.library_service.get_all_papers(limit=1000)
        self.library_panel.load_papers(papers)
        self.sidebar.refresh()
        self._update_status_bar()

    def _update_status_bar(self):
        total = self.library_service.count_papers()
        self.status_bar.showMessage(f"文献总数: {total}")

    def _on_search_text_changed(self, text: str):
        self._search_timer.start()

    def _do_search(self):
        query = self.sidebar.search_input.text().strip()
        if not query:
            self._refresh_library()
            return

        try:
            papers = self.search_service.advanced_search(
                query=query,
                **self.sidebar.get_filter_params()
            )
            self.library_panel.load_papers(papers)
        except Exception as e:
            logger.error(f"Search error: {e}")

    def _on_semantic_search(self, query: str):
        progress = ProgressDialog("语义搜索", self)
        progress.set_status("正在进行语义搜索...")
        progress.show()

        worker = SemanticSearchWorker(query, top_k=self.config.semantic_search_top_k)
        self._register_worker(worker, progress)

        def _on_done(results):
            try:
                progress.accept()
                papers = [paper for paper, score in results]
                self.library_panel.load_papers(papers)
                self.status_bar.showMessage(f"语义搜索结果: {len(results)} 篇")
            finally:
                self._cleanup_worker(worker, progress)

        def _on_err(error):
            try:
                progress.reject()
                QMessageBox.warning(self, "搜索失败", f"语义搜索失败:\n{error}")
            finally:
                self._cleanup_worker(worker, progress)

        worker.finished_search.connect(_on_done)
        worker.error.connect(_on_err)
        worker.start()

    def _on_semantic_search_finished(self, results, progress):
        progress.accept()
        papers = [paper for paper, score in results]
        self.library_panel.load_papers(papers)
        self.status_bar.showMessage(f"语义搜索结果: {len(results)} 篇")

    def _on_search_error(self, error: str, progress):
        progress.reject()
        QMessageBox.warning(self, "搜索失败", f"语义搜索失败:\n{error}")

    def _on_filter_changed(self, _=None):
        filter_params = self.sidebar.get_filter_params()
        query = self.sidebar.search_input.text().strip()

        if query:
            papers = self.search_service.advanced_search(query=query, **filter_params)
        else:
            papers = self.library_service.filter_papers(**filter_params)

        self.library_panel.load_papers(papers)

    def _on_paper_selected(self, paper_id: int):
        self.current_paper_id = paper_id
        paper = self.library_service.get_paper(paper_id)
        self.detail_panel.set_paper(paper)

    def _on_paper_double_clicked(self, paper_id: int):
        paper = self.library_service.get_paper(paper_id)
        if paper and paper.file_path:
            self._open_reader(paper)

    def _on_annotation_clicked(self, annotation_id: int, page: int):
        if self.reader_window and self.current_paper_id:
            self.reader_window.go_to_page(page)
            self.reader_window.raise_()
            self.reader_window.activateWindow()

    def _open_reader(self, paper):
        if self.reader_window is None:
            self.reader_window = PDFViewer()
            self.reader_window.setWindowTitle(f"{paper.title or '阅读'} - SmartLit")
            self.reader_window.resize(1000, 800)
            self.reader_window.annotation_added.connect(
                lambda ann: self.detail_panel.refresh_annotations()
            )

        self.reader_window.load_pdf(paper.file_path, paper.id)
        self.reader_window.show()
        self.reader_window.raise_()
        self.reader_window.activateWindow()

    def _on_export(self):
        from .dialogs import ExportDialog
        selected_id = self.library_panel.get_selected_paper_id()
        paper_ids = [selected_id] if selected_id else []

        if not paper_ids:
            all_papers = self.library_service.get_all_papers(limit=10000)
            paper_ids = [p.id for p in all_papers if p.id]

        dialog = ExportDialog(paper_ids, self)
        if dialog.exec():
            fmt = dialog.get_format()
            self._do_export(paper_ids, fmt)

    def _do_export(self, paper_ids: list[int], fmt: str):
        content = ""
        if fmt == "bibtex":
            content = self.library_service.export_bibtex(paper_ids)
            filter_str = "BibTeX (*.bib)"
            default_name = "papers.bib"
        else:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出文献", default_name, filter_str
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            QMessageBox.information(self, "导出成功", f"已导出 {len(paper_ids)} 篇文献")

    def _on_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def _on_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        try:
            for worker in list(self._workers):
                try:
                    if worker.isRunning():
                        worker.quit()
                        worker.wait(200)
                except Exception:
                    pass

            for progress in list(self._progress_dialogs):
                try:
                    progress.close()
                except Exception:
                    pass

            self._workers.clear()
            self._progress_dialogs.clear()

            if self.reader_window:
                self.reader_window.close()

            try:
                from ..db.database import get_db
                get_db().close()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error during close: {e}")

        event.accept()
