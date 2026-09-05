import json
from pathlib import Path
from typing import Any

import pytest

from scripts.chunk_safeguards import (
    build_context_header,
    chunk_safeguards,
    load_safeguards,
    validate_chunks,
)

class FakeTextSplitter:
    def __init__(self, chunk_size: int) -> None:
        self.chunk_size = chunk_size

    def split_text(self, text: str) -> list[str]:
        return [
            text[start : start + self.chunk_size]
            for start in range(
                0,
                len(text),
                self.chunk_size,
            )
        ]


def fake_text_splitter(
    chunk_size: int,
    chunk_overlap: int,
) -> FakeTextSplitter:
    del chunk_overlap

    return FakeTextSplitter(chunk_size)

def make_safeguard(
    safeguard_id: str = "1.1",
    content: str | None = None,
) -> dict[str, Any]:
    control_id = safeguard_id.split(".")[0]

    if content is None:
        content = (
            "| | |\n"
            "Asset Type: Devices\n"
            + (
                "Maintain a complete and accurate inventory. "
                * 20
            )
        )

    return {
        "page": 10,
        "control_id": control_id,
        "control_name": f"Control {control_id}",
        "safeguard_id": safeguard_id,
        "safeguard_name": (
            f"Test Safeguard {safeguard_id}"
        ),
        "content": content,
    }


def make_chunk(
    safeguard: dict[str, Any],
    chunk_index: int = 0,
) -> dict[str, Any]:
    chunk_id = (
        f"test-document:"
        f"{safeguard['safeguard_id']}:"
        f"{chunk_index:03d}"
    )
    header = build_context_header(safeguard)

    return {
        "chunk_id": chunk_id,
        "document_id": "test-document",
        "chunk_index": chunk_index,
        "page": safeguard["page"],
        "control_id": safeguard["control_id"],
        "control_name": safeguard["control_name"],
        "safeguard_id": safeguard["safeguard_id"],
        "safeguard_name": safeguard["safeguard_name"],
        "content": f"{header}\nSynthetic body.",
    }


def write_json(
    path: Path,
    payload: Any,
) -> Path:
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def test_load_safeguards_reads_valid_records(
    tmp_path: Path,
) -> None:
    records = [make_safeguard()]
    path = write_json(
        tmp_path / "safeguards.json",
        records,
    )

    assert load_safeguards(path) == records


def test_load_safeguards_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="were not found",
    ):
        load_safeguards(tmp_path / "missing.json")


def test_load_safeguards_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Invalid safeguard JSON",
    ):
        load_safeguards(path)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"safeguard": "not a list"},
    ],
)
def test_load_safeguards_requires_non_empty_list(
    tmp_path: Path,
    payload: Any,
) -> None:
    path = write_json(
        tmp_path / "invalid-container.json",
        payload,
    )

    with pytest.raises(
        ValueError,
        match="non-empty JSON list",
    ):
        load_safeguards(path)


def test_load_safeguards_rejects_non_object_record(
    tmp_path: Path,
) -> None:
    path = write_json(
        tmp_path / "non-object.json",
        ["invalid"],
    )

    with pytest.raises(
        ValueError,
        match="is not an object",
    ):
        load_safeguards(path)


def test_load_safeguards_rejects_missing_fields(
    tmp_path: Path,
) -> None:
    record = make_safeguard()
    del record["content"]

    path = write_json(
        tmp_path / "missing-field.json",
        [record],
    )

    with pytest.raises(
        ValueError,
        match="is missing",
    ):
        load_safeguards(path)


def test_load_safeguards_rejects_empty_content(
    tmp_path: Path,
) -> None:
    path = write_json(
        tmp_path / "empty-content.json",
        [make_safeguard(content="   ")],
    )

    with pytest.raises(
        ValueError,
        match="empty content",
    ):
        load_safeguards(path)


def test_context_header_uses_unknown_control_fallback() -> None:
    record = make_safeguard()
    record["control_name"] = None

    assert build_context_header(record).startswith(
        "Control 1: Unknown control\n"
    )


def test_chunking_is_deterministic_and_size_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "scripts.chunk_safeguards.create_text_splitter",
        fake_text_splitter,
    )
    safeguard = make_safeguard()

    first_run = chunk_safeguards(
        safeguards=[safeguard],
        document_id="test-document",
        chunk_size=160,
        chunk_overlap=20,
    )
    second_run = chunk_safeguards(
        safeguards=[safeguard],
        document_id="test-document",
        chunk_size=160,
        chunk_overlap=20,
    )

    assert first_run == second_run
    assert len(first_run) > 1

    expected_ids = [
        f"test-document:1.1:{index:03d}"
        for index in range(len(first_run))
    ]

    assert [
        chunk["chunk_id"]
        for chunk in first_run
    ] == expected_ids

    header = build_context_header(safeguard)

    assert all(
        chunk["content"].startswith(header)
        for chunk in first_run
    )
    assert all(
        len(chunk["content"]) <= 160
        for chunk in first_run
    )
    assert all(
        chunk["document_id"] == "test-document"
        for chunk in first_run
    )


