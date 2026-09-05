import json
from pathlib import Path
from typing import Any

import pytest

import scripts.extract_safeguards as extraction
from scripts.extract_safeguards import (
    extract_safeguards,
    normalize_line,
    remove_duplicate_safeguards,
    save_records,
    validate_records,
)


class FakePage:
    def __init__(self, text: str | None) -> None:
        self.text = text

    def extract_text(self) -> str | None:
        return self.text


class FakePDF:
    def __init__(
        self,
        page_texts: list[str | None],
    ) -> None:
        self.pages = [
            FakePage(text)
            for text in page_texts
        ]

    def __enter__(self) -> "FakePDF":
        return self

    def __exit__(
        self,
        exception_type: Any,
        exception: Any,
        traceback: Any,
    ) -> None:
        del exception_type
        del exception
        del traceback


def install_fake_pdf(
    monkeypatch: pytest.MonkeyPatch,
    page_texts: list[str | None],
) -> None:
    def fake_open(_: Path) -> FakePDF:
        return FakePDF(page_texts)

    monkeypatch.setattr(
        extraction.pdfplumber,
        "open",
        fake_open,
    )


def make_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "controls.pdf"
    path.write_bytes(b"synthetic PDF")

    return path


def make_record(
    safeguard_id: str = "1.1",
    content: str = (
        "| | |\n"
        "Asset Type: Devices\n"
        "Maintain the asset inventory."
    ),
) -> dict[str, Any]:
    control_id = safeguard_id.split(".")[0]

    return {
        "page": 10,
        "control_id": control_id,
        "control_name": f"Control {control_id}",
        "safeguard_id": safeguard_id,
        "safeguard_name": (
            f"Safeguard {safeguard_id}"
        ),
        "content": content,
    }


def test_normalize_line_collapses_whitespace() -> None:
    assert normalize_line(
        "  Maintain   the\tinventory  "
    ) == "Maintain the inventory"


def test_remove_duplicates_keeps_first_record() -> None:
    first = make_record(content="| | |\nFirst")
    duplicate = make_record(content="| | |\nSecond")
    second = make_record("2.1")

    result = remove_duplicate_safeguards(
        [first, duplicate, second]
    )

    assert result == [first, second]


def test_validate_records_accepts_valid_records() -> None:
    validate_records([make_record()])


def test_validate_records_rejects_empty_list() -> None:
    with pytest.raises(
        ValueError,
        match="No safeguards were extracted",
    ):
        validate_records([])


def test_validate_records_rejects_missing_fields() -> None:
    record = make_record()
    del record["control_name"]

    with pytest.raises(
        ValueError,
        match="missing fields",
    ):
        validate_records([record])


def test_validate_records_rejects_duplicates() -> None:
    record = make_record()

    with pytest.raises(
        ValueError,
        match="Duplicate safeguard",
    ):
        validate_records([record, dict(record)])


def test_validate_records_rejects_empty_content() -> None:
    with pytest.raises(
        ValueError,
        match="empty content",
    ):
        validate_records(
            [make_record(content="   ")]
        )


def test_validate_records_detects_wrapped_title() -> None:
    record = make_record(
        content=(
            "Unresolved title continuation\n"
            "| | |\n"
            "Asset Type: Devices"
        )
    )

    with pytest.raises(
        ValueError,
        match="unresolved wrapped title",
    ):
        validate_records([record])


def test_save_records_creates_parent_and_round_trips(
    tmp_path: Path,
) -> None:
    records = [make_record()]
    output_path = (
        tmp_path / "nested" / "records.json"
    )

    save_records(records, output_path)

    assert output_path.exists()
    assert json.loads(
        output_path.read_text(encoding="utf-8")
    ) == records


def test_extract_rejects_missing_pdf(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="was not found",
    ):
        extract_safeguards(
            tmp_path / "missing.pdf",
            start_page=1,
            end_page=1,
        )


def test_extract_preserves_wrapped_safeguard_title(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_text = """
CONTROL 1
Inventory and Control of Enterprise Assets
Safeguard 1.1: Establish and Maintain Detailed
Enterprise Asset Inventory
| | |
Asset Type: Devices Security Function: Identify
Maintain a complete enterprise asset inventory.
Safeguard 1.2: Address Unauthorized Assets
| | |
Asset Type: Devices Security Function: Respond
Remove or remediate unauthorized assets.
"""

    install_fake_pdf(monkeypatch, [page_text])

    records = extract_safeguards(
        make_pdf_path(tmp_path),
        start_page=1,
        end_page=1,
    )

    assert len(records) == 2
    assert records[0]["safeguard_id"] == "1.1"
    assert records[0]["safeguard_name"] == (
        "Establish and Maintain Detailed "
        "Enterprise Asset Inventory"
    )
    assert records[0]["page"] == 1
    assert records[0]["content"].startswith("| | |")
    assert records[1]["safeguard_id"] == "1.2"


@pytest.mark.parametrize(
    ("start_page", "end_page"),
    [
        (0, 1),
        (2, 1),
        (1, 2),
    ],
)
def test_extract_rejects_invalid_page_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    start_page: int,
    end_page: int,
) -> None:
    install_fake_pdf(monkeypatch, ["Page one"])

    with pytest.raises(
        ValueError,
        match="Invalid extraction range",
    ):
        extract_safeguards(
            make_pdf_path(tmp_path),
            start_page=start_page,
            end_page=end_page,
        )


def test_extract_skips_pages_without_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_text = """
CONTROL 2
Inventory and Control of Software Assets
Safeguard 2.1: Establish Software Inventory
| | |
Asset Type: Software Security Function: Identify
Maintain an accurate software inventory.
"""

    install_fake_pdf(
        monkeypatch,
        [None, page_text],
    )

    records = extract_safeguards(
        make_pdf_path(tmp_path),
        start_page=1,
        end_page=2,
    )

    assert len(records) == 1
    assert records[0]["page"] == 2
    assert records[0]["safeguard_id"] == "2.1"