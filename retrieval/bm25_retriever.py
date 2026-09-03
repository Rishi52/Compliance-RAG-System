import json
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from config.settings import settings


TOKEN_PATTERN = re.compile(r"\b[\w.-]+\b", re.UNICODE)


class BM25Retriever:
    """Retrieve CIS chunks using BM25 lexical matching."""

    def __init__(
        self,
        json_path: str | Path | None = None,
    ) -> None:
        self.json_path = Path(
            json_path or settings.chunked_safeguards_path
        )

        if not self.json_path.exists():
            raise FileNotFoundError(
                f"Chunk data was not found at: {self.json_path}\n"
                "Run: python -m scripts.chunk_safeguards"
            )

        self.documents = json.loads(
            self.json_path.read_text(encoding="utf-8")
        )

        if not isinstance(self.documents, list) or not self.documents:
            raise ValueError(
                "BM25 requires a non-empty chunk dataset."
            )

        for position, document in enumerate(self.documents):
            if "chunk_id" not in document or "content" not in document:
                raise ValueError(
                    f"Document at position {position} is missing "
                    "chunk_id or content."
                )

        self.corpus = [
            document["content"]
            for document in self.documents
        ]

        self.tokenized_corpus = [
            self.tokenize(content)
            for content in self.corpus
        ]

        self.bm25 = BM25Okapi(self.tokenized_corpus)

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Normalize text while preserving IDs such as 1.1."""

        return TOKEN_PATTERN.findall(text.lower())

    @staticmethod
    def build_metadata(
        document: dict[str, Any],
    ) -> dict[str, str | int]:
        """Return the same metadata stored in ChromaDB."""

        return {
            "chunk_id": document["chunk_id"],
            "document_id": document["document_id"],
            "chunk_index": int(document["chunk_index"]),
            "page": int(document["page"]),
            "control_id": str(document["control_id"]),
            "control_name": str(document["control_name"]),
            "safeguard_id": str(document["safeguard_id"]),
            "safeguard_name": str(document["safeguard_name"]),
        }

    def search(
        self,
        query: str,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top-k positive-scoring BM25 results."""

        query = query.strip()

        if not query:
            raise ValueError("Search query cannot be empty.")

        if k <= 0:
            raise ValueError("k must be greater than zero.")

        tokenized_query = self.tokenize(query)

        if not tokenized_query:
            return []

        scores = self.bm25.get_scores(tokenized_query)

        ranked_indices = sorted(
            (
                index
                for index, score in enumerate(scores)
                if score > 0
            ),
            key=lambda index: scores[index],
            reverse=True,
        )[:k]

        results: list[dict[str, Any]] = []

        for rank, index in enumerate(ranked_indices, start=1):
            document = self.documents[index]

            results.append(
                {
                    "chunk_id": document["chunk_id"],
                    "score": float(scores[index]),
                    "rank": rank,
                    "retriever": "bm25",
                    "content": document["content"],
                    "metadata": self.build_metadata(document),
                }
            )

        return results