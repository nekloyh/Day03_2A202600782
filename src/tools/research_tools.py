import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from src.telemetry.logger import logger
from src.tools.mock_papers import get_mock_papers


ARXIV_API_URL = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def search_papers(
    query: str,
    limit: int = 5,
    year_range: Optional[Sequence[int]] = None,
    offline: bool = False,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search arXiv when available, otherwise return the bundled mock dataset.

    The offline path is deterministic and is the default path used by tests.
    """
    limit = max(1, int(limit))
    parsed_year_range = _parse_year_range(year_range)

    if offline:
        return _mark_source_mode(
            get_mock_papers(query=query, limit=limit, year_range=parsed_year_range),
            "mock",
        )

    try:
        import requests

        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
        }

        response = requests.get(ARXIV_API_URL, params=params, timeout=timeout)
        response.raise_for_status()
        papers = [
            _normalise_arxiv_entry(entry)
            for entry in ElementTree.fromstring(response.text).findall(f"{_ATOM_NS}entry")
        ]
        papers = [paper for paper in papers if paper.get("paperId") and paper.get("title")]
        if parsed_year_range:
            start, end = parsed_year_range
            papers = [
                paper
                for paper in papers
                if paper.get("year") is not None and start <= int(paper["year"]) <= end
            ]
        if papers:
            return papers[:limit]
        _log_search_fallback(
            query=query,
            fallback_reason="empty_result",
            error_type=None,
            error_message=None,
        )
    except Exception as exc:
        _log_search_fallback(
            query=query,
            fallback_reason="request_failed",
            error_type=exc.__class__.__name__,
            error_message=_safe_error_message(exc),
        )

    return _mark_source_mode(
        get_mock_papers(query=query, limit=limit, year_range=parsed_year_range),
        "mock_fallback",
    )


def extract_evidence_cards(
    papers: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if papers is None:
        papers = get_mock_papers()

    cards = []
    for index, paper in enumerate(papers):
        paper_id = paper.get("paperId") or _fallback_paper_id(paper, index)
        title = paper.get("title") or "Untitled paper"
        year = paper.get("year")
        abstract = paper.get("abstract")
        authors = _author_names(paper.get("authors") or [])

        claims = list(paper.get("claims") or _extract_claims(abstract))
        methods = list(paper.get("methods") or _extract_methods(title, abstract))
        limitations = list(paper.get("limitations") or _extract_limitations(abstract))
        uncertain_fields = list(dict.fromkeys(paper.get("uncertain_fields") or []))

        if not year:
            uncertain_fields.append("year")
        if not abstract:
            uncertain_fields.append("abstract")
        if not authors:
            uncertain_fields.append("authors")
        if not claims:
            uncertain_fields.append("claims")
        if not methods:
            uncertain_fields.append("methods")
        if not limitations:
            limitations = ["No explicit limitation found in available metadata."]
            uncertain_fields.append("limitations")

        source_input = {
            **paper,
            "paperId": paper_id,
            "title": title,
            "year": year,
        }
        cards.append(
            {
                "paperId": paper_id,
                "title": title,
                "year": year,
                "abstract": abstract,
                "authors": authors,
                "venue": paper.get("venue"),
                "url": paper.get("url"),
                "externalIds": paper.get("externalIds") or {},
                "source_mode": paper.get("source_mode") or "unknown",
                "claims": claims,
                "limitations": limitations,
                "methods": methods,
                "uncertain_fields": list(dict.fromkeys(uncertain_fields)),
                "source": _source_ref(source_input),
            }
        )

    return cards


def compare_and_find_gaps(
    evidence_cards: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if evidence_cards is None:
        evidence_cards = extract_evidence_cards()

    matrix = [_matrix_row(card) for card in evidence_cards]
    gaps = _candidate_gaps(evidence_cards)

    return {
        "matrix": matrix,
        "candidate_gaps": gaps,
        "coverage": {
            "paper_count": len(evidence_cards),
            "uncertain_card_count": sum(1 for card in evidence_cards if card.get("uncertain_fields")),
            "all_gaps_have_sources": all(bool(gap.get("sources")) for gap in gaps),
            "all_claims_have_sources": all(
                bool(claim.get("source"))
                for row in matrix
                for claim in row.get("claims", [])
            ),
        },
    }


def _normalise_arxiv_entry(entry: ElementTree.Element) -> Dict[str, Any]:
    abs_url = _arxiv_text(entry, f"{_ATOM_NS}id")
    arxiv_id = _arxiv_id_from_url(abs_url)
    primary = entry.find(f"{_ARXIV_NS}primary_category")
    venue = primary.get("term") if primary is not None else None

    authors = [
        {"name": name}
        for author in entry.findall(f"{_ATOM_NS}author")
        for name in [_arxiv_text(author, f"{_ATOM_NS}name")]
        if name
    ]

    return {
        "paperId": arxiv_id or abs_url,
        "title": _collapse_whitespace(_arxiv_text(entry, f"{_ATOM_NS}title")),
        "year": _arxiv_year(_arxiv_text(entry, f"{_ATOM_NS}published")),
        "abstract": _collapse_whitespace(_arxiv_text(entry, f"{_ATOM_NS}summary")),
        "authors": authors,
        "venue": venue or "arXiv",
        "url": abs_url,
        "citationCount": None,
        "externalIds": {"ArXiv": arxiv_id} if arxiv_id else {},
        "source_mode": "arxiv",
    }


def _arxiv_text(element: Optional[ElementTree.Element], path: str) -> Optional[str]:
    if element is None:
        return None
    found = element.find(path)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _arxiv_id_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    match = re.search(r"arxiv\.org/abs/(.+)$", url)
    return match.group(1) if match else None


def _arxiv_year(published: Optional[str]) -> Optional[int]:
    if not published:
        return None
    match = re.match(r"(\d{4})", published)
    return int(match.group(1)) if match else None


def _collapse_whitespace(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    return re.sub(r"\s+", " ", text).strip()


def _mark_source_mode(papers: List[Dict[str, Any]], source_mode: str) -> List[Dict[str, Any]]:
    return [{**paper, "source_mode": source_mode} for paper in papers]


def _log_search_fallback(
    query: str,
    fallback_reason: str,
    error_type: Optional[str],
    error_message: Optional[str],
) -> None:
    logger.log_event(
        "SEARCH_FALLBACK",
        {
            "query": query,
            "fallback_reason": fallback_reason,
            "error_type": error_type,
            "error_message": error_message,
            "source_mode": "mock_fallback",
        },
    )


def _safe_error_message(exc: Exception, max_chars: int = 240) -> str:
    message = str(exc).replace("\n", " ").strip()
    if len(message) <= max_chars:
        return message
    return message[:max_chars] + "...[truncated]"


def _parse_year_range(year_range: Optional[Sequence[int]]) -> Optional[Tuple[int, int]]:
    if not year_range:
        return None

    if isinstance(year_range, str):
        parts = re.findall(r"\d{4}", year_range)
        if len(parts) < 2:
            return None
        start, end = int(parts[0]), int(parts[1])
    else:
        if len(year_range) != 2:
            return None
        start, end = int(year_range[0]), int(year_range[1])

    if start > end:
        start, end = end, start
    return (start, end)


def _author_names(authors: Iterable[Any]) -> List[str]:
    names = []
    for author in authors:
        if isinstance(author, dict):
            name = author.get("name")
        else:
            name = str(author)
        if name:
            names.append(name)
    return names


def _fallback_paper_id(paper: Dict[str, Any], index: int) -> str:
    title = re.sub(r"[^A-Za-z0-9]+", "-", str(paper.get("title") or "paper")).strip("-")
    return f"LOCAL-{index + 1}-{title[:32].upper()}"


def _extract_claims(abstract: Optional[str]) -> List[str]:
    if not abstract:
        return []

    claim_terms = [
        "improve",
        "outperform",
        "reduce",
        "gain",
        "robust",
        "suggest",
        "finds",
        "helps",
    ]
    claims = [
        sentence
        for sentence in _sentences(abstract)
        if any(term in sentence.lower() for term in claim_terms)
    ]
    return claims[:3]


def _extract_methods(title: str, abstract: Optional[str]) -> List[str]:
    text = f"{title} {abstract or ''}".lower()
    method_terms = {
        "contrastive": "contrastive self-supervised learning",
        "masked": "masked autoencoding",
        "autoencoding": "masked autoencoding",
        "pseudo-label": "pseudo-labeling",
        "consistency": "consistency regularization",
        "federated": "federated learning",
        "domain-shift": "domain-shift benchmark",
        "external": "external validation",
        "calibration": "calibration review",
        "u-net": "U-Net segmentation",
        "segmentation": "segmentation",
    }
    methods = [label for term, label in method_terms.items() if term in text]
    return list(dict.fromkeys(methods))


def _extract_limitations(abstract: Optional[str]) -> List[str]:
    if not abstract:
        return []

    limitation_terms = [
        "limited",
        "single-center",
        "omits",
        "does not",
        "sensitive",
        "shrink",
        "not",
    ]
    limitations = [
        sentence
        for sentence in _sentences(abstract)
        if any(term in sentence.lower() for term in limitation_terms)
    ]
    return limitations[:3]


def _sentences(text: str) -> List[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


def _matrix_row(card: Dict[str, Any]) -> Dict[str, Any]:
    source = _source_ref(card)
    claims = [
        {
            "claim": claim,
            "source": source,
        }
        for claim in card.get("claims", [])
    ]
    limitations = [
        {
            "limitation": limitation,
            "source": source,
        }
        for limitation in card.get("limitations", [])
    ]

    return {
        "paperId": card.get("paperId"),
        "title": card.get("title"),
        "year": card.get("year"),
        "methods": card.get("methods", []),
        "claims": claims,
        "limitations": limitations,
        "uncertain_fields": card.get("uncertain_fields", []),
        "evidence_quality": _evidence_quality(card),
    }


def _candidate_gaps(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []

    external_sources = _sources_for_terms(
        cards,
        ["external", "scanner", "institution", "single-center", "curated"],
    )
    if external_sources:
        gaps.append(
            _gap(
                "GAP-001",
                "External validation under scanner and institution shift",
                (
                    "Available evidence mentions curated datasets, single-center evaluation, "
                    "or shrinking gains under external cohort shift."
                ),
                external_sources,
                "medical image segmentation self-supervised pretraining external validation scanner shift",
                cards,
            )
        )

    comparison_sources = _sources_for_terms(
        cards,
        ["head-to-head", "matched budgets", "benchmark", "compares"],
    )
    if comparison_sources:
        gaps.append(
            _gap(
                "GAP-002",
                "Matched-budget comparison across SSL pretraining strategies",
                (
                    "The evidence suggests that contrastive, masked autoencoding, pseudo-label, "
                    "and benchmark studies are not always compared under the same label budgets."
                ),
                comparison_sources,
                "contrastive masked autoencoder pseudo-label medical segmentation matched label budget comparison",
                cards,
            )
        )

    weak_sources = [
        _source_ref(card)
        for card in cards
        if card.get("uncertain_fields")
        or _evidence_quality(card) == "weak"
        or _contains_any(card, ["uncertainty", "calibration", "claims cannot be verified"])
    ]
    if weak_sources:
        gaps.append(
            _gap(
                "GAP-003",
                "Uncertainty-aware claims for low-evidence or metadata-only studies",
                (
                    "At least one evidence card has missing or weak fields, so claims about "
                    "generalization, calibration, or federated settings should remain uncertain "
                    "until full text or stronger metadata is checked."
                ),
                _dedupe_sources(weak_sources),
                "federated self-supervised medical segmentation uncertainty calibration evidence gap",
                cards,
                force_uncertain=True,
            )
        )

    return gaps


def _gap(
    gap_id: str,
    gap: str,
    rationale: str,
    sources: List[Dict[str, Any]],
    validation_query: str,
    cards: List[Dict[str, Any]],
    force_uncertain: bool = False,
) -> Dict[str, Any]:
    source_ids = {source["paperId"] for source in sources}
    source_cards = [card for card in cards if card.get("paperId") in source_ids]
    confidence = "uncertain" if force_uncertain else _gap_confidence(source_cards)
    return {
        "id": gap_id,
        "gap": gap,
        "rationale": rationale,
        "sources": _dedupe_sources(sources),
        "confidence": confidence,
        "validation_query": validation_query,
    }


def _gap_confidence(source_cards: List[Dict[str, Any]]) -> str:
    if not source_cards:
        return "uncertain"
    if any(_evidence_quality(card) == "weak" for card in source_cards):
        return "uncertain"
    if len(source_cards) >= 2:
        return "medium"
    return "uncertain"


def _sources_for_terms(cards: List[Dict[str, Any]], terms: List[str]) -> List[Dict[str, Any]]:
    sources = [_source_ref(card) for card in cards if _contains_any(card, terms)]
    return _dedupe_sources(sources)


def _contains_any(card: Dict[str, Any], terms: List[str]) -> bool:
    text = " ".join(
        [
            str(card.get("title") or ""),
            str(card.get("abstract") or ""),
            " ".join(card.get("methods") or []),
            " ".join(card.get("claims") or []),
            " ".join(card.get("limitations") or []),
        ]
    ).lower()
    return any(term.lower() in text for term in terms)


def _source_ref(card: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "paperId": card.get("paperId"),
        "title": card.get("title"),
        "year": card.get("year"),
        "url": card.get("url"),
        "venue": card.get("venue"),
        "externalIds": card.get("externalIds") or {},
        "source_mode": card.get("source_mode") or "unknown",
    }


def _dedupe_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for source in sources:
        key = source.get("paperId") or source.get("title")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _evidence_quality(card: Dict[str, Any]) -> str:
    uncertain = set(card.get("uncertain_fields") or [])
    if {"abstract", "claims"}.intersection(uncertain):
        return "weak"
    if uncertain:
        return "partial"
    return "supported"
