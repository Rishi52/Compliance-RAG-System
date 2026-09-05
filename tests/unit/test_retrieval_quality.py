import pytest

from evaluation.check_retrieval_quality import (
    DEFAULT_METHOD,
    DEFAULT_REPORT_PATH,
    find_quality_failures,
    get_method_summary,
    load_report,
)


def test_saved_development_report_passes_quality_gate() -> None:
    report = load_report(DEFAULT_REPORT_PATH)
    method_summary = get_method_summary(
        report,
        DEFAULT_METHOD,
    )

    assert find_quality_failures(method_summary) == []


def test_quality_gate_detects_metric_regression() -> None:
    method_summary = {
        "recall@1": 0.50,
        "recall@3": 1.00,
        "mrr@5": 0.95,
        "ndcg@5": 0.95,
    }

    failures = find_quality_failures(method_summary)

    assert failures == [
        "recall@1: expected >= 0.800, found 0.500"
    ]


def test_method_summary_rejects_unknown_method() -> None:
    report = {
        "summary": {},
    }

    with pytest.raises(
        ValueError,
        match="has no method",
    ):
        get_method_summary(report, "missing_method")


def test_quality_gate_rejects_missing_metric() -> None:
    with pytest.raises(
        ValueError,
        match="missing metric",
    ):
        find_quality_failures({})