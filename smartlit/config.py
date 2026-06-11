import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        path = Path(base) / "SmartLit"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "SmartLit"
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        path = Path(base) / "SmartLit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    path = get_app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_app_data_dir() / "smartlit.db"


def get_notes_dir() -> Path:
    path = get_app_data_dir() / "notes"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Config:
    def __init__(self):
        self.app_data_dir = get_app_data_dir()
        self.db_path = get_db_path()
        self.log_dir = get_log_dir()
        self.models_dir = get_models_dir()
        self.notes_dir = get_notes_dir()
        self.watch_dirs: list[str] = []
        self.summary_language = "zh"
        self.summary_sentences = 5
        self.keyword_count = 10
        self.semantic_search_top_k = 10
        self.ai_cache_ttl = 86400
        self.ai_enabled = True


_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
