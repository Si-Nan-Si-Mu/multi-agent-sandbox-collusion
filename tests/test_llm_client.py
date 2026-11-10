import json

import httpx

from agent_sandbox.llm_client import MockLLM, OpenAICompatClient
from agent_sandbox.roles import build_system_prompt


def test_mock_llm_cycles():
    m = MockLLM(["hello", "world"])
    assert m.chat([{"role": "user", "content": "x"}]) == "hello"
    assert m.chat([{"role": "user", "content": "x"}]) == "world"
    assert m.chat([{"role": "user", "content": "x"}]) == "hello"


def test_openai_compat_posts_chat_completions():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content.decode("utf-8"))
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok-reply"}}]},
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:8001/v1/",
        model="Qwen2.5-14B",
        api_key="test-key",
        max_tokens=128,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "ok-reply"
    assert captured["url"] == "http://127.0.0.1:8001/v1/chat/completions"
    assert captured["json"]["model"] == "Qwen2.5-14B"
    assert captured["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["json"]["max_tokens"] == 128
    assert captured["auth"] == "Bearer test-key"


def test_system_prompt_bilingual_dsl_and_safety():
    strong = build_system_prompt("solver", "strong")
    assert "WRITE" in strong
    assert "SUBMIT answer=" in strong
    assert "求解" in strong or "solver" in strong.lower()
    assert "诚实" in strong or "honest" in strong.lower()

    copy_role = build_system_prompt("planner_2", "weak")
    assert "规划" in copy_role or "planner" in copy_role.lower()
    assert "weak" in copy_role.lower() or "弱" in copy_role
