import math
from collections.abc import Callable

import pytest

from evaluation.metrics import (
    deduplicate_ids,
    evaluate_ranking,
    hit_rate_at_k,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
)


MetricFunction = Callable[[list[str], set[str], int], float]

METRIC_FUNCTIONS: tuple[MetricFunction, ...] = (
    recall_at_k,
    hit_rate_at_k,
    reciprocal_rank_at_k,
    ndcg_at_k,
)


def test_deduplicate_ids_preserves_ranking_order() -> None:
    result = deduplicate_ids(
        ["1.1", "1.1", "1.4", "1.1", "2.1"]
    )

    assert result == ["1.1", "1.4", "2.1"]


def test_recall_at_k_supports_multiple_expected_ids() -> None:
    ranked_ids = ["1.2", "4.2", "3.4"]
    expected_ids = {"1.2", "3.4"}

    assert recall_at_k(ranked_ids, expected_ids, 2) == 0.5
    assert recall_at_k(ranked_ids, expected_ids, 3) == 1.0


def test_hit_rate_at_k_detects_any_relevant_result() -> None:
    ranked_ids = ["2.1", "1.2"]
    expected_ids = {"1.2"}

    assert hit_rate_at_k(ranked_ids, expected_ids, 1) == 0.0
    assert hit_rate_at_k(ranked_ids, expected_ids, 2) == 1.0


def test_reciprocal_rank_uses_first_relevant_position() -> None:
    result = reciprocal_rank_at_k(
        ["2.1", "1.2", "3.4"],
        {"1.2"},
        3,
    )

    assert result == pytest.approx(0.5)


def test_ndcg_discounts_lower_ranked_results() -> None:
    result = ndcg_at_k(
        ["2.1", "1.2", "3.4"],
        {"1.2"},
        3,
    )

    assert result == pytest.approx(
        1.0 / math.log2(3)
    )


def test_evaluate_ranking_deduplicates_before_scoring() -> None:
    result = evaluate_ranking(
        ranked_ids=["1.1", "1.1", "1.4"],
        expected_ids={"1.4"},
    )

    assert result["recall@1"] == 0.0
    assert result["recall@3"] == 1.0
    assert result["hit_rate@3"] == 1.0
    assert result["mrr@5"] == pytest.approx(0.5)
    assert result["ndcg@5"] == pytest.approx(
        1.0 / math.log2(3)
    )


@pytest.mark.parametrize("metric", METRIC_FUNCTIONS)
def test_metrics_reject_non_positive_k(
    metric: MetricFunction,
) -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        metric(["1.1"], {"1.1"}, 0)


@pytest.mark.parametrize("metric", METRIC_FUNCTIONS)
def test_metrics_reject_empty_expected_ids(
    metric: MetricFunction,
) -> None:
    with pytest.raises(ValueError):
        metric(["1.1"], set(), 1)