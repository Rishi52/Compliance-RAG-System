import argparse
from pathlib import Path
from typing import Any

import pytest

from evaluation.run_generation_benchmark import (
    INSUFFICIENT_RESPONSE,
    aggregate_generation_results,
    build_report_paths,
    calculate_citation_coverage,
    evaluate_generation_result,
    extract_document_safeguards,
    positive_int,
)


def make_document(
    safeguard_id: str,
) -> dict[str, Any]:
    return {
        "chunk_id": f"doc:{safeguard_id}:000",
        "content": "Synthetic evidence.",
        "metadata": {
            "safeguard_id": safeguard_id,
        },
    }


def make_result(
    answer: str = "Maintain inventory [S1].",
    sources: list[dict[str, Any]] | None = None,
    attempts: int = 1,
) -> dict[str, Any]:
    if sources is None:
        sources = [
            {
                "source_id": "S1",
                "safeguard_id": "1.1",
            }
        ]

    return {
        "answer": answer,
        "sources": sources,
        "citation_valid": True,
        "generation_attempts": attempts,
    }


def test_full_citation_coverage() -> None:
    answer = (
        "Maintain the inventory [S1]. "
        "Review it regularly [S1]."
    )

    assert calculate_citation_coverage(answer) == 1.0


def test_partial_citation_coverage() -> None:
    answer = (
        "Maintain the inventory [S1]. "
        "Review it regularly."
    )

    assert calculate_citation_coverage(answer) == 0.5


def test_abstention_has_no_citation_coverage() -> None:
    assert (
        calculate_citation_coverage(
            INSUFFICIENT_RESPONSE
        )
        is None
    )


def test_document_safeguards_are_deduplicated() -> None:
    documents = [
        make_document("1.1"),
        make_document("1.1"),
        make_document("2.1"),
    ]

    assert extract_document_safeguards(
        documents
    ) == ["1.1", "2.1"]


def test_generation_result_records_grounding_hits() -> None:
    metrics = evaluate_generation_result(
        result=make_result(),
        expected_ids={"1.1"},
        ranked_documents=[make_document("1.1")],
        selected_documents=[make_document("1.1")],
    )

    assert metrics["answered"] is True
    assert metrics["abstained"] is False
    assert metrics["retrieval_hit"] is True
    assert metrics["context_hit"] is True
    assert metrics["expected_source_hit"] is True
    assert metrics["citation_coverage"] == 1.0


def test_generation_result_records_abstention() -> None:
    metrics = evaluate_generation_result(
        result=make_result(
            answer=INSUFFICIENT_RESPONSE,
            sources=[],
            attempts=2,
        ),
        expected_ids={"1.1"},
        ranked_documents=[make_document("1.1")],
        selected_documents=[make_document("1.1")],
    )

    assert metrics["answered"] is False
    assert metrics["abstained"] is True
    assert metrics["citation_coverage"] is None
    assert metrics["generation_attempts"] == 2


def test_aggregate_generation_results() -> None:
    answered = evaluate_generation_result(
        result=make_result(),
        expected_ids={"1.1"},
        ranked_documents=[make_document("1.1")],
        selected_documents=[make_document("1.1")],
    )
    answered["latency_ms"] = {
        "retrieval": 10.0,
        "context_selection": 1.0,
        "generation": 100.0,
        "total": 111.0,
    }

    abstained = evaluate_generation_result(
        result=make_result(
            answer=INSUFFICIENT_RESPONSE,
            sources=[],
            attempts=2,
        ),
        expected_ids={"1.1"},
        ranked_documents=[make_document("1.1")],
        selected_documents=[make_document("1.1")],
    )
    abstained["latency_ms"] = {
        "retrieval": 20.0,
        "context_selection": 2.0,
        "generation": 200.0,
        "total": 222.0,
    }

    summary = aggregate_generation_results(
        [answered, abstained]
    )

    assert summary["quality"]["question_count"] == 2
    assert summary["quality"]["answer_rate"] == 0.5
    assert (
        summary["quality"]["citation_valid_rate"]
        == 1.0
    )
    assert (
        summary["quality"][
            "expected_source_hit_rate"
        ]
        == 0.5
    )
    assert (
        summary["quality"][
            "mean_citation_coverage"
        ]
        == 1.0
    )
    assert summary["quality"]["retry_rate"] == 0.5
    assert (
        summary["latency"]["retrieval"]["mean_ms"]
        == 15.0
    )


def test_empty_generation_results_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="empty generation benchmark",
    ):
        aggregate_generation_results([])


def test_report_paths_preserve_limited_runs(
    tmp_path: Path,
) -> None:
    json_path, csv_path = build_report_paths(
        split="dev",
        limit=3,
        output_directory=tmp_path,
    )

    assert json_path.name == (
        "generation_benchmark_dev_limit_3_results.json"
    )
    assert csv_path.name == (
        "generation_benchmark_dev_limit_3_results.csv"
    )


def test_positive_int_rejects_zero() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")