from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from config.settings import settings
from evaluation.dataset import (
    DEFAULT_DATASET_PATH,
    load_examples,
    load_manifest,
    validate_dataset,
)
from evaluation.metrics import deduplicate_ids
from evaluation.run_retrieval_benchmark import (
    measure,
    percentile,
)


EVALUATION_ROOT = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIRECTORY = EVALUATION_ROOT / "results"

INSUFFICIENT_RESPONSE = (
    "Insufficient compliance data found."
)
CITATION_PATTERN = re.compile(r"\[S\d+\]")
CLAIM_SPLIT_PATTERN = re.compile(
    r"(?<=[.!?])\s+|\n+"
)
BULLET_PREFIX_PATTERN = re.compile(
    r"^\s*(?:[-*]|\d+[.)])\s*"
)

LATENCY_STAGES = (
    "retrieval",
    "context_selection",
    "generation",
    "total",
)


def split_claims(answer: str) -> list[str]:
    """Split an answer into citation-bearing claims."""

    claims: list[str] = []

    for candidate in CLAIM_SPLIT_PATTERN.split(answer):
        claim = BULLET_PREFIX_PATTERN.sub(
            "",
            candidate,
        ).strip()

        if claim and any(character.isalnum() for character in claim):
            claims.append(claim)

    return claims


def calculate_citation_coverage(
    answer: str,
) -> float | None:
    """Return the fraction of answered claims with citations."""

    answer = answer.strip()

    if not answer or answer == INSUFFICIENT_RESPONSE:
        return None

    claims = split_claims(answer)

    if not claims:
        return 0.0

    cited_claims = sum(
        bool(CITATION_PATTERN.search(claim))
        for claim in claims
    )

    return cited_claims / len(claims)


def extract_document_safeguards(
    documents: list[dict[str, Any]],
) -> list[str]:
    """Extract a unique safeguard ranking from documents."""

    return deduplicate_ids(
        str(document.get("metadata", {}).get(
            "safeguard_id",
            "",
        ))
        for document in documents
        if document.get("metadata", {}).get(
            "safeguard_id"
        )
    )


