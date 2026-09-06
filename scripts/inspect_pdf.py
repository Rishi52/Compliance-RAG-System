import argparse

import pdfplumber

from config.settings import settings


def inspect_page(
    page_number: int,
    character_limit: int,
) -> None:
    """Print extracted text from one PDF page."""

    if not settings.cis_pdf_path.exists():
        raise FileNotFoundError(
            f"CIS PDF was not found at: "
            f"{settings.cis_pdf_path}"
        )

    if character_limit <= 0:
        raise ValueError(
            "character_limit must be greater than zero."
        )

    with pdfplumber.open(settings.cis_pdf_path) as pdf:
        total_pages = len(pdf.pages)

        if page_number < 1 or page_number > total_pages:
            raise ValueError(
                f"Page must be between 1 and {total_pages}."
            )

        text = pdf.pages[page_number - 1].extract_text()

    print(f"PDF: {settings.cis_pdf_path}")
    print(f"Page: {page_number}/{total_pages}")
    print("-" * 80)

    if not text:
        print("No text was extracted from this page.")
        return

    print(text[:character_limit])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect extracted text from the CIS PDF."
    )

    parser.add_argument(
        "--page",
        type=int,
        default=settings.control_start_page,
        help="One-based PDF page number.",
    )

    parser.add_argument(
        "--characters",
        type=int,
        default=2000,
        help="Maximum number of characters to print.",
    )

    arguments = parser.parse_args()

    inspect_page(
        page_number=arguments.page,
        character_limit=arguments.characters,
    )


if __name__ == "__main__":
    main()