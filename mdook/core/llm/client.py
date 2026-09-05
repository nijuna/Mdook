"""OpenAI-compatible HTTP client using standard library urllib."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from mdook.core.llm.models import LLMConfig


class LLMClientError(Exception):
    """Raised when an LLM API call fails."""


def normalize_chat_endpoint(base_url: str) -> str:
    """Normalize a base URL to a full /chat/completions endpoint URL.

    Handles:
    - https://api.openai.com/v1 -> https://api.openai.com/v1/chat/completions
    - http://localhost:11434 -> http://localhost:11434/v1/chat/completions
    - http://localhost:11434/v1/ -> http://localhost:11434/v1/chat/completions
    - https://api.foo.bar/v1/chat/completions -> https://api.foo.bar/v1/chat/completions
    """
    url = base_url.strip().rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if not url.endswith("/v1") and "/v1" not in url:
        url = f"{url}/v1"
    return f"{url}/chat/completions"


def normalize_models_endpoint(base_url: str) -> str:
    """Normalize a base URL to a full /models endpoint URL.

    Handles:
    - https://api.openai.com/v1 -> https://api.openai.com/v1/models
    - https://api.groq.com/openai/v1 -> https://api.groq.com/openai/v1/models
    - http://localhost:11434 -> http://localhost:11434/v1/models
    - http://localhost:11434/v1 -> http://localhost:11434/v1/models
    - https://api.foo.bar/v1/chat/completions -> https://api.foo.bar/v1/models
    """
    url = base_url.strip().rstrip("/")
    if url.endswith("/chat/completions"):
        url = url[:-len("/chat/completions")]
    if not url.endswith("/v1") and "/v1" not in url:
        url = f"{url}/v1"
    return f"{url}/models"



class OpenAICompatibleClient:
    """Lightweight, zero-dependency client for any OpenAI-compatible API."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.endpoint = normalize_chat_endpoint(config.base_url)

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        """Send a chat completion request and return the assistant message content."""
        temp = self.config.temperature if temperature is None else temperature
        tokens = self.config.max_tokens if max_tokens is None else max_tokens
        timeout = self.config.timeout_seconds if timeout_seconds is None else timeout_seconds

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "Mdook/0.1.0",
        }

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key.strip()}"

        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.status
                body = response.read().decode("utf-8")

                if status != 200:
                    raise LLMClientError(f"HTTP {status} from {self.endpoint}: {body}")

                parsed = json.loads(body)
                choices = parsed.get("choices")
                if not choices or not isinstance(choices, list):
                    raise LLMClientError(f"Malformed response (no choices): {body[:200]}")

                message = choices[0].get("message", {})
                content = message.get("content")
                if content is None:
                    raise LLMClientError(f"Malformed response (no content): {body[:200]}")

                return str(content)

        except urllib.error.HTTPError as err:
            err_body = ""
            try:
                err_body = err.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise LLMClientError(
                f"HTTP {err.code} ({err.reason}) calling {self.endpoint}: {err_body[:300]}"
            ) from err
        except urllib.error.URLError as err:
            if isinstance(err.reason, TimeoutError):
                raise LLMClientError(
                    f"Request to {self.endpoint} timed out after {timeout}s"
                ) from err
            raise LLMClientError(f"Connection failed to {self.endpoint}: {err.reason}") from err
        except TimeoutError as err:
            raise LLMClientError(
                f"Request to {self.endpoint} timed out after {timeout}s"
            ) from err
        except json.JSONDecodeError as err:
            raise LLMClientError(f"Invalid JSON received from {self.endpoint}: {err}") from err
        except Exception as err:
            raise LLMClientError(f"Unexpected error calling {self.endpoint}: {err}") from err

    def test_connection(self, timeout_seconds: float = 8.0) -> tuple[bool, str]:
        """Test API reachability and model responsiveness with a 5-token ping.

        Measures roundtrip latency and returns (True, success_message)
        or (False, error_message).
        """
        start_time = time.perf_counter()
        try:
            self.chat_completion(
                [{"role": "user", "content": "ping"}],
                max_tokens=5,
                temperature=0.0,
                timeout_seconds=timeout_seconds,
            )
            elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            return True, f"Connected ({elapsed_ms}ms) — model '{self.config.model}'"
        except LLMClientError as err:
            return False, str(err)
        except Exception as err:
            return False, f"Connection test failed: {err}"

    def list_models(self, timeout_seconds: float = 8.0) -> list[str]:
        """Fetch available model IDs from the provider's /models endpoint.

        Returns a sorted list of unique model IDs.
        """
        models_endpoint = normalize_models_endpoint(self.config.base_url)
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "Mdook/0.1.0",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key.strip()}"
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)

        req = urllib.request.Request(models_endpoint, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                status = response.status
                body = response.read().decode("utf-8")
                if status != 200:
                    raise LLMClientError(
                        f"HTTP {status} fetching models from {models_endpoint}: {body[:200]}"
                    )
                parsed = json.loads(body)
        except urllib.error.HTTPError as err:
            err_body = ""
            try:
                err_body = err.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise LLMClientError(
                f"HTTP {err.code} ({err.reason}) calling {models_endpoint}: "
                f"{err_body[:200]}"
            ) from err
        except urllib.error.URLError as err:
            if isinstance(err.reason, TimeoutError):
                raise LLMClientError(
                    f"Request to {models_endpoint} timed out after {timeout_seconds}s"
                ) from err
            raise LLMClientError(f"Connection failed to {models_endpoint}: {err.reason}") from err
        except TimeoutError as err:
            raise LLMClientError(
                f"Request to {models_endpoint} timed out after {timeout_seconds}s"
            ) from err
        except json.JSONDecodeError as err:
            raise LLMClientError(
                f"Invalid JSON received from {models_endpoint}: {err}"
            ) from err
        except Exception as err:
            raise LLMClientError(
                f"Unexpected error fetching models from {models_endpoint}: {err}"
            ) from err

        raw_items = parsed.get("data") if isinstance(parsed, dict) else None
        if not isinstance(raw_items, list) and isinstance(parsed, dict):
            raw_items = parsed.get("models")
        if not isinstance(raw_items, list) and isinstance(parsed, list):
            raw_items = parsed

        if not isinstance(raw_items, list):
            raise LLMClientError(
                f"Unexpected response format from {models_endpoint}: {body[:200]}"
            )

        model_ids: list[str] = []
        for item in raw_items:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name")
                if mid and isinstance(mid, str):
                    model_ids.append(mid)
            elif isinstance(item, str) and item.strip():
                model_ids.append(item.strip())

        return sorted(list(dict.fromkeys(model_ids)))


