from sentence_transformers import CrossEncoder


class Reranker:

    def __init__(self):

        self.model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    def rerank(
        self,
        query,
        documents,
        top_k=3
    ):

        pairs = []

        for doc in documents:

            pairs.append(
                (
                    query,
                    doc["content"]
                )
            )

        scores = self.model.predict(
            pairs
        )

        for doc, score in zip(
            documents,
            scores
        ):
            doc["rerank_score"] = float(score)

        ranked = sorted(
            documents,
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        return ranked[:top_k]