def evaluate_generation_result(
    result: dict[str, Any],
    expected_ids: set[str],
    ranked_documents: list[dict[str, Any]],
    selected_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate one generated response without model judging."""

    answer = result.get("answer")
    sources = result.get("sources")
    citation_valid = result.get("citation_valid")
    generation_attempts = result.get(
        "generation_attempts"
    )

    if not isinstance(answer, str) or not answer.strip():
        raise ValueError(
            "Generation result must contain an answer."
        )

    if not isinstance(sources, list):
        raise ValueError(
            "Generation result must contain a source list."
        )

    if not isinstance(citation_valid, bool):
        raise ValueError(
            "Generation result must contain citation_valid."
        )

    if (
        not isinstance(generation_attempts, int)
        or generation_attempts < 0
    ):
        raise ValueError(
            "Generation attempts must be non-negative."
        )

    ranked_ids = extract_document_safeguards(
        ranked_documents
    )
    selected_ids = extract_document_safeguards(
        selected_documents
    )

    source_ids = deduplicate_ids(
        str(source.get("safeguard_id", ""))
        for source in sources
        if isinstance(source, dict)
        and source.get("safeguard_id")
    )

    normalized_answer = answer.strip()
    answered = (
        normalized_answer != INSUFFICIENT_RESPONSE
    )

    return {
        "answered": answered,
        "abstained": not answered,
        "citation_valid": citation_valid,
        "citation_coverage": (
            calculate_citation_coverage(
                normalized_answer
            )
        ),
        "retrieval_hit": bool(
            expected_ids & set(ranked_ids)
        ),
        "context_hit": bool(
            expected_ids & set(selected_ids)
        ),
        "expected_source_hit": bool(
            expected_ids & set(source_ids)
        ),
        "generation_attempts": generation_attempts,
        "ranked_safeguard_ids": ranked_ids,
        "selected_safeguard_ids": selected_ids,
        "source_safeguard_ids": source_ids,
        "source_count": len(sources),
    }


def aggregate_generation_results(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate quality and component latency metrics."""

    if not records:
        raise ValueError(
            "Cannot aggregate an empty generation benchmark."
        )

    question_count = len(records)

    def rate(field_name: str) -> float:
        return statistics.mean(
            float(record[field_name])
            for record in records
        )

    coverage_values = [
        float(record["citation_coverage"])
        for record in records
        if record["citation_coverage"] is not None
    ]

    quality = {
        "question_count": question_count,
        "retrieval_hit_rate": rate("retrieval_hit"),
        "context_hit_rate": rate("context_hit"),
        "answer_rate": rate("answered"),
        "abstention_rate": rate("abstained"),
        "citation_valid_rate": rate(
            "citation_valid"
        ),
        "expected_source_hit_rate": rate(
            "expected_source_hit"
        ),
        "mean_citation_coverage": (
            statistics.mean(coverage_values)
            if coverage_values
            else 0.0
        ),
        "retry_rate": statistics.mean(
            float(
                record["generation_attempts"] > 1
            )
            for record in records
        ),
        "mean_generation_attempts": statistics.mean(
            record["generation_attempts"]
            for record in records
        ),
    }

    latency: dict[str, dict[str, float]] = {}

    for stage in LATENCY_STAGES:
        values = [
            float(record["latency_ms"][stage])
            for record in records
        ]

        latency[stage] = {
            "mean_ms": statistics.mean(values),
            "p95_ms": percentile(values, 0.95),
            "minimum_ms": min(values),
            "maximum_ms": max(values),
        }

    return {
        "quality": quality,
        "latency": latency,
    }


def build_report_paths(
    split: str,
    limit: int | None,
    output_directory: Path,
) -> tuple[Path, Path]:
    """Build report paths without overwriting official results."""

    limit_suffix = (
        f"_limit_{limit}"
        if limit is not None
        else ""
    )

    stem = (
        f"generation_benchmark_{split}"
        f"{limit_suffix}_results"
    )

    return (
        output_directory / f"{stem}.json",
        output_directory / f"{stem}.csv",
    )


def write_csv_report(
    records: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Write one auditable row per generation question."""

    fieldnames = [
        "example_id",
        "category",
        "split",
        "expected_safeguard_ids",
        "ranked_safeguard_ids",
        "selected_safeguard_ids",
        "source_safeguard_ids",
        "answered",
        "abstained",
        "citation_valid",
        "validation_error",
        "citation_coverage",
        "retrieval_hit",
        "context_hit",
        "expected_source_hit",
        "generation_attempts",
        "source_count",
        "retrieval_latency_ms",
        "context_selection_latency_ms",
        "generation_latency_ms",
        "total_latency_ms",
        "answer",
    ]

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for record in records:
            writer.writerow(
                {
                    "example_id": record["example_id"],
                    "category": record["category"],
                    "split": record["split"],
                    "expected_safeguard_ids": ";".join(
                        record[
                            "expected_safeguard_ids"
                        ]
                    ),
                    "ranked_safeguard_ids": ";".join(
                        record[
                            "ranked_safeguard_ids"
                        ]
                    ),
                    "selected_safeguard_ids": ";".join(
                        record[
                            "selected_safeguard_ids"
                        ]
                    ),
                    "source_safeguard_ids": ";".join(
                        record[
                            "source_safeguard_ids"
                        ]
                    ),
                    "answered": record["answered"],
                    "abstained": record["abstained"],
                    "citation_valid": record[
                        "citation_valid"
                    ],
                    "validation_error": (
                        record["validation_error"] or ""
                    ),
                    "citation_coverage": (
                        ""
                        if record["citation_coverage"]
                        is None
                        else round(
                            record[
                                "citation_coverage"
                            ],
                            4,
                        )
                    ),
                    "retrieval_hit": record[
                        "retrieval_hit"
                    ],
                    "context_hit": record[
                        "context_hit"
                    ],
                    "expected_source_hit": record[
                        "expected_source_hit"
                    ],
                    "generation_attempts": record[
                        "generation_attempts"
                    ],
                    "source_count": record[
                        "source_count"
                    ],
                    "retrieval_latency_ms": round(
                        record["latency_ms"][
                            "retrieval"
                        ],
                        4,
                    ),
                    "context_selection_latency_ms": (
                        round(
                            record["latency_ms"][
                                "context_selection"
                            ],
                            4,
                        )
                    ),
                    "generation_latency_ms": round(
                        record["latency_ms"][
                            "generation"
                        ],
                        4,
                    ),
                    "total_latency_ms": round(
                        record["latency_ms"]["total"],
                        4,
                    ),
                    "answer": record["answer"],
                }
            )


def positive_int(value: str) -> int:
    parsed_value = int(value)

    if parsed_value <= 0:
        raise argparse.ArgumentTypeError(
            "limit must be greater than zero."
        )

    return parsed_value


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark grounded generation and pipeline latency."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--split",
        choices=("dev", "test"),
        default="dev",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_RESULTS_DIRECTORY,
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    all_examples = load_examples(arguments.dataset)
    manifest = load_manifest()

    validate_dataset(
        all_examples,
        manifest,
        arguments.dataset,
    )

    examples = [
        example
        for example in all_examples
        if (
            example.split == arguments.split
            and example.answerable
        )
    ]

    if arguments.limit is not None:
        examples = examples[: arguments.limit]

    if not examples:
        raise ValueError(
            "No answerable examples matched the benchmark."
        )

    # Heavy dependencies load only for real benchmark runs.
    from generation.context_selector import (
        SafeguardContextSelector,
    )
    from generation.generator import ComplianceGenerator
    from retrieval.hybrid_retriever import HybridRetriever

    print("Loading end-to-end pipeline...")

    retriever = HybridRetriever()
    context_selector = SafeguardContextSelector()
    generator = ComplianceGenerator()

    print("Warming up retrieval and generation models...")

    warmup_example = examples[0]
    warmup_ranked = retriever.search(
        warmup_example.question,
        k=settings.final_top_k,
    )
    warmup_selected = context_selector.select(
        warmup_ranked
    )
    generator.generate(
        query=warmup_example.question,
        documents=warmup_selected,
    )

    records: list[dict[str, Any]] = []

    for position, example in enumerate(
        examples,
        start=1,
    ):
        print(
            f"[{position}/{len(examples)}] {example.id}"
        )

        total_started_at = perf_counter()

        ranked_documents, retrieval_latency = measure(
            lambda: retriever.search(
                example.question,
                k=settings.final_top_k,
            )
        )

        selected_documents, selection_latency = measure(
            lambda: context_selector.select(
                ranked_documents
            )
        )

        generation_result, generation_latency = measure(
            lambda: generator.generate(
                query=example.question,
                documents=selected_documents,
            )
        )

        total_latency = (
            perf_counter() - total_started_at
        ) * 1000

        metrics = evaluate_generation_result(
            result=generation_result,
            expected_ids=set(
                example.expected_safeguard_ids
            ),
            ranked_documents=ranked_documents,
            selected_documents=selected_documents,
        )

        record = {
            "example_id": example.id,
            "question": example.question,
            "category": example.category,
            "split": example.split,
            "expected_safeguard_ids": (
                example.expected_safeguard_ids
            ),
            "answer": generation_result["answer"],
            "sources": generation_result["sources"],
            "validation_error": (
                generation_result.get(
                    "validation_error"
                )
            ),
            **metrics,
            "latency_ms": {
                "retrieval": retrieval_latency,
                "context_selection": selection_latency,
                "generation": generation_latency,
                "total": total_latency,
            },
        }

        records.append(record)

        print(
            "  citation_valid=",
            record["citation_valid"],
            " expected_source_hit=",
            record["expected_source_hit"],
            " total_ms=",
            f"{total_latency:.2f}",
            sep="",
        )

    summary = aggregate_generation_results(records)

    arguments.output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path, csv_path = build_report_paths(
        split=arguments.split,
        limit=arguments.limit,
        output_directory=arguments.output_directory,
    )

    report = {
        "metadata": {
            "generated_at_utc": (
                datetime.now(timezone.utc).isoformat()
            ),
            "dataset_name": manifest["dataset_name"],
            "dataset_version": manifest[
                "dataset_version"
            ],
            "dataset_file_sha256": manifest[
                "dataset_file_sha256"
            ],
            "corpus_file_sha256": manifest[
                "corpus_file_sha256"
            ],
            "split": arguments.split,
            "limit": arguments.limit,
            "question_count": len(records),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "ollama_model": settings.ollama_model,
            "ollama_temperature": (
                settings.ollama_temperature
            ),
            "final_top_k": settings.final_top_k,
            "warmup_performed": True,
        },
        "summary": summary,
        "questions": records,
    }

    json_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    write_csv_report(records, csv_path)

    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"JSON report: {json_path}")
    print(f"CSV report: {csv_path}")


if __name__ == "__main__":
    main()