def test_chunking_rejects_empty_document_id() -> None:
    with pytest.raises(
        ValueError,
        match="document_id cannot be empty",
    ):
        chunk_safeguards(
            safeguards=[make_safeguard()],
            document_id="   ",
            chunk_size=160,
            chunk_overlap=20,
        )


def test_chunking_rejects_non_positive_size() -> None:
    with pytest.raises(
        ValueError,
        match="chunk_size must be greater than zero",
    ):
        chunk_safeguards(
            safeguards=[make_safeguard()],
            document_id="test-document",
            chunk_size=0,
            chunk_overlap=0,
        )


def test_chunking_rejects_negative_overlap() -> None:
    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        chunk_safeguards(
            safeguards=[make_safeguard()],
            document_id="test-document",
            chunk_size=160,
            chunk_overlap=-1,
        )


def test_chunking_requires_overlap_smaller_than_size() -> None:
    with pytest.raises(
        ValueError,
        match="smaller than chunk_size",
    ):
        chunk_safeguards(
            safeguards=[make_safeguard()],
            document_id="test-document",
            chunk_size=100,
            chunk_overlap=100,
        )


def test_chunking_rejects_header_larger_than_chunk() -> None:
    safeguard = make_safeguard()
    safeguard["safeguard_name"] = "X" * 200

    with pytest.raises(
        ValueError,
        match="header is larger",
    ):
        chunk_safeguards(
            safeguards=[safeguard],
            document_id="test-document",
            chunk_size=50,
            chunk_overlap=10,
        )


def test_validate_chunks_accepts_valid_chunks() -> None:
    safeguard = make_safeguard()
    chunk = make_chunk(safeguard)

    validate_chunks([chunk], [safeguard])


def test_validate_chunks_rejects_empty_list() -> None:
    with pytest.raises(
        ValueError,
        match="No chunks were created",
    ):
        validate_chunks([], [make_safeguard()])


def test_validate_chunks_rejects_non_object() -> None:
    with pytest.raises(
        ValueError,
        match="is not an object",
    ):
        validate_chunks(
            ["invalid"],  # type: ignore[list-item]
            [make_safeguard()],
        )


def test_validate_chunks_rejects_missing_fields() -> None:
    safeguard = make_safeguard()
    chunk = make_chunk(safeguard)
    del chunk["page"]

    with pytest.raises(
        ValueError,
        match="missing fields",
    ):
        validate_chunks([chunk], [safeguard])


def test_validate_chunks_rejects_duplicate_ids() -> None:
    safeguard = make_safeguard()
    chunk = make_chunk(safeguard)

    with pytest.raises(
        ValueError,
        match="Duplicate chunk ID",
    ):
        validate_chunks(
            [chunk, dict(chunk)],
            [safeguard],
        )


def test_validate_chunks_rejects_empty_content() -> None:
    safeguard = make_safeguard()
    chunk = make_chunk(safeguard)
    chunk["content"] = "   "

    with pytest.raises(
        ValueError,
        match="empty content",
    ):
        validate_chunks([chunk], [safeguard])


def test_validate_chunks_requires_context_header() -> None:
    safeguard = make_safeguard()
    chunk = make_chunk(safeguard)
    chunk["content"] = "Synthetic body only."

    with pytest.raises(
        ValueError,
        match="missing its context header",
    ):
        validate_chunks([chunk], [safeguard])


def test_validate_chunks_detects_missing_parent() -> None:
    first = make_safeguard("1.1")
    second = make_safeguard("2.1")

    with pytest.raises(
        ValueError,
        match="Safeguards without chunks",
    ):
        validate_chunks(
            [make_chunk(first)],
            [first, second],
        )


def test_validate_chunks_detects_unknown_parent() -> None:
    known = make_safeguard("1.1")
    unknown = make_safeguard("9.9")

    with pytest.raises(
        ValueError,
        match="unknown safeguards",
    ):
        validate_chunks(
            [
                make_chunk(known),
                make_chunk(unknown),
            ],
            [known],
        )


def test_validate_chunks_requires_contiguous_indices() -> None:
    safeguard = make_safeguard()

    with pytest.raises(
        ValueError,
        match="Non-contiguous chunk indices",
    ):
        validate_chunks(
            [
                make_chunk(safeguard, 0),
                make_chunk(safeguard, 2),
            ],
            [safeguard],
        )