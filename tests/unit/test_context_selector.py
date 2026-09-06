import json
from pathlib import Path
from typing import Any

import pytest

from generation.context_selector import (
    SafeguardContextSelector,
)


def make_chunk(
    safeguard_id: str,
    chunk_index: int = 0,
) -> dict[str, Any]:
    control_id = safeguard_id.split(".")[0]
    chunk_id = (
        f"test-document:{safeguard_id}:"
        f"{chunk_index:03d}"
    )

    return {
        "chunk_id": chunk_id,
        "document_id": "test-document",
        "chunk_index": chunk_index,
        "page": 10,
        "control_id": control_id,
        "control_name": f"Control {control_id}",
        "safeguard_id": safeguard_id,
        "safeguard_name": f"Safeguard {safeguard_id}",
        "content": (
            f"Content for {safeguard_id}, "
            f"chunk {chunk_index}"
        ),
    }


def write_chunks(
    tmp_path: Path,
    chunks: list[Any],
) -> Path:
    path = tmp_path / "chunks.json"
    path.write_text(
        json.dumps(chunks),
        encoding="utf-8",
    )

    return path


def ranked_document(
    safeguard_id: str,
) -> dict[str, Any]:
    return {
        "metadata": {
            "safeguard_id": safeguard_id,
        }
    }


def test_selector_rejects_missing_chunk_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="was not found",
    ):
        SafeguardContextSelector(
            tmp_path / "missing.json"
        )


def test_selector_rejects_empty_chunk_dataset(
    tmp_path: Path,
) -> None:
    path = write_chunks(tmp_path, [])

    with pytest.raises(
        ValueError,
        match="non-empty",
    ):
        SafeguardContextSelector(path)


def test_selector_rejects_non_object_chunk(
    tmp_path: Path,
) -> None:
    path = write_chunks(tmp_path, ["not an object"])

    with pytest.raises(
        ValueError,
        match="is not an object",
    ):
        SafeguardContextSelector(path)


def test_selector_rejects_missing_chunk_fields(
    tmp_path: Path,
) -> None:
    chunk = make_chunk("1.1")
    del chunk["content"]
    path = write_chunks(tmp_path, [chunk])

    with pytest.raises(
        ValueError,
        match="is missing",
    ):
        SafeguardContextSelector(path)


def test_selector_expands_and_sorts_sibling_chunks(
    tmp_path: Path,
) -> None:
    chunks = [
        make_chunk("1.1", 1),
        make_chunk("2.1", 0),
        make_chunk("1.1", 0),
    ]
    selector = SafeguardContextSelector(
        write_chunks(tmp_path, chunks)
    )

    selected = selector.select(
        [ranked_document("1.1")],
        max_safeguards=1,
    )

    assert [
        document["chunk_id"]
        for document in selected
    ] == [
        "test-document:1.1:000",
        "test-document:1.1:001",
    ]
    assert [
        document["metadata"]["chunk_index"]
        for document in selected
    ] == [0, 1]
    assert [
        document["safeguard_rank"]
        for document in selected
    ] == [1, 1]
    assert all(
        document["retriever"] == "parent_expansion"
        for document in selected
    )


def test_selector_deduplicates_ranked_safeguards(
    tmp_path: Path,
) -> None:
    selector = SafeguardContextSelector(
        write_chunks(
            tmp_path,
            [
                make_chunk("1.1"),
                make_chunk("2.1"),
                make_chunk("3.1"),
            ],
        )
    )

    selected = selector.select(
        [
            ranked_document("1.1"),
            ranked_document("1.1"),
            ranked_document("2.1"),
            ranked_document("3.1"),
        ],
        max_safeguards=2,
    )

    assert [
        document["metadata"]["safeguard_id"]
        for document in selected
    ] == ["1.1", "2.1"]

    assert [
        document["safeguard_rank"]
        for document in selected
    ] == [1, 2]


@pytest.mark.parametrize("invalid_limit", [0, -1])
def test_selector_rejects_non_positive_limit(
    tmp_path: Path,
    invalid_limit: int,
) -> None:
    selector = SafeguardContextSelector(
        write_chunks(
            tmp_path,
            [make_chunk("1.1")],
        )
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        selector.select(
            [ranked_document("1.1")],
            max_safeguards=invalid_limit,
        )


def test_selector_rejects_invalid_ranked_metadata(
    tmp_path: Path,
) -> None:
    selector = SafeguardContextSelector(
        write_chunks(
            tmp_path,
            [make_chunk("1.1")],
        )
    )

    with pytest.raises(
        ValueError,
        match="invalid metadata",
    ):
        selector.select(
            [{"metadata": "invalid"}],
            max_safeguards=1,
        )


def test_selector_requires_ranked_safeguard_id(
    tmp_path: Path,
) -> None:
    selector = SafeguardContextSelector(
        write_chunks(
            tmp_path,
            [make_chunk("1.1")],
        )
    )

    with pytest.raises(
        ValueError,
        match="missing safeguard_id",
    ):
        selector.select(
            [{"metadata": {}}],
            max_safeguards=1,
        )


def test_selector_rejects_unknown_safeguard(
    tmp_path: Path,
) -> None:
    selector = SafeguardContextSelector(
        write_chunks(
            tmp_path,
            [make_chunk("1.1")],
        )
    )

    with pytest.raises(
        ValueError,
        match="No stored chunks found",
    ):
        selector.select(
            [ranked_document("9.9")],
            max_safeguards=1,
        )