from __future__ import annotations

import argparse
import csv
import json
import math
import platform
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
from evaluation.metrics import (
    deduplicate_ids,
    evaluate_ranking,
)
METHODS = (
    "vector",
    "bm25",
    "rrf",
    "hybrid_reranked",
)

K_VALUES = (1, 3, 5)

DEFAULT_RESULTS_DIRECTORY = (
    Path(__file__).resolve().parent / "results"
)


def measure(operation: Any) -> tuple[Any, float]:
    """Run an operation and return its result and latency."""

    started_at = perf_counter()
    result = operation()
    latency_ms = (perf_counter() - started_at) * 1000

    return result, latency_ms


def extract_ranked_safeguards(
    results: list[dict[str, Any]],
) -> list[str]:
    """Convert chunk results to a unique safeguard ranking."""

    return deduplicate_ids(
        str(result["metadata"]["safeguard_id"])
        for result in results
    )


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    """Calculate a linearly interpolated percentile."""

    if not 0.0 <= percentile_value <= 1.0:
        raise ValueError(
            "percentile_value must be between 0 and 1."
        )

    if not values:
        raise ValueError(
            "Percentile requires at least one value."
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        (len(ordered) - 1)
        * percentile_value
    )
    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return ordered[lower_index]

    fraction = position - lower_index

    return (
        ordered[lower_index]
        + (
            ordered[upper_index]
            - ordered[lower_index]
        )
        * fraction
    )


