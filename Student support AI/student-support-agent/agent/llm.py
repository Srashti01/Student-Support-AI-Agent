"""Thin wrapper around the Groq SDK: handles tool-calling format, retries on rate limits and returns
latency + token usage for every call."""
import json
import time
from dataclasses import dataclass, field

import config


@dataclass
class LLMResponse:
    content: str
    tool_calls: list = field(default_factory=list)   # [{"id","name","arguments"(str)}]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency: float = 0.0
    retries: int = 0


class GroqLLM:
    def __init__(self, api_key=None, model=None):
        from groq import Groq
        self.api_key = api_key or config.GROQ_API_KEY
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is missing. Put it in .env or paste it in the sidebar.")
        self.client = Groq(api_key=self.api_key)
        self.model = model or config.DEFAULT_MODEL

    def chat(self, messages, tools=None, max_retries=4) -> LLMResponse:
        t0, retries = time.perf_counter(), 0
        while True:
            try:
                kwargs = dict(model=self.model, messages=messages, temperature=0, max_tokens=2000)
                if "gpt-oss" in self.model:   # reasoning models: keep thinking short
                    kwargs["extra_body"] = {"reasoning_effort": "low"}
                if tools:
                    kwargs.update(tools=tools, tool_choice="auto")
                r = self.client.chat.completions.create(**kwargs)
                msg = r.choices[0].message
                calls = [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments or "{}"}
                         for tc in (msg.tool_calls or [])]
                u = r.usage
                return LLMResponse(msg.content or "", calls, getattr(u, "prompt_tokens", 0),
                                   getattr(u, "completion_tokens", 0), time.perf_counter() - t0, retries)
            except Exception as e:  # rate limit / malformed tool call -> back off and retry
                name, text = type(e).__name__, str(e)
                retryable = "RateLimit" in name or "tool_use_failed" in text or "429" in text or "Connection" in name
                if retries >= max_retries or not retryable:
                    raise
                retries += 1
                time.sleep(min(2 ** retries * 2, 20) if "RateLimit" in name or "429" in text else 1)


def parse_args(raw: str) -> dict:
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}
