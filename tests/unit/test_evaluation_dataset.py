import hashlib
from pathlib import Path

from evaluation.dataset import (
    RetrievalExample,
    calculate_category_counts,
    calculate_split_counts,
    calculate_text_sha256,
)


def build_examples() -> list[RetrievalExample]:
    return [
        RetrievalExample(
            id="example-001",
            question="Which safeguard applies to this case?",
            expected_safeguard_ids=["1.1"],
            category="direct",
            split="dev",
            answerable=True,
        ),
        RetrievalExample(
            id="example-002",
            question="How should this requirement be handled?",
            expected_safeguard_ids=["2.1"],
            category="paraphrase",
            split="dev",
            answerable=True,
        ),
        RetrievalExample(
            id="example-003",
            question="What is the weather forecast tomorrow?",
            expected_safeguard_ids=[],
            category="unanswerable",
            split="test",
            answerable=False,
        ),
    ]


def test_dataset_count_helpers_include_zero_categories() -> None:
    examples = build_examples()

    assert calculate_split_counts(examples) == {
        "dev": 2,
        "test": 1,
    }
    assert calculate_category_counts(examples) == {
        "direct": 1,
        "paraphrase": 1,
        "multi_safeguard": 0,
        "unanswerable": 1,
    }


def test_text_hash_normalizes_line_endings(
    tmp_path: Path,
) -> None:
    windows_file = tmp_path / "windows.txt"
    unix_file = tmp_path / "unix.txt"

    windows_file.write_bytes(
        b"first line\r\nsecond line\r\n"
    )
    unix_file.write_bytes(
        b"first line\nsecond line\n"
    )

    expected_hash = hashlib.sha256(
        b"first line\nsecond line\n"
    ).hexdigest()

    assert calculate_text_sha256(
        windows_file
    ) == expected_hash
    assert calculate_text_sha256(
        unix_file
    ) == expected_hash