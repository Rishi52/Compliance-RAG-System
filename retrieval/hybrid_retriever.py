from typing import Any

from config.settings import settings
from retrieval.bm25_retriever import BM25Retriever
from retrieval.reranker import Reranker
from retrieval.rrf import ReciprocalRankFusion
from retrieval.vector_retriever import VectorRetriever


class HybridRetriever:
    """Combine dense, BM25, RRF and cross-encoder retrieval."""

    def __init__(
        self,
        vector: VectorRetriever | None = None,
        bm25: BM25Retriever | None = None,
        rrf: ReciprocalRankFusion | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.vector = vector or VectorRetriever()
        self.bm25 = bm25 or BM25Retriever()
        self.rrf = rrf or ReciprocalRankFusion(
            k=settings.rrf_k
        )
        self.reranker = reranker or Reranker()

    def search(
        self,
        query: str,
        k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return exactly the requested number of hybrid results."""

        query = query.strip()

        if not query:
            raise ValueError("Search query cannot be empty.")

        final_k = settings.final_top_k if k is None else k

        if final_k <= 0:
            raise ValueError("k must be greater than zero.")

        vector_k = max(
            settings.vector_candidates,
            final_k,
        )
        bm25_k = max(
            settings.bm25_candidates,
            final_k,
        )

        vector_results = self.vector.search(
            query,
            k=vector_k,
        )

        bm25_results = self.bm25.search(
            query,
            k=bm25_k,
        )

        fused_results = self.rrf.fuse(
            vector_results,
            bm25_results,
        )

        return self.reranker.rerank(
            query=query,
            documents=fused_results,
            top_k=final_k,
        )