import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.tools.research_tools import compare_and_find_gaps


DEFAULT_OUTPUT_DIR = Path("outputs/research_gap_analyzer_lite")


def write_research_artifacts(
    evidence_cards: List[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]] = None,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    topic: str = "self-supervised learning for medical image segmentation",
) -> Dict[str, str]:
    comparison = comparison or compare_and_find_gaps(evidence_cards)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    evidence_cards_path = output_path / "evidence_cards.json"
    comparison_matrix_path = output_path / "comparison_matrix.md"
    gap_report_path = output_path / "gap_analysis_report.md"

    evidence_cards_path.write_text(
        json.dumps(evidence_cards, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    comparison_matrix_path.write_text(
        _render_comparison_matrix(comparison),
        encoding="utf-8",
    )
    gap_report_path.write_text(
        _render_gap_report(evidence_cards, comparison, topic=topic),
        encoding="utf-8",
    )

    return {
        "gap_analysis_report": str(gap_report_path),
        "comparison_matrix": str(comparison_matrix_path),
        "evidence_cards": str(evidence_cards_path),
    }


def _render_comparison_matrix(comparison: Dict[str, Any]) -> str:
    rows = comparison.get("matrix", [])
    lines = [
        "# Comparison Matrix",
        "",
        "| Paper | Year | Methods | Claims | Limitations | Evidence quality |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        claims = [
            f"{claim.get('claim')} [{_source_label(claim.get('source') or {})}]"
            for claim in row.get("claims", [])
        ]
        limitations = [
            f"{limitation.get('limitation')} [{_source_label(limitation.get('source') or {})}]"
            for limitation in row.get("limitations", [])
        ]
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_md(f"{row.get('title')} ({row.get('paperId')})"),
                    _escape_md(row.get("year") or "n/a"),
                    _escape_md(_join(row.get("methods"))),
                    _escape_md(_join(claims)),
                    _escape_md(_join(limitations)),
                    _escape_md(row.get("evidence_quality") or "unknown"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Candidate Gaps", ""])
    for gap in comparison.get("candidate_gaps", []):
        lines.extend(
            [
                f"### {gap.get('id')}: {gap.get('gap')}",
                "",
                f"- Confidence: `{gap.get('confidence')}`",
                f"- Rationale: {gap.get('rationale')}",
                f"- Sources: {_join([_source_label(source) for source in gap.get('sources', [])])}",
                f"- Validation query: `{gap.get('validation_query')}`",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _render_gap_report(
    evidence_cards: List[Dict[str, Any]],
    comparison: Dict[str, Any],
    topic: str,
) -> str:
    coverage = comparison.get("coverage", {})
    gaps = comparison.get("candidate_gaps", [])
    uncertain_cards = [card for card in evidence_cards if card.get("uncertain_fields")]
    uncertain_gaps = [gap for gap in gaps if gap.get("confidence") == "uncertain"]

    lines = [
        "# Research Gap Analysis Report",
        "",
        "## Scope",
        "",
        f"Topic: {topic}",
        "Mode: MVP Lite evidence synthesis with arXiv best-effort search and offline fallback.",
        f"Source modes: {_source_mode_summary(evidence_cards)}",
        f"Fallback/mock status: {_fallback_status(evidence_cards)}",
        "",
        "## Coverage Check",
        "",
        f"- Evidence cards: {coverage.get('paper_count', len(evidence_cards))}",
        f"- Cards with uncertain fields: {coverage.get('uncertain_card_count', len(uncertain_cards))}",
        f"- All extracted claims have source references: {_yes_no(coverage.get('all_claims_have_sources'))}",
        f"- All candidate gaps have source references: {_yes_no(coverage.get('all_gaps_have_sources'))}",
        "",
        "## Candidate Gaps",
        "",
    ]

    for gap in gaps:
        lines.extend(
            [
                f"### {gap.get('id')}: {gap.get('gap')}",
                "",
                f"Confidence: `{gap.get('confidence')}`",
                "",
                gap.get("rationale", ""),
                "",
                f"Sources: {_join([_source_label(source) for source in gap.get('sources', [])])}",
                "",
                "Gap validation query:",
                "",
                f"`{gap.get('validation_query')}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Uncertainty Notes",
            "",
        ]
    )
    if uncertain_cards:
        for card in uncertain_cards:
            fields = _join(card.get("uncertain_fields"))
            lines.append(f"- {_source_label(card)} has uncertain fields: {fields}")
    else:
        lines.append("- No uncertain fields were detected in the evidence cards.")

    lines.extend(
        [
            "",
            "## Final Self-Review",
            "",
            f"- Unsupported gaps marked uncertain: {_yes_no(bool(uncertain_gaps))}",
            f"- Every listed gap includes at least one source: {_yes_no(all(bool(gap.get('sources')) for gap in gaps))}",
            "- Full-text PDF review, citation graph expansion, and human expert validation are outside this MVP.",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def _join(values: Any) -> str:
    if not values:
        return "n/a"
    if isinstance(values, str):
        return values
    return "; ".join(str(value) for value in values if value)


def _source_label(source: Dict[str, Any]) -> str:
    paper_id = source.get("paperId") or "unknown-id"
    title = source.get("title") or "untitled"
    year = source.get("year") or "n/a"
    parts = [paper_id, title, str(year)]
    venue = source.get("venue")
    source_mode = source.get("source_mode")
    url = source.get("url")
    external_ids = source.get("externalIds") or {}

    if venue:
        parts.append(f"venue: {venue}")
    if source_mode:
        parts.append(f"source: {source_mode}")
    if url:
        parts.append(f"url: {url}")
    if external_ids:
        rendered_ids = ", ".join(
            f"{key}: {value}" for key, value in sorted(external_ids.items()) if value
        )
        if rendered_ids:
            parts.append(f"external IDs: {rendered_ids}")

    return ", ".join(parts)


def _source_mode_summary(evidence_cards: List[Dict[str, Any]]) -> str:
    counts: Dict[str, int] = {}
    for card in evidence_cards:
        source = card.get("source") or {}
        source_mode = source.get("source_mode") or card.get("source_mode") or "unknown"
        counts[source_mode] = counts.get(source_mode, 0) + 1

    if not counts:
        return "none"

    return ", ".join(
        f"{source_mode} ({count})" for source_mode, count in sorted(counts.items())
    )


def _fallback_status(evidence_cards: List[Dict[str, Any]]) -> str:
    modes = {
        (card.get("source") or {}).get("source_mode") or card.get("source_mode") or "unknown"
        for card in evidence_cards
    }
    if "mock_fallback" in modes:
        return "arXiv failed or returned no usable results; mock fallback evidence is clearly marked."
    if "mock" in modes:
        return "Offline deterministic mock evidence is clearly marked."
    if modes == {"arxiv"}:
        return "arXiv evidence was used without mock fallback."
    return f"Mixed or unknown source modes: {_join(sorted(modes))}"


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"
