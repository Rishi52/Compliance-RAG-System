from typing import Any

import pytest

from retrieval.rrf import ReciprocalRankFusion


def make_result(
    chunk_id: str,
    score: float,
    retriever: str,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "content": f"Content for {chunk_id}",
        "metadata": {
            "chunk_id": chunk_id,
            "safeguard_id": "1.1",
        },
        "score": score,
        "retriever": retriever,
    }


@pytest.mark.parametrize("invalid_k", [0, -1])
def test_rrf_rejects_non_positive_k(
    invalid_k: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        ReciprocalRankFusion(k=invalid_k)


def test_rrf_returns_empty_result_without_rankings() -> None:
    fusion = ReciprocalRankFusion()

    assert fusion.fuse() == []


def test_rrf_boosts_chunks_found_by_multiple_retrievers() -> None:
    vector_results = [
        make_result("c1", 0.90, "vector"),
        make_result("c2", 0.80, "vector"),
    ]
    bm25_results = [
        make_result("c2", 4.00, "bm25"),
        make_result("c3", 3.00, "bm25"),
    ]

    results = ReciprocalRankFusion(k=60).fuse(
        vector_results,
        bm25_results,
    )

    assert [
        result["chunk_id"]
        for result in results
    ] == ["c2", "c1", "c3"]

    assert results[0]["retrievers"] == [
        "bm25",
        "vector",
    ]


def test_rrf_reads_chunk_id_from_metadata() -> None:
    result = make_result("c1", 0.90, "vector")
    del result["chunk_id"]

    fused = ReciprocalRankFusion().fuse([result])

    assert fused[0]["chunk_id"] == "c1"


def test_rrf_rejects_result_without_chunk_id() -> None:
    result = {
        "content": "Missing identifier",
        "metadata": {},
        "score": 0.90,
        "retriever": "vector",
    }

    with pytest.raises(
        ValueError,
        match="missing chunk_id",
    ):
        ReciprocalRankFusion().fuse([result])


def test_rrf_uses_chunk_id_for_deterministic_ties() -> None:
    results = ReciprocalRankFusion().fuse(
        [make_result("c2", 0.90, "vector")],
        [make_result("c1", 4.00, "bm25")],
    )

    assert [
        result["chunk_id"]
        for result in results
    ] == ["c1", "c2"]


def test_rrf_preserves_source_scores_and_ranks() -> None:
    vector_result = make_result(
        "c1",
        0.91,
        "vector",
    )
    bm25_result = make_result(
        "c1",
        7.50,
        "bm25",
    )

    result = ReciprocalRankFusion().fuse(
        [vector_result],
        [bm25_result],
    )[0]

    assert result["retrieval_scores"] == {
        "vector": 0.91,
        "bm25": 7.50,
    }
    assert result["retrieval_ranks"] == {
        "vector": 1,
        "bm25": 1,
    }
    assert result["rank"] == 1
    assert result["retriever"] == "hybrid"
    assert result["score"] == result["rrf_score"]