def aggregate_results(
    question_results: list[dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    """Average quality and latency metrics by method."""

    if not question_results:
        raise ValueError(
            "Cannot aggregate an empty benchmark."
        )

    summary: dict[
        str,
        dict[str, float | int],
    ] = {}

    for method in METHODS:
        method_records = [
            result["methods"][method]
            for result in question_results
        ]

        metric_names = method_records[0][
            "metrics"
        ].keys()

        method_summary: dict[str, float | int] = {
            "question_count": len(method_records)
        }

        for metric_name in metric_names:
            method_summary[metric_name] = (
                statistics.mean(
                    record["metrics"][metric_name]
                    for record in method_records
                )
            )

        latencies = [
            record["latency_ms"]
            for record in method_records
        ]

        method_summary["mean_latency_ms"] = (
            statistics.mean(latencies)
        )
        method_summary["p95_latency_ms"] = percentile(
            latencies,
            0.95,
        )

        summary[method] = method_summary

    return summary


def write_csv_report(
    question_results: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Write one CSV row per question and retrieval method."""

    metric_names = [
        "recall@1",
        "hit_rate@1",
        "recall@3",
        "hit_rate@3",
        "recall@5",
        "hit_rate@5",
        "mrr@5",
        "ndcg@5",
    ]

    fieldnames = [
        "example_id",
        "category",
        "split",
        "method",
        "expected_safeguard_ids",
        "ranked_safeguard_ids",
        "top_chunk_ids",
        "latency_ms",
        *metric_names,
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

        for question_result in question_results:
            for method in METHODS:
                method_result = question_result[
                    "methods"
                ][method]

                row = {
                    "example_id": question_result[
                        "example_id"
                    ],
                    "category": question_result[
                        "category"
                    ],
                    "split": question_result["split"],
                    "method": method,
                    "expected_safeguard_ids": ";".join(
                        question_result[
                            "expected_safeguard_ids"
                        ]
                    ),
                    "ranked_safeguard_ids": ";".join(
                        method_result[
                            "ranked_safeguard_ids"
                        ]
                    ),
                    "top_chunk_ids": ";".join(
                        method_result["top_chunk_ids"]
                    ),
                    "latency_ms": round(
                        method_result["latency_ms"],
                        4,
                    ),
                }

                row.update(method_result["metrics"])
                writer.writerow(row)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark CIS safeguard retrieval methods."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )

    parser.add_argument(
        "--split",
        choices=("dev", "test", "all"),
        default="dev",
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
    validate_dataset(all_examples, manifest)

    examples = [
        example
        for example in all_examples
        if (
            arguments.split == "all"
            or example.split == arguments.split
        )
        and example.answerable
    ]

    if not examples:
        raise ValueError(
            "No answerable examples matched the selected split."
        )

    # Import ML dependencies only when running the benchmark.
    # Unit tests for report utilities should remain lightweight.
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.reranker import Reranker
    from retrieval.rrf import ReciprocalRankFusion
    from retrieval.vector_retriever import VectorRetriever

    print("Loading retrieval models...")

    vector = VectorRetriever()
    bm25 = BM25Retriever()
    rrf = ReciprocalRankFusion(k=settings.rrf_k)
    reranker = Reranker()

    print("Warming up models...")

    warmup_results = vector.search(
        "enterprise security inventory",
        k=1,
    )

    if warmup_results:
        reranker.rerank(
            query="enterprise security inventory",
            documents=warmup_results,
            top_k=1,
        )

    question_results: list[dict[str, Any]] = []

    total_questions = len(examples)

    for question_number, example in enumerate(
        examples,
        start=1,
    ):
        print(
            f"[{question_number}/{total_questions}] "
            f"{example.id}"
        )

        vector_results, vector_latency = measure(
            lambda: vector.search(
                example.question,
                k=settings.vector_candidates,
            )
        )

        bm25_results, bm25_latency = measure(
            lambda: bm25.search(
                example.question,
                k=settings.bm25_candidates,
            )
        )

        rrf_results, fusion_latency = measure(
            lambda: rrf.fuse(
                vector_results,
                bm25_results,
            )
        )

        if rrf_results:
            reranked_results, reranker_latency = measure(
                lambda: reranker.rerank(
                    query=example.question,
                    documents=rrf_results,
                    top_k=len(rrf_results),
                )
            )
        else:
            reranked_results = []
            reranker_latency = 0.0

        method_results = {
            "vector": (
                vector_results,
                vector_latency,
            ),
            "bm25": (
                bm25_results,
                bm25_latency,
            ),
            "rrf": (
                rrf_results,
                (
                    vector_latency
                    + bm25_latency
                    + fusion_latency
                ),
            ),
            "hybrid_reranked": (
                reranked_results,
                (
                    vector_latency
                    + bm25_latency
                    + fusion_latency
                    + reranker_latency
                ),
            ),
        }

        expected_ids = set(
            example.expected_safeguard_ids
        )

        evaluated_methods: dict[
            str,
            dict[str, Any],
        ] = {}

        for method, (
            results,
            latency_ms,
        ) in method_results.items():
            ranked_safeguard_ids = (
                extract_ranked_safeguards(results)
            )

            metrics = evaluate_ranking(
                ranked_ids=ranked_safeguard_ids,
                expected_ids=expected_ids,
                k_values=K_VALUES,
            )

            evaluated_methods[method] = {
                "ranked_safeguard_ids": (
                    ranked_safeguard_ids[
                        : max(K_VALUES)
                    ]
                ),
                "top_chunk_ids": [
                    result["chunk_id"]
                    for result in results[
                        : max(K_VALUES)
                    ]
                ],
                "latency_ms": latency_ms,
                "metrics": metrics,
            }

        question_results.append(
            {
                "example_id": example.id,
                "question": example.question,
                "category": example.category,
                "split": example.split,
                "expected_safeguard_ids": (
                    example.expected_safeguard_ids
                ),
                "methods": evaluated_methods,
            }
        )

        hybrid_top_ids = evaluated_methods[
            "hybrid_reranked"
        ]["ranked_safeguard_ids"][:3]

        print(
            "  Gold:",
            example.expected_safeguard_ids,
            "| Hybrid top 3:",
            hybrid_top_ids,
        )

    summary = aggregate_results(question_results)

    report = {
        "metadata": {
            "generated_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "dataset_name": manifest["dataset_name"],
            "dataset_version": manifest[
                "dataset_version"
            ],
            "split": arguments.split,
            "corpus_file_sha256": manifest[
                "corpus_file_sha256"
            ],
            "question_count": len(examples),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
            "vector_candidates": (
                settings.vector_candidates
            ),
            "bm25_candidates": settings.bm25_candidates,
            "rrf_k": settings.rrf_k,
        },
        "summary": summary,
        "questions": question_results,
    }

    arguments.output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        arguments.output_directory
        / "retrieval_seed_results.json"
    )
    csv_path = (
        arguments.output_directory
        / "retrieval_seed_results.csv"
    )

    json_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    write_csv_report(question_results, csv_path)

    print("\nBenchmark summary:")

    for method in METHODS:
        values = summary[method]

        print(
            f"{method}: "
            f"Recall@1={values['recall@1']:.3f}, "
            f"Recall@3={values['recall@3']:.3f}, "
            f"Recall@5={values['recall@5']:.3f}, "
            f"MRR@5={values['mrr@5']:.3f}, "
            f"nDCG@5={values['ndcg@5']:.3f}, "
            f"Mean latency="
            f"{values['mean_latency_ms']:.2f} ms, "
            f"P95 latency="
            f"{values['p95_latency_ms']:.2f} ms"
        )

    print(f"\nJSON report: {json_path}")
    print(f"CSV report: {csv_path}")


if __name__ == "__main__":
    main()