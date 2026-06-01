import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from src.agent.agent import ActionParseError, ReActAgent
from src.core.llm_provider import LLMProvider
from src.tools.output_writer import write_research_artifacts
from src.tools.research_tools import (
    compare_and_find_gaps,
    extract_evidence_cards,
    search_papers,
)
from scripts.run_research_gap_demo import (
    build_research_tools,
    resolve_provider_name,
    run_failure_trace,
    run_success_trace,
)


class DummyProvider(LLMProvider):
    def __init__(self, responses: List[str]):
        super().__init__(model_name="dummy-test-model")
        self.responses = responses
        self.index = 0
        self.prompts: List[str] = []

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        self.prompts.append(prompt)
        if self.index < len(self.responses):
            content = self.responses[self.index]
        else:
            content = self.responses[-1]
        self.index += 1
        prompt_tokens = len(prompt.split()) + len((system_prompt or "").split())
        completion_tokens = len(content.split())
        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "latency_ms": 2,
            "provider": "dummy",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt=system_prompt)["content"]


def test_parse_action_json_args():
    action = ReActAgent.parse_action(
        'Thought: search first.\nAction: search_papers({"query": "ssl segmentation", "limit": 2})'
    )

    assert action is not None
    assert action.name == "search_papers"
    assert action.args == {"query": "ssl segmentation", "limit": 2}
    assert ReActAgent.parse_action("Thought: done.") is None

    with pytest.raises(ActionParseError):
        ReActAgent.parse_action('Action: search_papers(query="ssl segmentation")')


def test_mixed_action_observation_and_final_executes_tool_first(caplog):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    calls = []

    provider = DummyProvider(
        [
            (
                "Thought: I can do everything at once.\n"
                "Action: record({\"value\": 7})\n"
                "Observation: forged observation from the model.\n"
                "Final Answer: forged final answer."
            ),
            "Final Answer: runtime tool path completed.",
        ]
    )
    agent = ReActAgent(
        llm=provider,
        tools=[
            {
                "name": "record",
                "description": "Records a value.",
                "function": lambda value: calls.append(value) or {"ok": True, "value": value},
            }
        ],
        max_steps=2,
    )

    assert agent.run("exercise mixed response handling") == "runtime tool path completed."
    assert calls == [7]

    events = _captured_events(caplog)
    assert "MIXED_RESPONSE_IGNORED_FINAL" in events
    assert "MODEL_OBSERVATION_IGNORED" in events
    assert events.count("TOOL_CALL") == 1


def test_final_only_response_still_finishes():
    provider = DummyProvider(["Final Answer: direct final answer."])
    agent = ReActAgent(llm=provider, tools=[], max_steps=1)

    assert agent.run("finish directly") == "direct final answer."


def test_required_tool_guard_ignores_premature_final(caplog):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    calls = []
    provider = DummyProvider(
        [
            "Final Answer: premature.",
            "Thought: I should write outputs first.\nAction: write_outputs({})",
            "Final Answer: complete after write.",
        ]
    )
    agent = ReActAgent(
        llm=provider,
        tools=[
            {
                "name": "write_outputs",
                "description": "Writes artifacts.",
                "function": lambda: calls.append("write_outputs") or {"artifact_paths": {}},
            }
        ],
        max_steps=3,
        required_tools_before_final=["write_outputs"],
    )

    assert agent.run("require artifact write") == "complete after write."
    assert calls == ["write_outputs"]
    assert "PREMATURE_FINAL_ANSWER_IGNORED" in _captured_events(caplog)


def test_malformed_action_with_final_does_not_bypass_parser(caplog):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    calls = []

    provider = DummyProvider(
        [
            (
                "Thought: malformed but I will also claim completion.\n"
                "Action: record(value=7)\n"
                "Final Answer: bypassed final answer."
            ),
            "Final Answer: recovered after parser error.",
        ]
    )
    agent = ReActAgent(
        llm=provider,
        tools=[
            {
                "name": "record",
                "description": "Records a value.",
                "function": lambda value: calls.append(value) or {"ok": True, "value": value},
            }
        ],
        max_steps=2,
    )

    assert agent.run("exercise malformed action handling") == "recovered after parser error."
    assert calls == []

    events = _captured_events(caplog)
    assert "MIXED_RESPONSE_IGNORED_FINAL" in events
    assert "PARSER_ERROR" in events
    assert "TOOL_CALL" not in events


def test_unexecuted_extra_actions_are_not_added_to_scratchpad():
    calls = []
    provider = DummyProvider(
        [
            (
                "Thought: I will over-generate.\n"
                "Action: first_tool({})\n"
                "Observation: fake first observation.\n"
                "Thought: I will pretend to continue.\n"
                "Action: second_tool({})\n"
                "Observation: fake second observation."
            ),
            "Final Answer: done.",
        ]
    )
    agent = ReActAgent(
        llm=provider,
        tools=[
            {
                "name": "first_tool",
                "description": "First tool.",
                "function": lambda: calls.append("first") or {"ok": "first"},
            },
            {
                "name": "second_tool",
                "description": "Second tool.",
                "function": lambda: calls.append("second") or {"ok": "second"},
            },
        ],
        max_steps=2,
    )

    assert agent.run("exercise over-generated action handling") == "done."
    assert calls == ["first"]
    assert "Action: second_tool" not in provider.prompts[1]
    assert "fake second observation" not in provider.prompts[1]


