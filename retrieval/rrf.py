from collections import defaultdict
from typing import Any


class ReciprocalRankFusion:
    """Fuse ranked retrieval results using deterministic chunk IDs."""

    def __init__(self, k: int = 60) -> None:
        if k <= 0:
            raise ValueError("RRF k must be greater than zero.")

        self.k = k

    def fuse(
        self,
        *ranked_result_lists: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fuse any number of ranked result lists by chunk_id."""

        if not ranked_result_lists:
            return []

        scores: defaultdict[str, float] = defaultdict(float)
        documents: dict[str, dict[str, Any]] = {}

        for list_number, results in enumerate(
            ranked_result_lists,
            start=1,
        ):
            for rank, result in enumerate(results, start=1):
                chunk_id = result.get("chunk_id")

                if not chunk_id:
                    chunk_id = result.get("metadata", {}).get(
                        "chunk_id"
                    )

                if not chunk_id:
                    raise ValueError(
                        "Retrieval result is missing chunk_id."
                    )

                retriever_name = str(
                    result.get(
                        "retriever",
                        f"retriever_{list_number}",
                    )
                )

                scores[chunk_id] += 1.0 / (self.k + rank)

                if chunk_id not in documents:
                    documents[chunk_id] = {
                        "chunk_id": chunk_id,
                        "content": result["content"],
                        "metadata": dict(result["metadata"]),
                        "retrieval_scores": {},
                        "retrieval_ranks": {},
                    }

                documents[chunk_id]["retrieval_scores"][
                    retriever_name
                ] = float(result["score"])

                documents[chunk_id]["retrieval_ranks"][
                    retriever_name
                ] = rank

        ranked_chunks = sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )

        fused_results: list[dict[str, Any]] = []

        for fused_rank, (chunk_id, rrf_score) in enumerate(
            ranked_chunks,
            start=1,
        ):
            result = dict(documents[chunk_id])
            result["score"] = float(rrf_score)
            result["rrf_score"] = float(rrf_score)
            result["rank"] = fused_rank
            result["retriever"] = "hybrid"
            result["retrievers"] = sorted(
                result["retrieval_scores"]
            )

            fused_results.append(result)

        return fused_results