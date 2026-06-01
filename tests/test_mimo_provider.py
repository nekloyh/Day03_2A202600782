import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(
                [
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content="hel"))]
                    ),
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"))]
                    ),
                ]
            )

        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="hello from mimo"))
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                completion_tokens_details=SimpleNamespace(reasoning_tokens=3),
            ),
        )


class FakeOpenAI:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)
        self.__class__.instances.append(self)


def import_mimo_provider(monkeypatch):
    fake_openai = ModuleType("openai")
    fake_openai.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    sys.modules.pop("src.core.mimo_provider", None)
    return importlib.import_module("src.core.mimo_provider")


def test_mimo_provider_uses_token_plan_defaults(monkeypatch):
    module = import_mimo_provider(monkeypatch)

    provider = module.MimoProvider(api_key="test-key")
    result = provider.generate("Hello", system_prompt="Be direct.")

    client = FakeOpenAI.instances[-1]
    request = client.completions.calls[-1]

    assert client.kwargs == {
        "api_key": "test-key",
        "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
    }
    assert request["model"] == "mimo-v2.5-pro"
    assert request["messages"] == [
        {"role": "system", "content": "Be direct."},
        {"role": "user", "content": "Hello"},
    ]
    assert request["max_completion_tokens"] == 32768
    assert request["temperature"] == 1.0
    assert request["top_p"] == 0.95
    assert request["stream"] is False
    assert request["extra_body"] == {"thinking": {"type": "enabled"}}
    assert result["content"] == "hello from mimo"
    assert result["provider"] == "mimo"
    assert result["usage"]["reasoning_tokens"] == 3


def test_mimo_provider_streams_content(monkeypatch):
    module = import_mimo_provider(monkeypatch)

    provider = module.MimoProvider(api_key="test-key")

    assert "".join(provider.stream("Hello")) == "hello"
