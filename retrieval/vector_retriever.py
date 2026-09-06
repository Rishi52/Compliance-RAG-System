from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from config.settings import settings


class VectorRetriever:
    """Retrieve CIS chunks using dense vector similarity."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        collection_name: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.db_path = Path(db_path or settings.chroma_path)
        self.collection_name = (
            collection_name or settings.chroma_collection
        )
        self.embedding_model = (
            embedding_model or settings.embedding_model
        )

        self.model = SentenceTransformer(self.embedding_model)

        self.client = chromadb.PersistentClient(
            path=str(self.db_path)
        )

        try:
            self.collection = self.client.get_collection(
                name=self.collection_name
            )
        except Exception as error:
            raise RuntimeError(
                f"Chroma collection {self.collection_name!r} "
                f"was not found at {self.db_path}. "
                "Run: python -m scripts.create_vector_db"
            ) from error

    def search(
        self,
        query: str,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return the top-k vector results."""

        query = query.strip()

        if not query:
            raise ValueError("Search query cannot be empty.")

        if k <= 0:
            raise ValueError("k must be greater than zero.")

        collection_count = self.collection.count()

        if collection_count == 0:
            return []

        result_count = min(k, collection_count)

        query_embedding = self.model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

        response = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=result_count,
            include=["documents", "metadatas", "distances"],
        )

        ids = response["ids"][0]
        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        distances = response["distances"][0]

        results: list[dict[str, Any]] = []

        for rank, (
            chunk_id,
            document,
            metadata,
            distance,
        ) in enumerate(
            zip(ids, documents, metadatas, distances),
            start=1,
        ):
            results.append(
                {
                    "chunk_id": chunk_id,
                    "score": float(1.0 - distance),
                    "rank": rank,
                    "retriever": "vector",
                    "content": document,
                    "metadata": metadata,
                }
            )

        return results