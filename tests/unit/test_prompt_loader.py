from pathlib import Path

import pytest

from config.prompt_loader import load_prompt


def write_prompt(
    path: Path,
    content: str,
) -> Path:
    path.write_text(content, encoding="utf-8")

    return path


def test_load_prompt_reads_and_strips_valid_yaml(
    tmp_path: Path,
) -> None:
    prompt_path = write_prompt(
        tmp_path / "prompt.yaml",
        (
            "system_prompt: |\n"
            "  You are a compliance assistant.\n"
            "  Cite the supplied evidence.\n"
        ),
    )

    result = load_prompt(prompt_path)

    assert result == (
        "You are a compliance assistant.\n"
        "Cite the supplied evidence."
    )


def test_load_prompt_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(
        FileNotFoundError,
        match="was not found",
    ):
        load_prompt(missing_path)


def test_load_prompt_rejects_invalid_yaml(
    tmp_path: Path,
) -> None:
    prompt_path = write_prompt(
        tmp_path / "invalid.yaml",
        "system_prompt: [unfinished\n",
    )

    with pytest.raises(
        ValueError,
        match="Invalid prompt YAML",
    ):
        load_prompt(prompt_path)


def test_load_prompt_requires_yaml_mapping(
    tmp_path: Path,
) -> None:
    prompt_path = write_prompt(
        tmp_path / "string.yaml",
        "just a string\n",
    )

    with pytest.raises(
        ValueError,
        match="must be a YAML mapping",
    ):
        load_prompt(prompt_path)


@pytest.mark.parametrize(
    "content",
    [
        "another_setting: value\n",
        "system_prompt: 123\n",
    ],
)
def test_load_prompt_requires_string_system_prompt(
    tmp_path: Path,
    content: str,
) -> None:
    prompt_path = write_prompt(
        tmp_path / "invalid-prompt.yaml",
        content,
    )

    with pytest.raises(
        ValueError,
        match="requires a string",
    ):
        load_prompt(prompt_path)


def test_load_prompt_rejects_empty_system_prompt(
    tmp_path: Path,
) -> None:
    prompt_path = write_prompt(
        tmp_path / "empty.yaml",
        "system_prompt: '   '\n",
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        load_prompt(prompt_path)