def test_unknown_tool_and_tool_failure_logging(caplog):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")

    def explode() -> Dict[str, Any]:
        raise RuntimeError("tool exploded")

    provider = DummyProvider(
        [
            "Thought: call a missing tool.\nAction: missing_tool({})",
            "Thought: call a tool that fails.\nAction: explode({})",
            "Final Answer: handled failures.",
        ]
    )
    agent = ReActAgent(
        llm=provider,
        tools=[
            {
                "name": "explode",
                "description": "Raises an exception.",
                "function": explode,
            }
        ],
        max_steps=3,
    )

    assert agent.run("exercise failure handling") == "handled failures."

    events = _captured_events(caplog)
    assert "AGENT_ERROR" in events
    assert events.count("TOOL_CALL") == 2
    assert events.count("TOOL_RESULT") == 2
    assert "FINAL_ANSWER" in events


def test_max_steps_guard_logs_event(caplog):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    provider = DummyProvider(["Thought: keep going.\nAction: noop({})"])
    agent = ReActAgent(
        llm=provider,
        tools=[
            {
                "name": "noop",
                "description": "Returns a small observation.",
                "function": lambda: {"ok": True},
            }
        ],
        max_steps=1,
    )

    assert agent.run("never finish") == "Max steps exceeded before final answer."
    assert "MAX_STEPS_EXCEEDED" in _captured_events(caplog)


def test_offline_workflow_writes_source_linked_artifacts(tmp_path):
    topic = "federated learning privacy"
    papers = search_papers(
        topic,
        limit=5,
        year_range=[2021, 2025],
        offline=True,
    )
    cards = extract_evidence_cards(papers)
    comparison = compare_and_find_gaps(cards)
    paths = write_research_artifacts(cards, comparison, output_dir=tmp_path, topic=topic)

    assert len(cards) >= 4
    assert comparison["coverage"]["all_gaps_have_sources"] is True
    assert comparison["coverage"]["all_claims_have_sources"] is True
    assert {card["source"]["source_mode"] for card in cards} == {"mock"}

    for gap in comparison["candidate_gaps"]:
        assert gap["sources"]
        assert gap["confidence"] in {"medium", "uncertain"}
        assert gap["validation_query"]

    for row in comparison["matrix"]:
        for claim in row["claims"]:
            assert claim["source"]["paperId"]
            assert claim["source"]["title"]
            assert claim["source"]["source_mode"]

    for path in paths.values():
        assert Path(path).exists()

    report = Path(paths["gap_analysis_report"]).read_text(encoding="utf-8")
    matrix = Path(paths["comparison_matrix"]).read_text(encoding="utf-8")
    evidence_payload = json.loads(Path(paths["evidence_cards"]).read_text(encoding="utf-8"))
    assert f"Topic: {topic}" in report
    assert "self-supervised learning for medical image segmentation" not in report
    assert "## Coverage Check" in report
    assert "Gap validation query" in report
    assert "## Final Self-Review" in report
    assert "Source modes: mock" in report
    assert "Fallback/mock status:" in report
    assert "source: mock" in matrix
    assert all(card["source"]["source_mode"] == "mock" for card in evidence_payload)


def test_downstream_research_tools_ignore_llm_supplied_state(tmp_path):
    tools = {
        tool["name"]: tool["function"]
        for tool in build_research_tools(
            topic="federated learning privacy",
            offline=True,
            output_dir=tmp_path,
        )
    }
    tools["search_papers"](query="federated learning privacy", limit=5)

    malicious_papers = [
        {
            "paperId": "FAKE-001",
            "title": "LLM supplied fake paper",
            "year": 2099,
            "abstract": "This should never be trusted.",
        }
    ]
    extract_result = tools["extract_evidence_cards"](papers=malicious_papers)
    assert extract_result["ignored_args"] == ["papers"]
    assert extract_result["card_count"] >= 4
    assert all(card["paperId"] != "FAKE-001" for card in extract_result["evidence_cards"])

    fake_cards = [{"paperId": "FAKE-CARD", "title": "fake card", "claims": ["fake"]}]
    comparison_result = tools["compare_and_find_gaps"](evidence_cards=fake_cards)
    assert comparison_result["ignored_args"] == ["evidence_cards"]
    assert comparison_result["coverage"]["paper_count"] == extract_result["card_count"]

    write_result = tools["write_outputs"](
        evidence_cards=fake_cards,
        comparison={"candidate_gaps": []},
    )
    assert write_result["ignored_args"] == ["comparison", "evidence_cards"]
    evidence_path = Path(write_result["artifact_paths"]["evidence_cards"])
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert all(card["paperId"] != "FAKE-CARD" for card in evidence_payload)


