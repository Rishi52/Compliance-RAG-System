import json
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings


REQUIRED_SOURCE_FIELDS = {
    "page",
    "control_id",
    "control_name",
    "safeguard_id",
    "safeguard_name",
    "content",
}


def load_safeguards(input_path: Path) -> list[dict[str, Any]]:
    """Load extracted safeguard records from JSON."""

    if not input_path.exists():
        raise FileNotFoundError(
            f"Extracted safeguards were not found at: {input_path}\n"
            "Run: python -m scripts.extract_safeguards"
        )

    records = json.loads(input_path.read_text(encoding="utf-8"))

    if not isinstance(records, list) or not records:
        raise ValueError("Safeguard input must be a non-empty JSON list.")

    for position, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"Safeguard at position {position} is not an object."
            )

        missing_fields = REQUIRED_SOURCE_FIELDS - record.keys()

        if missing_fields:
            raise ValueError(
                f"Safeguard at position {position} is missing: "
                f"{sorted(missing_fields)}"
            )

    return records


def build_context_header(record: dict[str, Any]) -> str:
    """Create the identifying header repeated in every chunk."""

    control_name = record["control_name"] or "Unknown control"

    return (
        f"Control {record['control_id']}: {control_name}\n"
        f"Safeguard {record['safeguard_id']}: "
        f"{record['safeguard_name']}"
    )


def chunk_safeguards(
    safeguards: list[dict[str, Any]],
    document_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    """Split safeguards into deterministic, metadata-rich chunks."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative.")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    chunks: list[dict[str, Any]] = []

    for record in safeguards:
        header = build_context_header(record)

        # Reserve enough space so the repeated header does not cause
        # the final chunk to exceed the configured chunk size.
        body_chunk_size = chunk_size - len(header) - 1

        if body_chunk_size <= 0:
            raise ValueError(
                "The metadata header is larger than the configured "
                f"chunk size for safeguard {record['safeguard_id']}."
            )

        effective_overlap = min(
            chunk_overlap,
            max(body_chunk_size - 1, 0),
        )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=body_chunk_size,
            chunk_overlap=effective_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
            keep_separator=True,
        )

        body_chunks = splitter.split_text(record["content"])

        for chunk_index, body in enumerate(body_chunks):
            chunk_id = (
                f"{document_id}:"
                f"{record['safeguard_id']}:"
                f"{chunk_index:03d}"
            )

            content = f"{header}\n{body.strip()}"

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "page": record["page"],
                    "control_id": record["control_id"],
                    "control_name": record["control_name"],
                    "safeguard_id": record["safeguard_id"],
                    "safeguard_name": record["safeguard_name"],
                    "content": content,
                }
            )

    return chunks

def validate_chunks(
    chunks: list[dict[str, Any]],
    safeguards: list[dict[str, Any]],
) -> None:
    """Validate chunk identity, metadata and parent coverage."""

    if not chunks:
        raise ValueError("No chunks were created.")

    required_chunk_fields = {
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

    seen_chunk_ids: set[str] = set()
    parent_indices: dict[str, list[int]] = {}

    for chunk in chunks:
        missing_fields = required_chunk_fields - chunk.keys()

        if missing_fields:
            raise ValueError(
                f"Chunk is missing fields: {sorted(missing_fields)}"
            )

        chunk_id = chunk["chunk_id"]

        if chunk_id in seen_chunk_ids:
            raise ValueError(f"Duplicate chunk ID detected: {chunk_id}")

        if not chunk["content"].strip():
            raise ValueError(f"Chunk {chunk_id} has empty content.")

        expected_header = (
            f"Control {chunk['control_id']}: "
            f"{chunk['control_name'] or 'Unknown control'}\n"
            f"Safeguard {chunk['safeguard_id']}: "
            f"{chunk['safeguard_name']}"
        )

        if not chunk["content"].startswith(expected_header):
            raise ValueError(
                f"Chunk {chunk_id} is missing its context header."
            )

        seen_chunk_ids.add(chunk_id)

        safeguard_id = chunk["safeguard_id"]
        parent_indices.setdefault(safeguard_id, []).append(
            chunk["chunk_index"]
        )

    source_ids = {
        record["safeguard_id"]
        for record in safeguards
    }
    chunked_source_ids = set(parent_indices)

    missing_parents = source_ids - chunked_source_ids

    if missing_parents:
        raise ValueError(
            "Safeguards without chunks: "
            f"{sorted(missing_parents)}"
        )

    for safeguard_id, indices in parent_indices.items():
        expected_indices = list(range(len(indices)))

        if sorted(indices) != expected_indices:
            raise ValueError(
                f"Non-contiguous chunk indices for {safeguard_id}: "
                f"{sorted(indices)}"
            )


def save_chunks(
    chunks: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Save chunks as formatted JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    safeguards = load_safeguards(settings.safeguards_path)

    chunks = chunk_safeguards(
        safeguards=safeguards,
        document_id=settings.document_id,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    validate_chunks(chunks, safeguards)
    save_chunks(chunks, settings.chunked_safeguards_path)

    multi_chunk_safeguards = len(
        {
            chunk["safeguard_id"]
            for chunk in chunks
            if chunk["chunk_index"] > 0
        }
    )

    print(f"Input safeguards: {len(safeguards)}")
    print(f"Generated chunks: {len(chunks)}")
    print(f"Unique chunk IDs: {len({c['chunk_id'] for c in chunks})}")
    print(f"Safeguards with multiple chunks: {multi_chunk_safeguards}")
    print(f"Chunk size: {settings.chunk_size}")
    print(f"Chunk overlap: {settings.chunk_overlap}")
    print(f"Saved to: {settings.chunked_safeguards_path}")


if __name__ == "__main__":
    main()