from PySide6.QtWidgets import QLineEdit, QWidget, QHBoxLayout
from PySide6.QtCore import Signal


class SearchBar(QWidget):
    search_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._input = QLineEdit()
        self._input.setPlaceholderText(
            'Search... try "sunset beach", "type:jpg year:2024", "red car camera:Canon"'
        )
        self._input.setMinimumWidth(400)
        self._input.returnPressed.connect(self._on_return)
        layout.addWidget(self._input)

    def _on_return(self):
        text = self._input.text().strip()
        if text:
            self.search_requested.emit(text)

    def set_query(self, query: str):
        self._input.setText(query)

    def get_query(self) -> str:
        return self._input.text().strip()
