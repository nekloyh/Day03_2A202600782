from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence


MOCK_PAPERS: List[Dict[str, Any]] = [
    {
        "paperId": "MOCK-SSL-MEDSEG-001",
        "title": "Contrastive self-supervised pretraining for low-label medical image segmentation",
        "year": 2021,
        "abstract": (
            "This study evaluates contrastive self-supervised pretraining for U-Net style "
            "segmentation on cardiac MRI and abdominal CT. The method improves Dice scores "
            "when only a small fraction of labels is available, but evaluation is limited to "
            "two curated datasets and does not test external scanners."
        ),
        "authors": [{"name": "A. Nguyen"}, {"name": "R. Patel"}],
        "venue": "Mock Medical Imaging Workshop",
        "url": "https://example.org/mock-ssl-medseg-001",
        "externalIds": {},
        "source_mode": "mock",
        "claims": [
            "Contrastive self-supervised pretraining can improve segmentation Dice under low-label settings.",
            "The strongest evidence is for curated cardiac MRI and abdominal CT datasets.",
        ],
        "limitations": [
            "Limited to two curated datasets.",
            "No external scanner or institution validation is reported.",
        ],
        "methods": [
            "contrastive self-supervised learning",
            "U-Net segmentation",
            "low-label evaluation",
        ],
    },
    {
        "paperId": "MOCK-SSL-MEDSEG-002",
        "title": "Masked autoencoding for annotation-efficient organ segmentation",
        "year": 2022,
        "abstract": (
            "Masked image modeling is used to pretrain an encoder before organ segmentation. "
            "The approach reduces annotation needs on abdominal CT and liver MRI benchmarks. "
            "The paper compares against supervised initialization but omits direct comparison "
            "with contrastive pretraining under the same label budgets."
        ),
        "authors": [{"name": "L. Smith"}, {"name": "M. Zhao"}],
        "venue": "Mock MICCAI Track",
        "url": "https://example.org/mock-ssl-medseg-002",
        "externalIds": {},
        "source_mode": "mock",
        "claims": [
            "Masked autoencoding reduces annotation needs for organ segmentation benchmarks.",
            "Pretrained encoders outperform supervised initialization under small label budgets.",
        ],
        "limitations": [
            "No head-to-head comparison with contrastive pretraining under matched budgets.",
            "Evaluation does not include uncertainty calibration.",
        ],
        "methods": [
            "masked autoencoding",
            "encoder pretraining",
            "organ segmentation",
        ],
    },
    {
        "paperId": "MOCK-SSL-MEDSEG-003",
        "title": "Consistency regularization with pseudo-labels for semi-supervised lesion segmentation",
        "year": 2023,
        "abstract": (
            "The method combines consistency regularization with pseudo-label refinement for "
            "lesion segmentation. Results suggest gains when labeled cases are scarce. The "
            "study notes sensitivity to pseudo-label noise and reports only single-center "
            "validation."
        ),
        "authors": [{"name": "E. Garcia"}, {"name": "S. Iqbal"}],
        "venue": "Mock Journal of Imaging AI",
        "url": "https://example.org/mock-ssl-medseg-003",
        "externalIds": {},
        "source_mode": "mock",
        "claims": [
            "Consistency regularization and pseudo-label refinement can help lesion segmentation with scarce labels.",
            "Performance is sensitive to pseudo-label noise.",
        ],
        "limitations": [
            "Single-center validation only.",
            "Pseudo-label noise can degrade segmentation quality.",
        ],
        "methods": [
            "consistency regularization",
            "pseudo-label refinement",
            "semi-supervised segmentation",
        ],
    },
    {
        "paperId": "MOCK-SSL-MEDSEG-004",
        "title": "Federated self-supervised segmentation pretraining across hospitals",
        "year": 2024,
        "abstract": None,
        "authors": [{"name": "N. Kumar"}, {"name": "H. Lee"}],
        "venue": "Mock Federated Health AI Poster",
        "url": "https://example.org/mock-ssl-medseg-004",
        "externalIds": {},
        "source_mode": "mock",
        "claims": [],
        "limitations": [
            "Only metadata is available in this demo dataset; claims cannot be verified from an abstract.",
        ],
        "methods": [
            "federated self-supervised learning",
            "multi-hospital pretraining",
        ],
        "uncertain_fields": ["abstract", "claims"],
    },
    {
        "paperId": "MOCK-SSL-MEDSEG-005",
        "title": "Domain-shift stress testing for self-supervised medical segmentation",
        "year": 2025,
        "abstract": (
            "This benchmark compares self-supervised segmentation pretraining methods under "
            "scanner and institution shift. It finds that reported low-label gains shrink on "
            "external cohorts and recommends explicit calibration and subgroup reporting."
        ),
        "authors": [{"name": "P. Rossi"}, {"name": "T. Williams"}],
        "venue": "Mock Clinical ML Benchmark",
        "url": "https://example.org/mock-ssl-medseg-005",
        "externalIds": {},
        "source_mode": "mock",
        "claims": [
            "Low-label gains from self-supervised pretraining may shrink under external cohort shift.",
            "Scanner and institution shift should be part of segmentation evaluation.",
        ],
        "limitations": [
            "Benchmark coverage is broad but not disease-specific.",
            "The benchmark reports stress-test outcomes but not a new training method.",
        ],
        "methods": [
            "domain-shift benchmark",
            "external cohort validation",
            "calibration review",
        ],
    },
]


def get_mock_papers(
    query: Optional[str] = None,
    limit: int = 5,
    year_range: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    papers = deepcopy(MOCK_PAPERS)

    if year_range:
        start, end = _normalise_year_range(year_range)
        papers = [
            paper
            for paper in papers
            if paper.get("year") is not None and start <= int(paper["year"]) <= end
        ]

    if query:
        terms = [term.lower() for term in query.split() if len(term) > 2]
        if terms:
            ranked = sorted(
                papers,
                key=lambda paper: _score_query_match(paper, terms),
                reverse=True,
            )
            papers = ranked

    return papers[: max(0, int(limit))]


def _normalise_year_range(year_range: Sequence[int]) -> Sequence[int]:
    if len(year_range) != 2:
        return (1900, 2100)
    start, end = int(year_range[0]), int(year_range[1])
    if start > end:
        start, end = end, start
    return (start, end)


def _score_query_match(paper: Dict[str, Any], terms: List[str]) -> int:
    haystack = " ".join(
        [
            str(paper.get("title") or ""),
            str(paper.get("abstract") or ""),
            " ".join(paper.get("methods") or []),
        ]
    ).lower()
    return sum(1 for term in terms if term in haystack)
