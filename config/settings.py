from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Central configuration for the Compliance RAG application."""

    app_name: str = "Compliance RAG"

    # Data files
    cis_pdf_filename: str = "CIS_Controls_Guide_v8.1.2_0325_v2.pdf"
    safeguards_filename: str = "cis_safeguards.json"
    chunked_safeguards_filename: str = "chunked_safeguards.json"
 
    # CIS document extraction range
    control_start_page: int = 20
    control_end_page: int = 95

    # Retrieval models
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Generation model
    ollama_model: str = "llama3.2:1b"
    ollama_temperature: float = 0.0

    # ChromaDB
    chroma_directory_name: str = "chroma_db"
    chroma_collection: str = "cis_controls"

    # Retrieval configuration
    vector_candidates: int = 20
    bm25_candidates: int = 20
    final_top_k: int = 3
    rrf_k: int = 60

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="COMPLIANCE_RAG_",
        extra="ignore",
    )

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
        return self.processed_data_directory / self.safeguards_filename

    @property
    def chunked_safeguards_path(self) -> Path:
        return (
            self.processed_data_directory
            / self.chunked_safeguards_filename
        )

    @property
    def chroma_path(self) -> Path:
        return PROJECT_ROOT / self.chroma_directory_name


settings = Settings()