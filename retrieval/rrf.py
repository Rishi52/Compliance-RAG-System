from collections import defaultdict


class ReciprocalRankFusion:

    def __init__(self, k=60):
        self.k = k

    def fuse(self, vector_results, bm25_results):

        scores = defaultdict(float)
        documents = {}

        for rank, result in enumerate(
            vector_results,
            start=1
        ):

            safeguard_id = result["metadata"]["safeguard_id"]

            scores[safeguard_id] += (
                1 / (self.k + rank)
            )

            documents[safeguard_id] = result

        for rank, result in enumerate(
            bm25_results,
            start=1
        ):

            safeguard_id = result["metadata"]["safeguard_id"]

            scores[safeguard_id] += (
                1 / (self.k + rank)
            )

            documents[safeguard_id] = result

        ranked = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        fused_results = []

        for safeguard_id, score in ranked:

            result = documents[safeguard_id]

            result["rrf_score"] = score

            fused_results.append(result)

        return fused_results