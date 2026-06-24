from retrieval.vector_retriever import VectorRetriever
from retrieval.bm25_retriever import BM25Retriever
from retrieval.rrf import ReciprocalRankFusion
from retrieval.reranker import Reranker



class HybridRetriever:

    def __init__(self):

        self.vector = VectorRetriever()

        self.bm25 = BM25Retriever()

        self.rrf = ReciprocalRankFusion()

        self.reranker = Reranker()

    def search(self, query, k=5):

        vector_results = self.vector.search(
            query,
            k=20
        )

        bm25_results = self.bm25.search(
            query,
            k=20
        )

        fused_results = self.rrf.fuse(
            vector_results,
            bm25_results
        )

        reranked_results = self.reranker.rerank(
            query=query,
            documents=fused_results,
            top_k=3
        )

        return reranked_results