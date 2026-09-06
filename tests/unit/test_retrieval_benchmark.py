import json
from pathlib import Path
from typing import Any

import pytest

from evaluation.run_retrieval_benchmark import (
    METHODS,
    aggregate_results,
    build_report_paths,
    extract_ranked_safeguards,
    percentile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "retrieval_benchmark_dev_results.json"
)

REQUIRED_METADATA_FIELDS = {
    "generated_at_utc",
    "dataset_name",
    "dataset_version",
    "split",
    "corpus_file_sha256",
    "question_count",
    "python_version",
    "platform",
    "embedding_model",
    "reranker_model",
    "vector_candidates",
    "bm25_candidates",
    "rrf_k",
    "dataset_file_sha256",
}

REQUIRED_METRIC_FIELDS = {
    "recall@1",
    "hit_rate@1",
    "recall@3",
    "hit_rate@3",
    "recall@5",
    "hit_rate@5",
    "mrr@5",
    "ndcg@5",
}


def load_saved_report() -> dict[str, Any]:
    return json.loads(
        REPORT_PATH.read_text(encoding="utf-8")
    )


def build_method_result(
    metric_value: float,
    latency_ms: float,
) -> dict[str, Any]:
    return {
        "metrics": {
            "recall@1": metric_value,
        },
        "latency_ms": latency_ms,
    }


def test_extract_ranked_safeguards_removes_duplicates() -> None:
    results = [
        {"metadata": {"safeguard_id": "1.1"}},
        {"metadata": {"safeguard_id": "1.1"}},
        {"metadata": {"safeguard_id": "1.4"}},
    ]

    assert extract_ranked_safeguards(results) == [
        "1.1",
        "1.4",
    ]


def test_percentile_interpolates_values() -> None:
    result = percentile(
        [10.0, 20.0, 30.0, 40.0],
        0.5,
    )

    assert result == pytest.approx(25.0)


def test_percentile_supports_single_value() -> None:
    assert percentile([12.5], 0.95) == 12.5


def test_percentile_rejects_empty_values() -> None:
    with pytest.raises(
        ValueError,
        match="at least one value",
    ):
        percentile([], 0.95)


@pytest.mark.parametrize(
    "percentile_value",
    [-0.1, 1.1],
)
def test_percentile_rejects_invalid_range(
    percentile_value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 1",
    ):
        percentile([10.0], percentile_value)


def test_aggregate_results_averages_metrics_and_latency() -> None:
    first_methods = {
        method: build_method_result(1.0, 10.0)
        for method in METHODS
    }
    second_methods = {
        method: build_method_result(0.0, 20.0)
        for method in METHODS
    }

    summary = aggregate_results(
        [
            {"methods": first_methods},
            {"methods": second_methods},
        ]
    )

    for method in METHODS:
        assert summary[method]["question_count"] == 2
        assert summary[method]["recall@1"] == 0.5
        assert summary[method][
            "mean_latency_ms"
        ] == pytest.approx(15.0)
        assert summary[method][
            "p95_latency_ms"
        ] == pytest.approx(19.5)


def test_aggregate_results_rejects_empty_input() -> None:
    with pytest.raises(
        ValueError,
        match="empty benchmark",
    ):
        aggregate_results([])


def test_saved_report_contains_reproducibility_metadata() -> None:
    report = load_saved_report()
    metadata = report["metadata"]

    assert REQUIRED_METADATA_FIELDS <= metadata.keys()
    assert metadata["question_count"] == len(
        report["questions"]
    )
    assert len(metadata["corpus_file_sha256"]) == 64


def test_saved_report_contains_all_retrieval_methods() -> None:
    report = load_saved_report()

    assert set(report["summary"]) == set(METHODS)

    for question in report["questions"]:
        assert set(question["methods"]) == set(METHODS)

        for method in METHODS:
            method_result = question["methods"][method]
            ranked_ids = method_result[
                "ranked_safeguard_ids"
            ]

            assert len(ranked_ids) <= 5
            assert len(ranked_ids) == len(
                set(ranked_ids)
            )
            assert REQUIRED_METRIC_FIELDS <= (
                method_result["metrics"].keys()
            )
@pytest.mark.parametrize(
    ("split", "expected_stem"),
    [
        (
            "dev",
            "retrieval_benchmark_dev_results",
        ),
        (
            "test",
            "retrieval_benchmark_test_results",
        ),
    ],
)
def test_report_paths_include_dataset_and_split(
    tmp_path: Path,
    split: str,
    expected_stem: str,
) -> None:
    dataset_path = Path(
        "evaluation/datasets/retrieval_benchmark.jsonl"
    )

    json_path, csv_path = build_report_paths(
        dataset_path=dataset_path,
        split=split,
        output_directory=tmp_path,
    )

    assert json_path == (
        tmp_path / f"{expected_stem}.json"
    )
    assert csv_path == (
        tmp_path / f"{expected_stem}.csv"
    )