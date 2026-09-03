import math
from collections.abc import Iterable


def validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k must be greater than zero.")


def recall_at_k(
    ranked_ids: list[str],
    expected_ids: set[str],
    k: int,
) -> float:
    """Fraction of expected safeguards found in the top-k."""

    validate_k(k)

    if not expected_ids:
        raise ValueError(
            "Recall requires at least one expected ID."
        )

    retrieved = set(ranked_ids[:k])

    return len(retrieved & expected_ids) / len(expected_ids)


def hit_rate_at_k(
    ranked_ids: list[str],
    expected_ids: set[str],
    k: int,
) -> float:
    """Return 1 when any expected safeguard appears in top-k."""

    validate_k(k)

    if not expected_ids:
        raise ValueError(
            "Hit rate requires at least one expected ID."
        )

    return float(
        bool(set(ranked_ids[:k]) & expected_ids)
    )


def reciprocal_rank_at_k(
    ranked_ids: list[str],
    expected_ids: set[str],
    k: int,
) -> float:
    """Reciprocal rank of the first relevant safeguard."""

    validate_k(k)

    if not expected_ids:
        raise ValueError(
            "MRR requires at least one expected ID."
        )

    for rank, safeguard_id in enumerate(
        ranked_ids[:k],
        start=1,
    ):
        if safeguard_id in expected_ids:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(
    ranked_ids: list[str],
    expected_ids: set[str],
    k: int,
) -> float:
    """Binary normalized discounted cumulative gain."""

    validate_k(k)

    if not expected_ids:
        raise ValueError(
            "nDCG requires at least one expected ID."
        )

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, safeguard_id in enumerate(
            ranked_ids[:k],
            start=1,
        )
        if safeguard_id in expected_ids
    )

    ideal_relevant_count = min(len(expected_ids), k)

    ideal_dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_relevant_count + 1)
    )

    return dcg / ideal_dcg if ideal_dcg else 0.0


def deduplicate_ids(
    safeguard_ids: Iterable[str],
) -> list[str]:
    """Preserve ranking while removing duplicate safeguards."""

    seen: set[str] = set()
    unique_ids: list[str] = []

    for safeguard_id in safeguard_ids:
        safeguard_id = str(safeguard_id)

        if safeguard_id not in seen:
            seen.add(safeguard_id)
            unique_ids.append(safeguard_id)

    return unique_ids


def evaluate_ranking(
    ranked_ids: list[str],
    expected_ids: set[str],
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, float]:
    """Calculate retrieval metrics for one question."""

    unique_ranked_ids = deduplicate_ids(ranked_ids)

    metrics: dict[str, float] = {}

    for k in k_values:
        metrics[f"recall@{k}"] = recall_at_k(
            unique_ranked_ids,
            expected_ids,
            k,
        )
        metrics[f"hit_rate@{k}"] = hit_rate_at_k(
            unique_ranked_ids,
            expected_ids,
            k,
        )

    maximum_k = max(k_values)

    metrics[f"mrr@{maximum_k}"] = reciprocal_rank_at_k(
        unique_ranked_ids,
        expected_ids,
        maximum_k,
    )

    metrics[f"ndcg@{maximum_k}"] = ndcg_at_k(
        unique_ranked_ids,
        expected_ids,
        maximum_k,
    )

    return metrics