from pathlib import Path

import yaml

from config.settings import settings


def load_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """Load and validate the system prompt from YAML."""

    path = Path(prompt_path or settings.prompts_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Prompt configuration was not found at: {path}"
        )

    try:
        prompt_config = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )
    except yaml.YAMLError as error:
        raise ValueError(
            f"Invalid prompt YAML at: {path}"
        ) from error

    if not isinstance(prompt_config, dict):
        raise ValueError(
            "Prompt configuration must be a YAML mapping."
        )

    system_prompt = prompt_config.get("system_prompt")

    if not isinstance(system_prompt, str):
        raise ValueError(
            "Prompt configuration requires a string "
            "'system_prompt' value."
        )

    system_prompt = system_prompt.strip()

    if not system_prompt:
        raise ValueError("The system prompt cannot be empty.")

    return system_prompt