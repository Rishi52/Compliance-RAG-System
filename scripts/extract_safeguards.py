import json
import re
from pathlib import Path
from typing import Any

import pdfplumber

from config.settings import settings


CONTROL_PATTERN = re.compile(
    r"^\s*CONTROL\s+(\d+)\s*$",
    re.IGNORECASE,
)

SAFEGUARD_PATTERN = re.compile(
    r"^\s*Safeguard\s+(\d+\.\d+):\s*(.+?)\s*$",
    re.IGNORECASE,
)


def normalize_line(line: str) -> str:
    """Remove repeated whitespace from an extracted PDF line."""

    return " ".join(line.split()).strip()


def extract_safeguards(
    pdf_path: Path,
    start_page: int,
    end_page: int,
) -> list[dict[str, Any]]:
    """Extract CIS safeguards while preserving their source metadata."""

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"CIS PDF was not found at: {pdf_path}"
        )

    records: list[dict[str, Any]] = []

    current_control_id: str | None = None
    current_control_name: str | None = None
    current_record: dict[str, Any] | None = None
    content_lines: list[str] = []
    expecting_control_name = False
    expecting_safeguard_name_continuation = False

    def save_current_record() -> None:
        nonlocal current_record
        nonlocal content_lines
        nonlocal expecting_safeguard_name_continuation

        if current_record is None:
            return

        content = "\n".join(content_lines).strip()

        if content:
            current_record["content"] = content
            records.append(current_record)

        current_record = None
        content_lines = []
        expecting_safeguard_name_continuation = False

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        if start_page < 1 or end_page > total_pages:
            raise ValueError(
                "Invalid extraction range: "
                f"{start_page}-{end_page}. "
                f"The PDF contains {total_pages} pages."
            )

        selected_pages = pdf.pages[start_page - 1 : end_page]

        for page_number, page in enumerate(
            selected_pages,
            start=start_page,
        ):
            page_text = page.extract_text()

            if not page_text:
                continue

            for raw_line in page_text.splitlines():
                line = normalize_line(raw_line)

                if not line:
                    continue

                control_match = CONTROL_PATTERN.match(line)

                if control_match:
                    save_current_record()

                    current_control_id = control_match.group(1)
                    current_control_name = None
                    expecting_control_name = True
                    continue

                if expecting_control_name:
                    current_control_name = line
                    expecting_control_name = False
                    continue

                safeguard_match = SAFEGUARD_PATTERN.match(line)

                if safeguard_match:
                    save_current_record()

                    safeguard_id = safeguard_match.group(1)
                    safeguard_name = safeguard_match.group(2)
                    safeguard_control_id = safeguard_id.split(".")[0]

                    # The safeguard ID is the most reliable source
                    # for its parent control.
                    if current_control_id != safeguard_control_id:
                        current_control_id = safeguard_control_id

                    current_record = {
                        "page": page_number,
                        "control_id": current_control_id,
                        "control_name": current_control_name,
                        "safeguard_id": safeguard_id,
                        "safeguard_name": safeguard_name,
                    }

                    content_lines = []
                    expecting_safeguard_name_continuation = True
                    continue

                if (
                    current_record is not None
                    and expecting_safeguard_name_continuation
                ):
                    compact_line = line.replace(" ", "")

                    body_has_started = (
                        compact_line == "|||"
                        or line.startswith("Asset Type:")
                    )

                    if body_has_started:
                        expecting_safeguard_name_continuation = False
                        content_lines.append(line)
                    else:
                        current_record["safeguard_name"] = (
                            f"{current_record['safeguard_name']} {line}"
                        ).strip()

                    continue

                if current_record is not None:
                    content_lines.append(line)

    save_current_record()

    return remove_duplicate_safeguards(records)


def remove_duplicate_safeguards(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep the first occurrence of each CIS safeguard."""

    unique_records: dict[str, dict[str, Any]] = {}

    for record in records:
        safeguard_id = record["safeguard_id"]

        if safeguard_id not in unique_records:
            unique_records[safeguard_id] = record

    return list(unique_records.values())


def validate_records(records: list[dict[str, Any]]) -> None:
    """Validate required metadata and safeguard uniqueness."""

    if not records:
        raise ValueError("No safeguards were extracted from the PDF.")

    required_fields = {
        "page",
        "control_id",
        "control_name",
        "safeguard_id",
        "safeguard_name",
        "content",
    }

    seen_ids: set[str] = set()

    for record in records:
        missing_fields = required_fields - record.keys()

        if missing_fields:
            raise ValueError(
                f"Safeguard record is missing fields: {missing_fields}"
            )

        safeguard_id = record["safeguard_id"]

        if safeguard_id in seen_ids:
            raise ValueError(
                f"Duplicate safeguard detected: {safeguard_id}"
            )

        if not record["content"].strip():
            raise ValueError(
                f"Safeguard {safeguard_id} has empty content."
            )
        first_content_line = record["content"].splitlines()[0]
        compact_first_line = first_content_line.replace(" ", "")

        valid_body_start = (
            compact_first_line == "|||"
            or first_content_line.startswith("Asset Type:")
        )

        if not valid_body_start:
            raise ValueError(
                f"Safeguard {safeguard_id} may have an "
                "unresolved wrapped title. First content line: "
                f"{first_content_line!r}"
            )
        seen_ids.add(safeguard_id)


def save_records(
    records: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Write extracted safeguard records to JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    records = extract_safeguards(
        pdf_path=settings.cis_pdf_path,
        start_page=settings.control_start_page,
        end_page=settings.control_end_page,
    )

    validate_records(records)
    save_records(records, settings.safeguards_path)

    print(f"Source PDF: {settings.cis_pdf_path}")
    print(
        "Pages processed: "
        f"{settings.control_start_page}-"
        f"{settings.control_end_page}"
    )
    print(f"Unique safeguards extracted: {len(records)}")
    print(f"Saved to: {settings.safeguards_path}")


if __name__ == "__main__":
    main()