_ARXIV_FEED_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <published>2024-01-15T00:00:00Z</published>
    <title>arXiv source test</title>
    <summary>A method improves robustness
    but omits external validation.</summary>
    <author><name>A. Author</name></author>
    <arxiv:primary_category term="cs.LG"/>
  </entry>
</feed>"""


def test_arxiv_success_preserves_source_metadata(monkeypatch):
    class FakeResponse:
        text = _ARXIV_FEED_TEMPLATE

        def raise_for_status(self):
            return None

    import requests

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

    papers = search_papers("source metadata test", limit=1, offline=False)
    assert papers[0]["source_mode"] == "arxiv"
    assert papers[0]["paperId"] == "2401.00001v1"
    assert papers[0]["url"] == "http://arxiv.org/abs/2401.00001v1"
    assert papers[0]["year"] == 2024
    assert papers[0]["venue"] == "cs.LG"
    # whitespace/newlines in the abstract are collapsed
    assert papers[0]["abstract"] == "A method improves robustness but omits external validation."
    assert papers[0]["externalIds"] == {"ArXiv": "2401.00001v1"}

    cards = extract_evidence_cards(papers)
    assert cards[0]["source"]["source_mode"] == "arxiv"
    assert cards[0]["source"]["url"] == "http://arxiv.org/abs/2401.00001v1"
    assert cards[0]["source"]["venue"] == "cs.LG"
    assert cards[0]["source"]["externalIds"] == {"ArXiv": "2401.00001v1"}


def test_arxiv_failure_logs_and_marks_mock_fallback(monkeypatch, caplog):
    import requests

    def fail_request(*args, **kwargs):
        raise requests.Timeout("timed out")

    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    monkeypatch.setattr(requests, "get", fail_request)

    papers = search_papers("fallback source test", limit=2, offline=False)

    assert len(papers) == 2
    assert {paper["source_mode"] for paper in papers} == {"mock_fallback"}
    events = _captured_event_payloads(caplog)
    fallback_events = [event for event in events if event.get("event") == "SEARCH_FALLBACK"]
    assert fallback_events
    assert fallback_events[-1]["data"]["fallback_reason"] == "request_failed"
    assert fallback_events[-1]["data"]["error_type"] == "Timeout"


def test_scripted_cli_path_renders_requested_topic(caplog, tmp_path):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    topic = "federated learning privacy"
    answer = run_success_trace(
        topic=topic,
        offline=True,
        output_dir=tmp_path,
        provider_name="scripted",
    )

    assert "MVP research gap analysis is complete" in answer
    tool_calls = [
        payload["data"]["tool"]
        for payload in _captured_event_payloads(caplog)
        if payload.get("event") == "TOOL_CALL"
    ]
    assert tool_calls[:4] == [
        "search_papers",
        "extract_evidence_cards",
        "compare_and_find_gaps",
        "write_outputs",
    ]
    report = (tmp_path / "gap_analysis_report.md").read_text(encoding="utf-8")
    assert f"Topic: {topic}" in report


def test_provider_selection_defaults_to_mimo_and_requires_key(monkeypatch):
    monkeypatch.delenv("DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("MIMO_API_KEY", raising=False)

    assert resolve_provider_name(None) == "mimo"

    with pytest.raises(SystemExit) as exc:
        run_success_trace(
            topic="federated learning privacy",
            offline=True,
            output_dir=Path("unused"),
            provider_name="mimo",
        )

    assert "--provider scripted --offline" in str(exc.value)


def test_failure_trace_returns_useful_summary(caplog, tmp_path):
    caplog.set_level(logging.INFO, logger="AI-Lab-Agent")
    result = run_failure_trace(
        topic="federated learning privacy",
        offline=True,
        output_dir=tmp_path,
    )

    assert "Failure-handling trace complete" in result
    events = _captured_events(caplog)
    assert "PARSER_ERROR" in events
    assert "AGENT_ERROR" in events
    assert "MAX_STEPS_EXCEEDED" not in events


def test_uncertain_gap_when_evidence_is_missing():
    cards = extract_evidence_cards(
        [
            {
                "paperId": "MISSING-EVIDENCE-001",
                "title": "Metadata-only federated SSL segmentation claim",
                "year": 2024,
                "abstract": None,
                "authors": [{"name": "A. Researcher"}],
                "methods": ["federated self-supervised learning"],
                "limitations": ["Only metadata is available; claims cannot be verified."],
            }
        ]
    )
    comparison = compare_and_find_gaps(cards)

    assert "abstract" in cards[0]["uncertain_fields"]
    uncertain_gaps = [
        gap for gap in comparison["candidate_gaps"] if gap["confidence"] == "uncertain"
    ]
    assert uncertain_gaps
    assert any(gap["id"] == "GAP-003" for gap in uncertain_gaps)
    assert all(gap["sources"] for gap in uncertain_gaps)


def _captured_events(caplog) -> List[str]:
    return [payload["event"] for payload in _captured_event_payloads(caplog) if payload.get("event")]


def _captured_event_payloads(caplog) -> List[Dict[str, Any]]:
    events = []
    for record in caplog.records:
        try:
            payload = json.loads(record.message)
        except json.JSONDecodeError:
            continue
        events.append(payload)
    return events
