import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.tools.output_writer import DEFAULT_OUTPUT_DIR, write_research_artifacts
from src.tools.research_tools import (
    compare_and_find_gaps,
    extract_evidence_cards,
    search_papers,
)


PROVIDER_CHOICES = ("mimo", "openai", "google", "local", "scripted")
PROVIDER_ALIASES = {
    "gemini": "google",
}


class ScriptedProvider(LLMProvider):
    def __init__(self, responses: List[str], model_name: str = "scripted-react-demo"):
        super().__init__(model_name=model_name)
        self.responses = responses
        self.index = 0

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        if self.index < len(self.responses):
            content = self.responses[self.index]
        else:
            content = "Final Answer: Script exhausted before a final answer was prepared."
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
            "latency_ms": 1,
            "provider": "scripted",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt=system_prompt)["content"]


def build_research_tools(topic: str, offline: bool, output_dir: Path) -> List[Dict[str, Any]]:
    state: Dict[str, Any] = {}

    def search_papers_tool(
        query: str,
        limit: int = 5,
        year_range: Optional[List[int]] = None,
        offline: Optional[bool] = None,
    ) -> Dict[str, Any]:
        ignored_args = []
        if offline is not None:
            ignored_args.append("offline")
        papers = search_papers(
            query=query,
            limit=limit,
            year_range=year_range,
            offline=state.get("offline", False),
        )
        state["papers"] = papers
        source_modes = sorted({paper.get("source_mode", "unknown") for paper in papers})
        return {
            "paper_count": len(papers),
            "papers": papers,
            "source_modes": source_modes,
            "ignored_args": ignored_args,
        }

    def extract_evidence_cards_tool(
        papers: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ignored_args = _ignored_args({"papers": papers, **kwargs})
        cards = extract_evidence_cards(state.get("papers"))
        state["evidence_cards"] = cards
        return {
            "card_count": len(cards),
            "evidence_cards": cards,
            "ignored_args": ignored_args,
        }

    def compare_and_find_gaps_tool(
        evidence_cards: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ignored_args = _ignored_args({"evidence_cards": evidence_cards, **kwargs})
        comparison = compare_and_find_gaps(state.get("evidence_cards"))
        state["comparison"] = comparison
        return {**comparison, "ignored_args": ignored_args}

    def write_outputs_tool(
        evidence_cards: Optional[List[Dict[str, Any]]] = None,
        comparison: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ignored_args = _ignored_args(
            {"evidence_cards": evidence_cards, "comparison": comparison, **kwargs}
        )
        evidence_cards = state.get("evidence_cards") or extract_evidence_cards(state.get("papers"))
        comparison = state.get("comparison") or compare_and_find_gaps(evidence_cards)
        paths = write_research_artifacts(
            evidence_cards=evidence_cards,
            comparison=comparison,
            output_dir=output_dir,
            topic=topic,
        )
        return {
            "artifact_paths": paths,
            "gap_count": len(comparison.get("candidate_gaps", [])),
            "uncertain_gap_count": sum(
                1
                for gap in comparison.get("candidate_gaps", [])
                if gap.get("confidence") == "uncertain"
            ),
            "source_modes": sorted(
                {
                    (card.get("source") or {}).get("source_mode")
                    or card.get("source_mode")
                    or "unknown"
                    for card in evidence_cards
                }
            ),
            "ignored_args": ignored_args,
        }

    state["offline"] = offline

    return [
        {
            "name": "search_papers",
            "description": "Search papers by query, limit, and optional year_range. The runtime controls online/offline mode.",
            "function": search_papers_tool,
        },
        {
            "name": "extract_evidence_cards",
            "description": "Convert papers into source-linked evidence cards with claims, methods, limitations, and uncertain fields.",
            "function": extract_evidence_cards_tool,
        },
        {
            "name": "compare_and_find_gaps",
            "description": "Build a comparison matrix and source-linked candidate research gaps.",
            "function": compare_and_find_gaps_tool,
        },
        {
            "name": "write_outputs",
            "description": "Write gap_analysis_report.md, comparison_matrix.md, and evidence_cards.json artifacts.",
            "function": write_outputs_tool,
        },
    ]


def _ignored_args(values: Dict[str, Any]) -> List[str]:
    return sorted(key for key, value in values.items() if value is not None)


def scripted_success_responses(topic: str) -> List[str]:
    return [
        (
            "Thought: I need papers for the topic before making claims.\n"
            f"Action: search_papers({{\"query\": \"{topic}\", \"limit\": 5, "
            f"\"year_range\": [2021, 2025]}})"
        ),
        (
            "Thought: I have papers. I should extract source-linked evidence cards.\n"
            "Action: extract_evidence_cards({})"
        ),
        (
            "Thought: I need compare the evidence and find defensible gaps.\n"
            "Action: compare_and_find_gaps({})"
        ),
        (
            "Thought: The gaps are ready. I should write the required artifacts.\n"
            "Action: write_outputs({})"
        ),
        (
            "Final Answer: The MVP research gap analysis is complete. Artifacts were written "
            "under outputs/research_gap_analyzer_lite, and weak evidence is marked uncertain."
        ),
    ]


def run_success_trace(
    topic: str,
    offline: bool,
    output_dir: Path,
    provider_name: str = "scripted",
) -> str:
    llm = build_llm_provider(provider_name, topic=topic)
    agent = ReActAgent(
        llm=llm,
        tools=build_research_tools(topic=topic, offline=offline, output_dir=output_dir),
        max_steps=10,
        required_tools_before_final=["write_outputs"],
    )
    return agent.run(
        (
            f"Analyze research gaps for: {topic}. "
            "Use the available tools in this order unless a runtime observation says otherwise: "
            "search_papers, extract_evidence_cards, compare_and_find_gaps, write_outputs. "
            "Do not provide Final Answer until write_outputs returns artifact_paths."
        )
    )


def run_failure_trace(topic: str, offline: bool, output_dir: Path) -> str:
    responses = [
        (
            "Thought: I should search, but I will use a malformed action.\n"
            f"Action: search_papers(query=\"{topic}\")"
        ),
        (
            "Thought: The parser rejected that, so I will demonstrate an unknown tool failure.\n"
            "Action: cite_unseen_pdf({\"paperId\": \"MISSING-PDF-001\"})"
        ),
        (
            "Final Answer: Failure-handling trace complete. The runtime logged the malformed "
            "action as a parser error and the unavailable tool as an unknown-tool error."
        ),
    ]
    agent = ReActAgent(
        llm=ScriptedProvider(responses, model_name="scripted-failure-trace"),
        tools=build_research_tools(topic=topic, offline=offline, output_dir=output_dir),
        max_steps=3,
    )
    return agent.run(f"Run a failure-handling trace for: {topic}")


def resolve_provider_name(provider_name: Optional[str]) -> str:
    provider = (provider_name or os.getenv("DEFAULT_PROVIDER") or "mimo").strip().lower()
    provider = PROVIDER_ALIASES.get(provider, provider)
    if provider not in PROVIDER_CHOICES:
        choices = ", ".join(PROVIDER_CHOICES)
        raise SystemExit(f"Unsupported provider '{provider}'. Choose one of: {choices}.")
    return provider


def build_llm_provider(provider_name: str, topic: str) -> LLMProvider:
    provider = resolve_provider_name(provider_name)
    model_name = os.getenv("DEFAULT_MODEL")

    if provider == "scripted":
        return ScriptedProvider(
            scripted_success_responses(topic),
            model_name="scripted-success-trace",
        )

    if provider == "mimo":
        if not os.getenv("MIMO_API_KEY"):
            raise SystemExit(
                "MIMO_API_KEY is required for the default MiMo demo. "
                "Set MIMO_API_KEY in .env, or run the deterministic fallback with "
                "--provider scripted --offline."
            )
        from src.core.mimo_provider import MimoProvider

        return MimoProvider(model_name=model_name or MimoProvider.DEFAULT_MODEL)

    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model_name=model_name or "gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    if provider == "google":
        from src.core.gemini_provider import GeminiProvider

        return GeminiProvider(
            model_name=model_name or "gemini-1.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
        )

    if provider == "local":
        from src.core.local_provider import LocalProvider

        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        return LocalProvider(model_path=model_path)

    raise SystemExit(f"Unsupported provider '{provider}'.")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the Research Gap Analyzer Lite demo.")
    parser.add_argument(
        "--topic",
        default="self-supervised learning for medical image segmentation",
        help="Research topic for the demo.",
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDER_CHOICES,
        default=None,
        help="LLM provider for the success trace. Defaults to DEFAULT_PROVIDER, then mimo.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=False,
        help="Use the deterministic mock paper dataset.",
    )
    parser.add_argument(
        "--online",
        action="store_false",
        dest="offline",
        help="Try arXiv first, with automatic fallback to mock data. This is the default.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for generated artifacts.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    provider_name = resolve_provider_name(args.provider)
    success_answer = run_success_trace(
        args.topic,
        args.offline,
        output_dir,
        provider_name=provider_name,
    )
    failure_answer = run_failure_trace(args.topic, args.offline, output_dir)

    print(f"Success trace final answer ({provider_name}):")
    print(success_answer)
    print()
    print("Failure trace result:")
    print(failure_answer)
    print()
    print(f"Artifacts: {output_dir}")


if __name__ == "__main__":
    main()
