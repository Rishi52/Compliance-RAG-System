import json
from rank_bm25 import BM25Okapi


class BM25Retriever:

    def __init__(
        self,
        json_path="data/processed/cis_safeguards.json"
    ):

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as f:
            self.documents = json.load(f)

        self.corpus = [
            doc["content"]
            for doc in self.documents
        ]

        self.tokenized_corpus = [
            doc.lower().split()
            for doc in self.corpus
        ]

        self.bm25 = BM25Okapi(
            self.tokenized_corpus
        )

    def search(self, query, k=5):

        tokenized_query = query.lower().split()

        scores = self.bm25.get_scores(
            tokenized_query
        )

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:k]

        results = []

        for idx in ranked_indices:

            doc = self.documents[idx]

            results.append(
                {
                    "score": float(scores[idx]),
                    "content": doc["content"],
                    "metadata": {
                        "page": doc["page"],
                        "control_id": doc["control_id"],
                        "control_name": doc["control_name"],
                        "safeguard_id": doc["safeguard_id"],
                        "safeguard_name": doc["safeguard_name"]
                    }
                }
            )

        return results