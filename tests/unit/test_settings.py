from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from config.settings import PROJECT_ROOT, Settings


def make_settings(**overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        **overrides,
    )


def test_default_paths_are_project_relative() -> None:
    configuration = make_settings()

    assert configuration.data_directory == (
        PROJECT_ROOT / "data"
    )
    assert configuration.cis_pdf_path == (
        PROJECT_ROOT
        / "data"
        / "raw"
        / configuration.cis_pdf_filename
    )
    assert configuration.chroma_path == (
        PROJECT_ROOT / "chroma_db"
    )
    assert configuration.prompts_path == (
        PROJECT_ROOT / "config" / "prompts.yaml"
    )


def test_cors_origins_are_normalized_and_deduplicated() -> None:
    configuration = make_settings(
        cors_origins=(
            " http://localhost:5500/,"
            "http://localhost:5500,"
            "https://example.com "
        )
    )

    assert configuration.allowed_cors_origins == [
        "http://localhost:5500",
        "https://example.com",
    ]


def test_invalid_cors_origin_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="Invalid CORS origin",
    ):
        make_settings(
            cors_origins="localhost:5500"
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("max_question_length", 0),
        ("chunk_size", 0),
        ("generation_max_attempts", 0),
        ("final_top_k", 0),
        ("rrf_k", -1),
    ],
)
def test_positive_settings_reject_non_positive_values(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field_name: value})


def test_chunk_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(
        ValidationError,
        match="chunk_overlap must be smaller",
    ):
        make_settings(
            chunk_size=100,
            chunk_overlap=100,
        )


def test_page_range_must_be_ordered() -> None:
    with pytest.raises(
        ValidationError,
        match="control_end_page",
    ):
        make_settings(
            control_start_page=20,
            control_end_page=19,
        )


def test_temperature_has_safe_range() -> None:
    with pytest.raises(ValidationError):
        make_settings(ollama_temperature=2.1)


@pytest.mark.parametrize(
    "field_name",
    [
        "app_name",
        "embedding_model",
        "ollama_model",
    ],
)
def test_required_text_rejects_blank_values(
    field_name: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="cannot be empty",
    ):
        make_settings(**{field_name: "   "})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("cis_pdf_filename", "../controls.pdf"),
        ("chroma_directory_name", "data/chroma"),
    ],
)
def test_local_names_reject_paths(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="local name",
    ):
        make_settings(**{field_name: value})
def test_ollama_url_is_normalized() -> None:
    configuration = make_settings(
        ollama_base_url="http://localhost:11434/"
    )

    assert configuration.ollama_base_url == (
        "http://localhost:11434"
    )


def test_invalid_ollama_url_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="valid HTTP URL",
    ):
        make_settings(
            ollama_base_url="localhost:11434"
        )
def test_log_level_is_normalized() -> None:
    configuration = make_settings(
        log_level="debug"
    )

    assert configuration.log_level == "DEBUG"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(log_level="verbose")