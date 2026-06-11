from typing import Optional
import json

from ..infrastructure.logger import get_logger

logger = get_logger(__name__)


class BaseAIProvider:
    name = "base"

    def __init__(self, api_key: str = "", base_url: str = "", model_name: str = "", **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.extra = kwargs

    def is_available(self) -> bool:
        return True

    def generate_summary(self, text: str, language: str = "zh", sentences: int = 5) -> Optional[str]:
        raise NotImplementedError

    def generate_keywords(self, text: str, count: int = 10) -> list[str]:
        raise NotImplementedError

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        raise NotImplementedError


class LocalAIProvider(BaseAIProvider):
    name = "local"

    def is_available(self) -> bool:
        return True

    def _split_sentences(self, text: str) -> list[str]:
        import re
        sentences = re.split(r'(?<=[.!?。！？])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 20]

    def generate_summary(self, text: str, language: str = "zh", sentences: int = 5) -> Optional[str]:
        try:
            from keybert import KeyBERT
            sents = self._split_sentences(text)
            if not sents:
                return None

            try:
                kw_model = KeyBERT()
                keywords = kw_model.extract_keywords(
                    text[:5000],
                    keyphrase_ngram_range=(1, 2),
                    top_n=20
                )
            except Exception:
                keywords = []

            scored = []
            for sent in sents[:30]:
                score = 0
                for kw, kw_score in keywords:
                    if kw.lower() in sent.lower():
                        score += kw_score
                scored.append((score, sent))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = [s for _, s in scored[:sentences]]
            summary = " ".join(top)
            return summary[:2000] if summary else None
        except Exception as e:
            logger.error(f"Local summary failed: {e}")
            sents = self._split_sentences(text)
            if sents:
                return " ".join(sents[:sentences])[:2000]
            return None

    def generate_keywords(self, text: str, count: int = 10) -> list[str]:
        try:
            from keybert import KeyBERT
            kw_model = KeyBERT()
            keywords = kw_model.extract_keywords(
                text[:5000],
                keyphrase_ngram_range=(1, 2),
                top_n=count
            )
            return [kw for kw, _ in keywords]
        except Exception as e:
            logger.error(f"Local keywords failed: {e}")
            import re
            from collections import Counter
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
            stop = {'with', 'that', 'this', 'from', 'which', 'between',
                    'based', 'using', 'also', 'more', 'each', 'other',
                    'such', 'these', 'those', 'than', 'then', 'their'}
            filtered = [(w, c) for w, c in Counter(words).items() if w not in stop]
            filtered.sort(key=lambda x: x[1], reverse=True)
            return [w for w, _ in filtered[:count]]

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        return None


class OpenAICompatibleProvider(BaseAIProvider):
    name = "openai_compatible"

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model_name)

    def _request(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        if not self.is_available():
            return None

        try:
            import urllib.request
            import ssl

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            url = f"{self.base_url.rstrip('/')}/chat/completions"

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"{self.name} API request failed: {e}")
            return None

    def generate_summary(self, text: str, language: str = "zh", sentences: int = 5) -> Optional[str]:
        lang_prompt = "中文" if language == "zh" else "English"
        system = (
            f"You are a helpful research assistant. "
            f"Generate a concise {sentences}-sentence summary of the following paper in {lang_prompt}."
        )
        user = f"Please summarize this paper:\n\n{text[:8000]}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self._request(messages, temperature=0.5, max_tokens=1500)

    def generate_keywords(self, text: str, count: int = 10) -> list[str]:
        system = (
            "You are a research paper keyword extractor. "
            "Extract the most important keywords from the paper. "
            f"Return exactly {count} keywords as a JSON array of strings. No other text."
        )
        user = f"Extract keywords from:\n\n{text[:5000]}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        result = self._request(messages, temperature=0.3, max_tokens=500)
        if not result:
            return []

        try:
            start = result.find("[")
            end = result.rfind("]") + 1
            if start >= 0 and end > start:
                kws = json.loads(result[start:end])
                if isinstance(kws, list):
                    return [str(k).strip() for k in kws if str(k).strip()][:count]
        except Exception:
            pass

        lines = [l.strip().lstrip("-•*0123456789. ") for l in result.split("\n")]
        return [l for l in lines if l][:count]

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        return self._request(messages, temperature, max_tokens)


class ClaudeProvider(OpenAICompatibleProvider):
    name = "claude"

    def _request(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        if not self.api_key or not self.base_url or not self.model_name:
            return None

        try:
            import urllib.request
            import ssl

            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }

            system = ""
            user_msgs = []
            for m in messages:
                if m["role"] == "system":
                    system = m["content"]
                else:
                    user_msgs.append(m)

            payload = {
                "model": self.model_name,
                "messages": user_msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system:
                payload["system"] = system

            url = f"{self.base_url.rstrip('/')}/v1/messages"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["content"][0]["text"]

        except Exception as e:
            logger.error(f"Claude API request failed: {e}")
            return None


class AzureProvider(BaseAIProvider):
    name = "azure"

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model_name)

    def _request(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        if not self.is_available():
            return None

        try:
            import urllib.request
            import ssl

            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }

            payload = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            api_version = self.extra.get("api_version", "2024-02-01")
            url = (
                f"{self.base_url.rstrip('/')}/openai/deployments/{self.model_name}"
                f"/chat/completions?api-version={api_version}"
            )

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Azure API request failed: {e}")
            return None

    def generate_summary(self, text: str, language: str = "zh", sentences: int = 5) -> Optional[str]:
        lang_prompt = "中文" if language == "zh" else "English"
        system = (
            f"You are a helpful research assistant. "
            f"Generate a concise {sentences}-sentence summary in {lang_prompt}."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"总结以下论文:\n\n{text[:8000]}"},
        ]
        return self._request(messages, temperature=0.5, max_tokens=1500)

    def generate_keywords(self, text: str, count: int = 10) -> list[str]:
        system = f"提取 {count} 个关键词，返回 JSON 数组"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"关键词提取:\n\n{text[:5000]}"},
        ]
        result = self._request(messages, temperature=0.3, max_tokens=500)
        if not result:
            return []
        try:
            start = result.find("[")
            end = result.rfind("]") + 1
            if start >= 0 and end > start:
                kws = json.loads(result[start:end])
                if isinstance(kws, list):
                    return [str(k).strip() for k in kws if str(k).strip()][:count]
        except Exception:
            pass
        return []

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        return self._request(messages, temperature, max_tokens)


PROVIDER_REGISTRY = {
    "local": LocalAIProvider,
    "openai": OpenAICompatibleProvider,
    "claude": ClaudeProvider,
    "qwen": OpenAICompatibleProvider,
    "deepseek": OpenAICompatibleProvider,
    "azure": AzureProvider,
    "custom": OpenAICompatibleProvider,
}


def create_provider(provider_name: str, api_key: str = "", base_url: str = "",
                    model_name: str = "", **kwargs) -> BaseAIProvider:
    cls = PROVIDER_REGISTRY.get(provider_name, LocalAIProvider)
    return cls(api_key=api_key, base_url=base_url, model_name=model_name, **kwargs)
