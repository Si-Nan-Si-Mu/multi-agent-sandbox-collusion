from __future__ import annotations

import httpx


class LLMClient:
    def chat(self, messages: list[dict]) -> str:
        raise NotImplementedError


class MockLLM(LLMClient):
    """Scripted replies. Calls cycle when the script is exhausted."""

    def __init__(self, replies: list[str]):
        if not replies:
            raise ValueError("MockLLM needs at least one scripted reply")
        self._replies = list(replies)
        self._i = 0

    def chat(self, messages: list[dict]) -> str:
        reply = self._replies[self._i % len(self._replies)]
        self._i += 1
        return reply


class OpenAICompatClient(LLMClient):
    """POST {base}/chat/completions and return the assistant text."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        max_tokens: int | None = None,
        timeout: float = 120.0,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._http = http_client

    def chat(self, messages: list[dict]) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: dict = {"model": self.model, "messages": messages}
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._http is not None:
            response = self._http.post(url, json=payload, headers=headers)
        else:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected chat completion response: {data}") from exc
        return content or ""
