import os
import time
from typing import Any, Dict, Generator, Optional

from openai import OpenAI

from src.core.llm_provider import LLMProvider


class MimoProvider(LLMProvider):
    """
    LLM provider for Xiaomi MiMo's OpenAI-compatible API.
    Defaults to the token-plan Singapore endpoint shown in the dedicated plan.
    """

    DEFAULT_BASE_URL = "https://token-plan-sgp.xiaomimimo.com/v1"
    DEFAULT_MODEL = "mimo-v2.5-pro"
    DEFAULT_MAX_COMPLETION_TOKENS = 4096

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        thinking_type: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
    ):
        explicit_api_key = api_key is not None
        use_env_config = not explicit_api_key

        api_key = api_key or os.getenv("MIMO_API_KEY")
        if not api_key:
            raise ValueError("MIMO_API_KEY is required for MimoProvider.")

        super().__init__(model_name, api_key)

        self.base_url = (
            base_url
            or (os.getenv("MIMO_BASE_URL") if use_env_config else None)
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.thinking_type = (
            thinking_type
            or (os.getenv("MIMO_THINKING") if use_env_config else None)
            or "disabled"
        )
        self.max_completion_tokens = self._resolve_int(
            max_completion_tokens,
            "MIMO_MAX_COMPLETION_TOKENS",
            self.DEFAULT_MAX_COMPLETION_TOKENS,
            use_env=use_env_config,
        )
        self.temperature = self._resolve_float(
            temperature,
            "MIMO_TEMPERATURE",
            0.3,
            use_env=use_env_config,
        )
        self.top_p = self._resolve_float(
            top_p,
            "MIMO_TOP_P",
            0.95,
            use_env=use_env_config,
        )

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()

        response = self.client.chat.completions.create(
            **self._chat_request(prompt, system_prompt, stream=False)
        )

        latency_ms = int((time.time() - start_time) * 1000)
        content = response.choices[0].message.content or ""

        return {
            "content": content,
            "usage": self._usage_dict(getattr(response, "usage", None)),
            "latency_ms": latency_ms,
            "provider": "mimo",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        stream = self.client.chat.completions.create(
            **self._chat_request(prompt, system_prompt, stream=True)
        )

        for chunk in stream:
            if not getattr(chunk, "choices", None):
                continue

            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content

    def _chat_request(
        self,
        prompt: str,
        system_prompt: Optional[str],
        stream: bool,
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_completion_tokens": self.max_completion_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": stream,
        }

        if self.thinking_type:
            payload["extra_body"] = {"thinking": {"type": self.thinking_type}}

        return payload

    @staticmethod
    def _usage_dict(usage: Optional[Any]) -> Dict[str, int]:
        if usage is None:
            return {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

        usage_dict = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }

        details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None
        if reasoning_tokens is not None:
            usage_dict["reasoning_tokens"] = reasoning_tokens

        return usage_dict

    @staticmethod
    def _resolve_int(
        value: Optional[int],
        env_name: str,
        default: int,
        use_env: bool = True,
    ) -> int:
        if value is not None:
            return value
        if not use_env:
            return default
        return int(os.getenv(env_name, str(default)))

    @staticmethod
    def _resolve_float(
        value: Optional[float],
        env_name: str,
        default: float,
        use_env: bool = True,
    ) -> float:
        if value is not None:
            return value
        if not use_env:
            return default
        return float(os.getenv(env_name, str(default)))
