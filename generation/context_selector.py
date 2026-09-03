import json
from pathlib import Path
from typing import Any

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


class SafeguardContextSelector:
    """Select top safeguards and restore all their sibling chunks."""

    def __init__(
        self,
        json_path: str | Path | None = None,
    ) -> None:
        self.json_path = Path(
            json_path or settings.chunked_safeguards_path
        )

        if not self.json_path.exists():
            raise FileNotFoundError(
                f"Chunk data was not found at: {self.json_path}"
            )

        chunks = json.loads(
            self.json_path.read_text(encoding="utf-8")
        )

        if not isinstance(chunks, list) or not chunks:
            raise ValueError(
                "Context selection requires a non-empty chunk dataset."
            )

        self.chunks_by_safeguard: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for position, chunk in enumerate(chunks):
            missing_fields = REQUIRED_CHUNK_FIELDS - chunk.keys()

            if missing_fields:
                raise ValueError(
                    f"Chunk at position {position} is missing: "
                    f"{sorted(missing_fields)}"
                )

            safeguard_id = str(chunk["safeguard_id"])

            self.chunks_by_safeguard.setdefault(
                safeguard_id,
                [],
            ).append(chunk)

        for safeguard_chunks in (
            self.chunks_by_safeguard.values()
        ):
            safeguard_chunks.sort(
                key=lambda chunk: chunk["chunk_index"]
            )

    @staticmethod
    def build_metadata(
        chunk: dict[str, Any],
    ) -> dict[str, str | int]:
        """Convert a stored chunk to retrieval-style metadata."""

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

    def select(
        self,
        ranked_documents: list[dict[str, Any]],
        max_safeguards: int | None = None,
    ) -> list[dict[str, Any]]:
        """Select unique safeguards and expand their complete text."""

        limit = (
            settings.generation_safeguards_k
            if max_safeguards is None
            else max_safeguards
        )

        if limit <= 0:
            raise ValueError(
                "max_safeguards must be greater than zero."
            )

        selected_safeguard_ids: list[str] = []

        for document in ranked_documents:
            metadata = document.get("metadata")

            if not isinstance(metadata, dict):
                raise ValueError(
                    "Ranked document has invalid metadata."
                )

            safeguard_id = str(metadata["safeguard_id"])

            if safeguard_id not in selected_safeguard_ids:
                selected_safeguard_ids.append(safeguard_id)

            if len(selected_safeguard_ids) == limit:
                break

        selected_documents: list[dict[str, Any]] = []

        for safeguard_rank, safeguard_id in enumerate(
            selected_safeguard_ids,
            start=1,
        ):
            sibling_chunks = self.chunks_by_safeguard.get(
                safeguard_id
            )

            if not sibling_chunks:
                raise ValueError(
                    f"No stored chunks found for safeguard "
                    f"{safeguard_id}."
                )

            for chunk in sibling_chunks:
                selected_documents.append(
                    {
                        "chunk_id": chunk["chunk_id"],
                        "content": chunk["content"],
                        "metadata": self.build_metadata(chunk),
                        "retriever": "parent_expansion",
                        "safeguard_rank": safeguard_rank,
                    }
                )

        return selected_documents