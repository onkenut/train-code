from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QListWidget, QListWidgetItem,
    QDialogButtonBox, QTabWidget, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QFormLayout, QWidget, QGroupBox
)
from PySide6.QtCore import Qt

from ..services.library_service import get_library_service
from ..ai_config import get_ai_config_manager, AIConfigManager


class ProgressDialog(QDialog):
    def __init__(self, title: str = "处理中", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        self.status_label = QLabel("准备中...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn, alignment=Qt.AlignRight)

    def update_progress(self, current: int, total: int, status: str = ""):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        if status:
            self.status_label.setText(status)

    def set_status(self, text: str):
        self.status_label.setText(text)


class ImportDialog(ProgressDialog):
    def __init__(self, file_paths: list[str], parent=None):
        super().__init__("导入文献", parent)
        self.file_paths = file_paths
        self.papers = []

    def set_results(self, papers: list):
        self.papers = papers


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 SmartLit")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        title = QLabel("<h2>SmartLit</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        version = QLabel("版本 1.0.0")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

        layout.addSpacing(10)

        desc = QLabel(
            "智能文献管理器\n"
            "本地优先的 PDF 文献管理与 AI 辅助分析工具\n\n"
            "功能特性：\n"
            "• PDF 文献管理与全文搜索\n"
            "• 内置阅读器与标注\n"
            "• AI 摘要与关键词提取\n"
            "• 语义搜索\n"
            "• 标签与笔记系统\n"
            "• 引用关系发现"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


class ExportDialog(QDialog):
    def __init__(self, paper_ids: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出文献")
        self.paper_ids = paper_ids

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"选择导出格式（{len(paper_ids)} 篇文献）:"))

        self.format_list = QListWidget()
        self.format_list.addItems(["BibTeX", "CSV", "JSON"])
        self.format_list.setCurrentRow(0)
        layout.addWidget(self.format_list)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_format(self) -> str:
        return self.format_list.currentItem().text().lower()


PROVIDER_LABELS = {
    "local": "本地离线 (KeyBERT)",
    "openai": "OpenAI",
    "claude": "Claude (Anthropic)",
    "qwen": "通义千问 (Qwen)",
    "deepseek": "DeepSeek",
    "azure": "Azure OpenAI",
    "custom": "自定义兼容 OpenAI 接口",
}


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.ai_config_mgr: AIConfigManager = get_ai_config_manager()

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_general_tab()
        self._build_ai_tab()

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _build_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("语言与显示")
        form = QFormLayout(group)
        self.summary_lang_combo = QComboBox()
        self.summary_lang_combo.addItem("中文", "zh")
        self.summary_lang_combo.addItem("English", "en")
        idx = self.summary_lang_combo.findData(
            self.ai_config_mgr.config.summary_language
        )
        if idx >= 0:
            self.summary_lang_combo.setCurrentIndex(idx)
        form.addRow("摘要语言:", self.summary_lang_combo)
        layout.addWidget(group)

        group2 = QGroupBox("AI 处理参数")
        form2 = QFormLayout(group2)
        self.summary_sentences_spin = QSpinBox()
        self.summary_sentences_spin.setRange(2, 20)
        self.summary_sentences_spin.setValue(
            self.ai_config_mgr.config.summary_sentences
        )
        form2.addRow("摘要句数:", self.summary_sentences_spin)

        self.keyword_count_spin = QSpinBox()
        self.keyword_count_spin.setRange(3, 50)
        self.keyword_count_spin.setValue(
            self.ai_config_mgr.config.keyword_count
        )
        form2.addRow("关键词数量:", self.keyword_count_spin)

        self.semantic_topk_spin = QSpinBox()
        self.semantic_topk_spin.setRange(3, 100)
        self.semantic_topk_spin.setValue(
            self.ai_config_mgr.config.semantic_search_top_k
        )
        form2.addRow("语义搜索结果数:", self.semantic_topk_spin)
        layout.addWidget(group2)

        layout.addStretch()
        self.tabs.addTab(tab, "通用")

    def _build_ai_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.ai_enabled_check = QCheckBox("启用 AI 功能")
        self.ai_enabled_check.setChecked(self.ai_config_mgr.config.enabled)
        layout.addWidget(self.ai_enabled_check)

        default_group = QGroupBox("默认 AI 提供方")
        default_layout = QVBoxLayout(default_group)
        self.provider_combo = QComboBox()
        for key, label in PROVIDER_LABELS.items():
            self.provider_combo.addItem(label, key)
        idx = self.provider_combo.findData(
            self.ai_config_mgr.config.default_provider
        )
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        default_layout.addWidget(self.provider_combo)
        layout.addWidget(default_group)

        keys_group = QGroupBox("API Key 配置")
        keys_layout = QVBoxLayout(keys_group)

        hint = QLabel("选择提供方后填入 API Key，设置保存在本地 AppData 目录下的 ai_config.json")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        keys_layout.addWidget(hint)

        self.api_fields = {}
        for prov_key, prov_label in PROVIDER_LABELS.items():
            if prov_key == "local":
                continue
            prov = self.ai_config_mgr.get_provider(prov_key)

            group = QGroupBox(prov_label)
            form = QFormLayout(group)

            api_key_edit = QLineEdit()
            api_key_edit.setEchoMode(QLineEdit.Password)
            api_key_edit.setPlaceholderText(f"输入 {prov_label} API Key")
            if prov and prov.api_key:
                api_key_edit.setText(prov.api_key)
            form.addRow("API Key:", api_key_edit)

            base_url_edit = QLineEdit()
            base_url_edit.setPlaceholderText("API Base URL（通常留空使用默认）")
            if prov and prov.base_url:
                base_url_edit.setText(prov.base_url)
            form.addRow("Base URL:", base_url_edit)

            model_edit = QLineEdit()
            model_edit.setPlaceholderText("模型名称")
            if prov and prov.model_name:
                model_edit.setText(prov.model_name)
            form.addRow("模型:", model_edit)

            if prov_key == "azure":
                api_version_edit = QLineEdit()
                api_version_edit.setPlaceholderText("API Version，如 2024-02-01")
                if prov and prov.api_version:
                    api_version_edit.setText(prov.api_version)
                form.addRow("API Version:", api_version_edit)
                self.api_fields[prov_key] = {
                    "api_key": api_key_edit,
                    "base_url": base_url_edit,
                    "model": model_edit,
                    "api_version": api_version_edit,
                }
            else:
                self.api_fields[prov_key] = {
                    "api_key": api_key_edit,
                    "base_url": base_url_edit,
                    "model": model_edit,
                }

            keys_layout.addWidget(group)

        keys_layout.addStretch()
        layout.addWidget(keys_group)

        self.tabs.addTab(tab, "AI 提供方")

    def _on_provider_changed(self, index: int):
        pass

    def _on_accept(self):
        cfg = self.ai_config_mgr
        cfg.config.enabled = self.ai_enabled_check.isChecked()
        cfg.config.default_provider = self.provider_combo.currentData()
        cfg.config.summary_language = self.summary_lang_combo.currentData()
        cfg.config.summary_sentences = self.summary_sentences_spin.value()
        cfg.config.keyword_count = self.keyword_count_spin.value()
        cfg.config.semantic_search_top_k = self.semantic_topk_spin.value()

        for prov_key, fields in self.api_fields.items():
            prov = cfg.get_provider(prov_key)
            if prov is None:
                from ..ai_config import AIModelConfig
                prov = AIModelConfig(provider=prov_key)

            prov.api_key = fields["api_key"].text().strip()
            prov.base_url = fields["base_url"].text().strip()
            prov.model_name = fields["model"].text().strip()
            if "api_version" in fields:
                prov.api_version = fields["api_version"].text().strip()

            cfg.set_provider(prov_key, prov)

        cfg.save()
        self.accept()
