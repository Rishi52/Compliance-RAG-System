import json
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from config.settings import settings


REQUIRED_CHUNK_FIELDS = {
    "chunk_id",
    "document_id",
    "chunk_index",
    "page",
    "control_id",
    "control_name",
    "safeguard_id",
    "safeguard_name",
    "content",
}


def load_chunks(input_path: Path) -> list[dict[str, Any]]:
    """Load and validate chunks before indexing."""

    if not input_path.exists():
        raise FileNotFoundError(
            f"Chunk data was not found at: {input_path}\n"
            "Run: python -m scripts.chunk_safeguards"
        )

    chunks = json.loads(input_path.read_text(encoding="utf-8"))

    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Chunk input must be a non-empty JSON list.")

    seen_ids: set[str] = set()

    for position, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(
                f"Chunk at position {position} is not an object."
            )

        missing_fields = REQUIRED_CHUNK_FIELDS - chunk.keys()

        if missing_fields:
            raise ValueError(
                f"Chunk at position {position} is missing: "
                f"{sorted(missing_fields)}"
            )

        chunk_id = chunk["chunk_id"]

        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk ID: {chunk_id}")

        if not chunk["content"].strip():
            raise ValueError(f"Chunk {chunk_id} has empty content.")

        seen_ids.add(chunk_id)

    return chunks


def build_metadata(chunk: dict[str, Any]) -> dict[str, str | int]:
    """Convert chunk metadata into Chroma-compatible scalar values."""

    return {
        "chunk_id": chunk["chunk_id"],
        "document_id": chunk["document_id"],
        "chunk_index": int(chunk["chunk_index"]),
        "page": int(chunk["page"]),
        "control_id": str(chunk["control_id"]),
        "control_name": str(chunk["control_name"]),
        "safeguard_id": str(chunk["safeguard_id"]),
        "safeguard_name": str(chunk["safeguard_name"]),
    }


def create_vector_index(
    chunks: list[dict[str, Any]],
) -> tuple[int, int]:
    """Create or update the persistent Chroma vector index."""

    print(f"Loading embedding model: {settings.embedding_model}")

    model = SentenceTransformer(settings.embedding_model)

    documents = [chunk["content"] for chunk in chunks]
    ids = [chunk["chunk_id"] for chunk in chunks]
    metadatas = [build_metadata(chunk) for chunk in chunks]

    print(f"Generating embeddings for {len(documents)} chunks...")

    embeddings = model.encode(
        documents,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()

    client = chromadb.PersistentClient(
        path=str(settings.chroma_path)
    )

    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )

    # Remove records that no longer exist in the current chunk dataset.
    existing_ids = set(collection.get()["ids"])
    current_ids = set(ids)
    stale_ids = sorted(existing_ids - current_ids)

    if stale_ids:
        collection.delete(ids=stale_ids)

    # Upsert makes indexing safe to run repeatedly.
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    stored_ids = set(collection.get()["ids"])

    if stored_ids != current_ids:
        missing_ids = sorted(current_ids - stored_ids)
        unexpected_ids = sorted(stored_ids - current_ids)

        raise RuntimeError(
            "Vector index validation failed. "
            f"Missing IDs: {missing_ids[:5]}; "
            f"Unexpected IDs: {unexpected_ids[:5]}"
        )

    return collection.count(), len(stale_ids)


def main() -> None:
    chunks = load_chunks(settings.chunked_safeguards_path)

    stored_count, removed_count = create_vector_index(chunks)

    print(f"Source chunks: {len(chunks)}")
    print(f"Removed stale records: {removed_count}")
    print(f"Stored vector records: {stored_count}")
    print(f"Collection: {settings.chroma_collection}")
    print(f"Database path: {settings.chroma_path}")


if __name__ == "__main__":
    main()