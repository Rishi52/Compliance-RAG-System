from pathlib import Path
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class Settings(BaseSettings):
    """Central configuration for the Compliance RAG application."""

    app_name: str = "Compliance RAG"
    app_version: str = "0.2.0"
    log_level: Literal[
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
    ] = "INFO"
    max_question_length: PositiveInt = 2000
    cors_origins: str = (
        "http://127.0.0.1:5500,"
        "http://localhost:5500"
    )

    # Data files
    cis_pdf_filename: str = (
        "CIS_Controls_Guide_v8.1.2_0325_v2.pdf"
    )
    safeguards_filename: str = "cis_safeguards.json"
    chunked_safeguards_filename: str = (
        "chunked_safeguards.json"
    )

    # CIS document extraction range
    control_start_page: PositiveInt = 20
    control_end_page: PositiveInt = 95

    # Chunking configuration
    document_id: str = "cis-controls-v8.1.2"
    chunk_size: PositiveInt = 1000
    chunk_overlap: NonNegativeInt = 150

    # Retrieval models
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = (
        "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    # Generation model
    ollama_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    generation_max_attempts: PositiveInt = 2
    generation_safeguards_k: PositiveInt = 1
    ollama_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
    )

    # ChromaDB
    chroma_directory_name: str = "chroma_db"
    chroma_collection: str = "cis_controls"

    # Retrieval configuration
    vector_candidates: PositiveInt = 20
    bm25_candidates: PositiveInt = 20
    final_top_k: PositiveInt = 3
    rrf_k: PositiveInt = 60

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="COMPLIANCE_RAG_",
        extra="ignore",
        validate_default=True,
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(
        cls,
        value: Any,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "Logging level must be a string."
            )

        return value.strip().upper()

    @field_validator(
        "app_name",
        "app_version",
        "document_id",
        "embedding_model",
        "reranker_model",
        "ollama_model",
        "chroma_collection",
        mode="before",
    )
    @classmethod
    def validate_required_text(
        cls,
        value: Any,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "Configuration value cannot be empty."
            )

        return value.strip()

    @field_validator(
        "cis_pdf_filename",
        "safeguards_filename",
        "chunked_safeguards_filename",
        "chroma_directory_name",
        mode="before",
    )
    @classmethod
    def validate_local_name(
        cls,
        value: Any,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "File or directory name cannot be empty."
            )

        value = value.strip()

        if (
            value in {".", ".."}
            or "/" in value
            or "\\" in value
        ):
            raise ValueError(
                "File and directory settings must contain "
                "a local name, not a path."
            )

        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(
        cls,
        value: Any,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "CORS origins must be a comma-separated string."
            )

        origins: list[str] = []

        for raw_origin in value.split(","):
            origin = raw_origin.strip().rstrip("/")

            if not origin:
                continue

            parsed = urlsplit(origin)

            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError(
                    f"Invalid CORS origin: {origin}"
                )

            try:
                parsed.port
            except ValueError as error:
                raise ValueError(
                    f"Invalid CORS origin: {origin}"
                ) from error

            if origin not in origins:
                origins.append(origin)

        if not origins:
            raise ValueError(
                "At least one valid CORS origin is required."
            )

        return ",".join(origins)

    @field_validator("ollama_base_url", mode="before")
    @classmethod
    def validate_ollama_base_url(
        cls,
        value: Any,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "Ollama base URL must be a string."
            )

        value = value.strip().rstrip("/")
        parsed = urlsplit(value)

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError(
                "Ollama base URL must be a valid HTTP URL."
            )

        try:
            parsed.port
        except ValueError as error:
            raise ValueError(
                "Ollama base URL must be a valid HTTP URL."
            ) from error

        return value

    @model_validator(mode="after")
    def validate_related_values(self) -> Self:
        if self.control_end_page < self.control_start_page:
            raise ValueError(
                "control_end_page must be greater than or "
                "equal to control_start_page."
            )

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        return self

    @property
    def data_directory(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def raw_data_directory(self) -> Path:
        return self.data_directory / "raw"

    @property
    def processed_data_directory(self) -> Path:
        return self.data_directory / "processed"

    @property
    def cis_pdf_path(self) -> Path:
        return self.raw_data_directory / self.cis_pdf_filename

    @property
    def safeguards_path(self) -> Path:
        return (
            self.processed_data_directory
            / self.safeguards_filename
        )

    @property
    def chunked_safeguards_path(self) -> Path:
        return (
            self.processed_data_directory
            / self.chunked_safeguards_filename
        )

    @property
    def chroma_path(self) -> Path:
        return PROJECT_ROOT / self.chroma_directory_name

    @property
    def prompts_path(self) -> Path:
        return PROJECT_ROOT / "config" / "prompts.yaml"

    @property
    def allowed_cors_origins(self) -> list[str]:
        return self.cors_origins.split(",")


settings = Settings()