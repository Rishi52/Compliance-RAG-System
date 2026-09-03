import json
from pathlib import Path
from typing import Any

import chromadb

from config.settings import settings
from scripts.chunk_safeguards import validate_chunks
from scripts.extract_safeguards import validate_records


def load_json_records(
    path: Path,
    description: str,
) -> list[dict[str, Any]]:
    """Load a non-empty JSON record list."""

    if not path.exists():
        raise FileNotFoundError(
            f"{description} was not found at: {path}"
        )

    records = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(records, list) or not records:
        raise ValueError(
            f"{description} must be a non-empty JSON list."
        )

    return records


def validate_vector_index(
    chunks: list[dict[str, Any]],
) -> int:
    """Confirm that Chroma contains exactly the current chunks."""

    client = chromadb.PersistentClient(
        path=str(settings.chroma_path)
    )

    try:
        collection = client.get_collection(
            name=settings.chroma_collection
        )
    except Exception as error:
        raise RuntimeError(
            f"Chroma collection "
            f"{settings.chroma_collection!r} was not found. "
            "Run: python -m scripts.create_vector_db"
        ) from error

    expected_ids = {
        chunk["chunk_id"]
        for chunk in chunks
    }
    stored_ids = set(collection.get()["ids"])

    missing_ids = expected_ids - stored_ids
    unexpected_ids = stored_ids - expected_ids

    if missing_ids or unexpected_ids:
        raise ValueError(
            "Vector index does not match the chunk dataset. "
            f"Missing: {sorted(missing_ids)[:5]}; "
            f"Unexpected: {sorted(unexpected_ids)[:5]}"
        )

    return collection.count()


def main() -> None:
    """Validate extracted data, chunks and vector index."""

    safeguards = load_json_records(
        settings.safeguards_path,
        "Extracted safeguard data",
    )

    chunks = load_json_records(
        settings.chunked_safeguards_path,
        "Chunk data",
    )

    validate_records(safeguards)
    validate_chunks(chunks, safeguards)
    indexed_count = validate_vector_index(chunks)

    document_ids = sorted(
        {
            chunk["document_id"]
            for chunk in chunks
        }
    )

    print(f"Safeguards: {len(safeguards)}")
    print(f"Unique safeguards: {len({x['safeguard_id'] for x in safeguards})}")
    print(f"Chunks: {len(chunks)}")
    print(f"Unique chunks: {len({x['chunk_id'] for x in chunks})}")
    print(f"Indexed chunks: {indexed_count}")
    print(f"Document IDs: {document_ids}")
    print("Data and vector index validation passed.")


if __name__ == "__main__":
    main()