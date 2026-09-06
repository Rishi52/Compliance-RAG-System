from typing import Any

from sentence_transformers import CrossEncoder

from config.settings import settings


class Reranker:
    """Rerank retrieved chunks using a cross-encoder."""

    def __init__(
        self,
        model_name: str | None = None,
    ) -> None:
        self.model_name = model_name or settings.reranker_model
        self.model = CrossEncoder(self.model_name)

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Return the top-k cross-encoder-ranked chunks."""

        query = query.strip()

        if not query:
            raise ValueError("Reranking query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if not documents:
            return []

        pairs = [
            (query, document["content"])
            for document in documents
        ]

        scores = self.model.predict(
            pairs,
            show_progress_bar=False,
        )

        scored_documents: list[dict[str, Any]] = []

        for document, score in zip(documents, scores):
            scored_document = dict(document)
            scored_document["rerank_score"] = float(score)
            scored_documents.append(scored_document)

        ranked_documents = sorted(
            scored_documents,
            key=lambda document: (
                -document["rerank_score"],
                document["chunk_id"],
            ),
        )[:top_k]

        for rank, document in enumerate(
            ranked_documents,
            start=1,
        ):
            document["rank"] = rank

        return ranked_documents