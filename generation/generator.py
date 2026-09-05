import re
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_ollama import ChatOllama

from config.prompt_loader import load_prompt
from config.settings import settings


INSUFFICIENT_RESPONSE = "Insufficient compliance data found."
CITATION_PATTERN = re.compile(r"\[(S\d+)\]")

REQUIRED_METADATA_FIELDS = {
    "chunk_id",
    "control_id",
    "control_name",
    "safeguard_id",
    "safeguard_name",
    "page",
}


class ComplianceGenerator:
    """Generate citation-validated answers from CIS evidence."""

    def __init__(
        self,
        llm: Any | None = None,
        system_prompt: str | None = None,
        max_attempts: int | None = None,
    ) -> None:
        self.llm = llm or ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.ollama_temperature,
        )

        self.system_prompt = system_prompt or load_prompt()
        self.max_attempts = (
            max_attempts
            if max_attempts is not None
            else settings.generation_max_attempts
        )

        if self.max_attempts <= 0:
            raise ValueError(
                "generation_max_attempts must be greater than zero."
            )

    @staticmethod
    def build_evidence(
        documents: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Build labeled evidence and public source metadata."""

        evidence_blocks: list[str] = []
        sources: list[dict[str, Any]] = []

        for position, document in enumerate(
            documents,
            start=1,
        ):
            metadata = document.get("metadata")

            if not isinstance(metadata, dict):
                raise ValueError(
                    f"Document {position} has invalid metadata."
                )

            missing_fields = (
                REQUIRED_METADATA_FIELDS - metadata.keys()
            )

            if missing_fields:
                raise ValueError(
                    f"Document {position} metadata is missing: "
                    f"{sorted(missing_fields)}"
                )

            content = str(document.get("content", "")).strip()

            if not content:
                raise ValueError(
                    f"Document {position} has empty content."
                )

            source_id = f"S{position}"

            evidence_blocks.append(
                f"[{source_id}]\n"
                f"Control: {metadata['control_id']} - "
                f"{metadata['control_name']}\n"
                f"Safeguard: {metadata['safeguard_id']} - "
                f"{metadata['safeguard_name']}\n"
                f"Page: {metadata['page']}\n"
                f"Evidence:\n{content}"
            )

            sources.append(
                {
                    "source_id": source_id,
                    "chunk_id": metadata["chunk_id"],
                    "control_id": metadata["control_id"],
                    "control_name": metadata["control_name"],
                    "safeguard_id": metadata["safeguard_id"],
                    "safeguard_name": metadata["safeguard_name"],
                    "page": metadata["page"],
                }
            )

        return "\n\n".join(evidence_blocks), sources

    @staticmethod
    def validate_citations(
        answer: str,
        sources: list[dict[str, Any]],
    ) -> tuple[bool, str | None]:
        """Check that an answer cites only supplied evidence labels."""

        if answer == INSUFFICIENT_RESPONSE:
            return True, None

        allowed_labels = {
            source["source_id"]
            for source in sources
        }
        cited_labels = set(CITATION_PATTERN.findall(answer))

        if not cited_labels:
            return False, "The answer contains no evidence citations."

        invalid_labels = cited_labels - allowed_labels

        if invalid_labels:
            return (
                False,
                "The answer contains invalid citations: "
                f"{sorted(invalid_labels)}",
            )

        return True, None

    def generate(
        self,
        query: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate an answer and retry once if citations are invalid."""

        query = query.strip()

        if not query:
            raise ValueError("Question cannot be empty.")

        if not documents:
            return {
                "answer": INSUFFICIENT_RESPONSE,
                "sources": [],
                "citation_valid": True,
                "generation_attempts": 0,
            }

        evidence, sources = self.build_evidence(documents)

        user_prompt = (
            "Answer the question using only the evidence below.\n"
            "Use the source labels in square brackets after every "
            "supported claim.\n\n"
            f"Evidence:\n{evidence}\n\n"
            f"Question:\n{query}"
        )

        messages: list[Any] = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]

        last_error: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            response = self.llm.invoke(messages)

            if not isinstance(response.content, str):
                raise TypeError(
                    "The language model returned unsupported content."
                )

            answer = response.content.strip()

            if not answer:
                answer = INSUFFICIENT_RESPONSE

            citation_valid, validation_error = (
                self.validate_citations(answer, sources)
            )

            if citation_valid:
                return {
                    "answer": answer,
                    "sources": sources,
                    "citation_valid": True,
                    "generation_attempts": attempt,
                }

            last_error = validation_error

            messages.extend(
                [
                    AIMessage(content=answer),
                    HumanMessage(
                        content=(
                            "Rewrite the answer. It failed validation: "
                            f"{validation_error} "
                            "Use only the supplied evidence labels and "
                            "place citations after every factual claim."
                        )
                    ),
                ]
            )

        return {
            "answer": INSUFFICIENT_RESPONSE,
            "sources": sources,
            "citation_valid": False,
            "generation_attempts": self.max_attempts,
            "validation_error": last_error,
        }