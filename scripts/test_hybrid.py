import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

from retrieval.hybrid_retriever import HybridRetriever

retriever = HybridRetriever()

query = input("Query: ")

results = retriever.search(
    query=query,
    k=5
)

for i, result in enumerate(results, start=1):

    print("\n" + "=" * 80)

    print(f"Rank {i}")

    print(result["metadata"])

    print()

    print(f"RRF Score: {result['rrf_score']:.5f}")

    print()

    print(
        result["content"][:500]
    )

    print(
    f"Rerank Score: {result['rerank_score']:.4f}"
    )