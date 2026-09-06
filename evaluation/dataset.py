from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from config.settings import settings


EVALUATION_ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET_PATH = (
    EVALUATION_ROOT
    / "datasets"
    / "retrieval_benchmark.jsonl"
)
DEFAULT_MANIFEST_PATH = (
    EVALUATION_ROOT / "datasets" / "manifest.json"
)

SAFEGUARD_ID_PATTERN = re.compile(r"^\d+\.\d+$")

DATASET_SPLITS = (
    "dev",
    "test",
)

DATASET_CATEGORIES = (
    "direct",
    "paraphrase",
    "multi_safeguard",
    "unanswerable",
)

class RetrievalExample(BaseModel):
    """One gold-labelled retrieval evaluation question."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    question: str = Field(min_length=10)
    expected_safeguard_ids: list[str]
    category: Literal[
        "direct",
        "paraphrase",
        "multi_safeguard",
        "unanswerable",
    ]
    split: Literal["dev", "test"]
    answerable: bool

    @field_validator("id", "question")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be blank.")

        return value

    @field_validator("expected_safeguard_ids")
    @classmethod
    def validate_safeguard_ids(
        cls,
        values: list[str],
    ) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError(
                "Expected safeguard IDs must be unique."
            )

        for safeguard_id in values:
            if not SAFEGUARD_ID_PATTERN.fullmatch(
                safeguard_id
            ):
                raise ValueError(
                    f"Invalid safeguard ID: {safeguard_id}"
                )

        return values

    @model_validator(mode="after")
    def validate_answerability(self) -> RetrievalExample:
        if self.answerable and not self.expected_safeguard_ids:
            raise ValueError(
                "Answerable questions require expected safeguards."
            )

        if not self.answerable and self.expected_safeguard_ids:
            raise ValueError(
                "Unanswerable questions cannot have expected safeguards."
            )

        if (
            self.category == "unanswerable"
            and self.answerable
        ):
            raise ValueError(
                "Unanswerable category requires answerable=false."
            )

        return self


def load_manifest(
    path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Load the evaluation provenance manifest."""

    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation manifest was not found at: {path}"
        )

    manifest = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(manifest, dict):
        raise ValueError(
            "Evaluation manifest must be a JSON object."
        )

    return manifest


def load_examples(
    path: Path = DEFAULT_DATASET_PATH,
) -> list[RetrievalExample]:
    """Load and validate JSONL evaluation examples."""

    if not path.exists():
        raise FileNotFoundError(
            f"Evaluation dataset was not found at: {path}"
        )

    examples: list[RetrievalExample] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        try:
            example = RetrievalExample.model_validate_json(
                line
            )
        except Exception as error:
            raise ValueError(
                f"Invalid evaluation record on line "
                f"{line_number}: {error}"
            ) from error

        examples.append(example)

    if not examples:
        raise ValueError("Evaluation dataset is empty.")

    example_ids = [example.id for example in examples]

    if len(example_ids) != len(set(example_ids)):
        raise ValueError(
            "Evaluation example IDs must be unique."
        )

    return examples

def calculate_split_counts(
    examples: list[RetrievalExample],
) -> dict[str, int]:
    """Count examples in every supported dataset split."""

    return {
        split: sum(
            example.split == split
            for example in examples
        )
        for split in DATASET_SPLITS
    }


def calculate_category_counts(
    examples: list[RetrievalExample],
) -> dict[str, int]:
    """Count examples in every supported category."""

    return {
        category: sum(
            example.category == category
            for example in examples
        )
        for category in DATASET_CATEGORIES
    }


def calculate_text_sha256(path: Path) -> str:
    """Hash UTF-8 text using normalized Unix line endings."""

    text = path.read_text(encoding="utf-8")
    normalized_text = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    return hashlib.sha256(
        normalized_text.encode("utf-8")
    ).hexdigest()

def calculate_file_sha256(path: Path) -> str:
    """Calculate the SHA-256 of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def validate_dataset(
    examples: list[RetrievalExample],
    manifest: dict[str, Any],
    dataset_path: Path = DEFAULT_DATASET_PATH,
) -> None:
    """Validate gold labels and corpus provenance."""

    safeguard_records = json.loads(
        settings.safeguards_path.read_text(
            encoding="utf-8"
        )
    )

    available_safeguard_ids = {
        record["safeguard_id"]
        for record in safeguard_records
    }

    expected_ids = {
        safeguard_id
        for example in examples
        for safeguard_id in example.expected_safeguard_ids
    }

    unknown_ids = expected_ids - available_safeguard_ids

    if unknown_ids:
        raise ValueError(
            f"Unknown gold safeguard IDs: "
            f"{sorted(unknown_ids)}"
        )

    manifest_count = manifest.get("question_count")

    actual_split_counts = calculate_split_counts(
        examples
    )
    expected_split_counts = manifest.get(
        "split_counts"
    )

    if expected_split_counts != actual_split_counts:
        raise ValueError(
            "Dataset split counts do not match the "
            "manifest. Expected "
            f"{expected_split_counts}, found "
            f"{actual_split_counts}."
        )

    actual_category_counts = (
        calculate_category_counts(examples)
    )
    expected_category_counts = manifest.get(
        "category_counts"
    )

    if (
        expected_category_counts
        != actual_category_counts
    ):
        raise ValueError(
            "Dataset category counts do not match the "
            "manifest. Expected "
            f"{expected_category_counts}, found "
            f"{actual_category_counts}."
        )

    expected_dataset_hash = str(
        manifest.get("dataset_file_sha256", "")
    ).lower()

    if len(expected_dataset_hash) != 64:
        raise ValueError(
            "Manifest must contain a valid "
            "dataset_file_sha256."
        )

    actual_dataset_hash = calculate_text_sha256(
        dataset_path
    )

    if actual_dataset_hash != expected_dataset_hash:
        raise ValueError(
            "Dataset hash does not match the manifest. "
            f"Expected {expected_dataset_hash}, found "
            f"{actual_dataset_hash}."
        )

    if manifest_count != len(examples):
        raise ValueError(
            f"Manifest expects {manifest_count} questions, "
            f"but the dataset contains {len(examples)}."
        )

    expected_hash = str(
        manifest.get("corpus_file_sha256", "")
    ).lower()

    actual_hash = calculate_file_sha256(
        settings.chunked_safeguards_path
    )

    if actual_hash != expected_hash:
        raise ValueError(
            "Corpus hash does not match the evaluation "
            "manifest. Expected "
            f"{expected_hash}, found {actual_hash}."
        )


def main() -> None:
    examples = load_examples()
    manifest = load_manifest()

    validate_dataset(examples, manifest)

    category_counts = Counter(
        example.category
        for example in examples
    )
    split_counts = Counter(
        example.split
        for example in examples
    )

    print(f"Dataset: {manifest['dataset_name']}")
    print(f"Version: {manifest['dataset_version']}")
    print(f"Examples: {len(examples)}")
    print(f"Categories: {dict(category_counts)}")
    print(f"Splits: {dict(split_counts)}")
    print(
        "Dataset SHA-256:",
        manifest["dataset_file_sha256"],
    )
    print(
        "Corpus SHA-256:",
        manifest["corpus_file_sha256"],
    )
    print("Evaluation dataset validation passed.")


if __name__ == "__main__":
    main()