import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

from .config import get_config


@dataclass
class AIModelConfig:
    provider: str = "local"
    api_key: str = ""
    base_url: str = ""
    model_name: str = ""
    api_version: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "AIModelConfig":
        return cls(
            provider=data.get("provider", "local"),
            api_key=data.get("api_key", ""),
            base_url=data.get("base_url", ""),
            model_name=data.get("model_name", ""),
            api_version=data.get("api_version", ""),
        )


@dataclass
class AIConfig:
    enabled: bool = True
    default_provider: str = "local"
    providers: dict[str, AIModelConfig] = field(default_factory=dict)
    summary_language: str = "zh"
    summary_sentences: int = 5
    keyword_count: int = 10
    semantic_search_top_k: int = 10

    @classmethod
    def default(cls) -> "AIConfig":
        return cls(
            providers={
                "local": AIModelConfig(provider="local"),
                "openai": AIModelConfig(
                    provider="openai",
                    base_url="https://api.openai.com/v1",
                    model_name="gpt-4o-mini",
                ),
                "claude": AIModelConfig(
                    provider="claude",
                    base_url="https://api.anthropic.com",
                    model_name="claude-3-haiku-20240307",
                ),
                "qwen": AIModelConfig(
                    provider="qwen",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    model_name="qwen-plus",
                ),
                "deepseek": AIModelConfig(
                    provider="deepseek",
                    base_url="https://api.deepseek.com/v1",
                    model_name="deepseek-chat",
                ),
                "azure": AIModelConfig(
                    provider="azure",
                    api_version="2024-02-01",
                    model_name="gpt-4o-mini",
                ),
                "custom": AIModelConfig(
                    provider="custom",
                    base_url="",
                    model_name="",
                ),
            }
        )


class AIConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.config_dir = get_config().app_data_dir
        self.config_file = self.config_dir / "ai_config.json"
        self.config: AIConfig = self._load()

    def _load(self) -> AIConfig:
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                providers = {}
                for name, prov_data in data.get("providers", {}).items():
                    providers[name] = AIModelConfig.from_dict(prov_data)

                default = AIConfig.default()
                for name, prov in default.providers.items():
                    if name not in providers:
                        providers[name] = prov

                return AIConfig(
                    enabled=data.get("enabled", True),
                    default_provider=data.get("default_provider", "local"),
                    providers=providers,
                    summary_language=data.get("summary_language", "zh"),
                    summary_sentences=data.get("summary_sentences", 5),
                    keyword_count=data.get("keyword_count", 10),
                    semantic_search_top_k=data.get("semantic_search_top_k", 10),
                )
            except Exception:
                pass
        return AIConfig.default()

    def save(self):
        try:
            data = {
                "enabled": self.config.enabled,
                "default_provider": self.config.default_provider,
                "providers": {
                    name: asdict(prov) for name, prov in self.config.providers.items()
                },
                "summary_language": self.config.summary_language,
                "summary_sentences": self.config.summary_sentences,
                "keyword_count": self.config.keyword_count,
                "semantic_search_top_k": self.config.semantic_search_top_k,
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_provider(self, name: str) -> Optional[AIModelConfig]:
        return self.config.providers.get(name)

    def set_provider(self, name: str, provider: AIModelConfig):
        self.config.providers[name] = provider
        self.save()

    def get_default_provider(self) -> AIModelConfig:
        name = self.config.default_provider
        return self.config.providers.get(name, AIModelConfig(provider="local"))


def get_ai_config_manager() -> AIConfigManager:
    return AIConfigManager()
