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


from retrieval.bm25_retriever import BM25Retriever

retriever = BM25Retriever()

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

    print(
        result["content"][:500]
    )