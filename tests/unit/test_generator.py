from typing import Any

import pytest

from generation.generator import (
    INSUFFICIENT_RESPONSE,
    ComplianceGenerator,
)


class FakeResponse:
    def __init__(self, content: Any) -> None:
        self.content = content


class FakeLLM:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[list[Any]] = []

    def invoke(
        self,
        messages: list[Any],
    ) -> FakeResponse:
        self.calls.append(list(messages))

        if not self.responses:
            raise AssertionError(
                "Fake LLM has no remaining responses."
            )

        return FakeResponse(self.responses.pop(0))


def make_document(
    chunk_id: str = "doc:1.1:000",
    safeguard_id: str = "1.1",
    content: str = "Maintain an asset inventory.",
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "content": content,
        "metadata": {
            "chunk_id": chunk_id,
            "control_id": "1",
            "control_name": "Asset Management",
            "safeguard_id": safeguard_id,
            "safeguard_name": "Maintain Inventory",
            "page": 10,
        },
    }


def build_generator(
    responses: list[Any],
    max_attempts: int = 2,
) -> tuple[ComplianceGenerator, FakeLLM]:
    fake_llm = FakeLLM(responses)

    generator = ComplianceGenerator(
        llm=fake_llm,
        system_prompt="Use only supplied evidence.",
        max_attempts=max_attempts,
    )

    return generator, fake_llm


def test_build_evidence_labels_documents_and_sources() -> None:
    documents = [
        make_document(),
        make_document(
            chunk_id="doc:2.1:000",
            safeguard_id="2.1",
            content="Maintain a software inventory.",
        ),
    ]

    evidence, sources = (
        ComplianceGenerator.build_evidence(documents)
    )

    assert "[S1]" in evidence
    assert "[S2]" in evidence
    assert "Maintain an asset inventory." in evidence
    assert "Maintain a software inventory." in evidence
    assert [
        source["source_id"]
        for source in sources
    ] == ["S1", "S2"]
    assert [
        source["chunk_id"]
        for source in sources
    ] == [
        "doc:1.1:000",
        "doc:2.1:000",
    ]


def test_build_evidence_rejects_invalid_metadata() -> None:
    document = make_document()
    document["metadata"] = "invalid"

    with pytest.raises(
        ValueError,
        match="invalid metadata",
    ):
        ComplianceGenerator.build_evidence([document])


def test_build_evidence_rejects_missing_metadata_fields() -> None:
    document = make_document()
    document["metadata"] = {
        "chunk_id": "doc:1.1:000",
    }

    with pytest.raises(
        ValueError,
        match="metadata is missing",
    ):
        ComplianceGenerator.build_evidence([document])


def test_build_evidence_rejects_empty_content() -> None:
    document = make_document(content="   ")

    with pytest.raises(
        ValueError,
        match="empty content",
    ):
        ComplianceGenerator.build_evidence([document])


def test_validate_citations_accepts_supplied_labels() -> None:
    valid, error = ComplianceGenerator.validate_citations(
        "Maintain the inventory [S1].",
        [{"source_id": "S1"}],
    )

    assert valid is True
    assert error is None


def test_validate_citations_rejects_missing_citation() -> None:
    valid, error = ComplianceGenerator.validate_citations(
        "Maintain the inventory.",
        [{"source_id": "S1"}],
    )

    assert valid is False
    assert error == (
        "The answer contains no evidence citations."
    )


def test_validate_citations_rejects_unknown_label() -> None:
    valid, error = ComplianceGenerator.validate_citations(
        "Maintain the inventory [S2].",
        [{"source_id": "S1"}],
    )

    assert valid is False
    assert error is not None
    assert "S2" in error


def test_insufficient_response_requires_no_citation() -> None:
    valid, error = ComplianceGenerator.validate_citations(
        INSUFFICIENT_RESPONSE,
        [],
    )

    assert valid is True
    assert error is None


def test_generate_abstains_without_documents() -> None:
    generator, fake_llm = build_generator([])

    result = generator.generate(
        query="What is required?",
        documents=[],
    )

    assert result == {
        "answer": INSUFFICIENT_RESPONSE,
        "sources": [],
        "citation_valid": True,
        "generation_attempts": 0,
    }
    assert fake_llm.calls == []


def test_generate_accepts_valid_first_response() -> None:
    generator, fake_llm = build_generator(
        ["Maintain the inventory [S1]."]
    )

    result = generator.generate(
        query="What should be maintained?",
        documents=[make_document()],
    )

    assert result["answer"] == (
        "Maintain the inventory [S1]."
    )
    assert result["citation_valid"] is True
    assert result["generation_attempts"] == 1
    assert result["sources"][0]["source_id"] == "S1"
    assert len(fake_llm.calls) == 1

    first_call = fake_llm.calls[0]

    assert first_call[0].content == (
        "Use only supplied evidence."
    )
    assert (
        "Question:\nWhat should be maintained?"
        in first_call[1].content
    )


def test_generate_retries_invalid_citations() -> None:
    generator, fake_llm = build_generator(
        [
            "Maintain the inventory.",
            "Maintain the inventory [S1].",
        ]
    )

    result = generator.generate(
        query="What should be maintained?",
        documents=[make_document()],
    )

    assert result["answer"] == (
        "Maintain the inventory [S1]."
    )
    assert result["citation_valid"] is True
    assert result["generation_attempts"] == 2
    assert len(fake_llm.calls) == 2
    assert len(fake_llm.calls[1]) == 4
    assert (
        "failed validation"
        in fake_llm.calls[1][-1].content
    )


def test_generate_abstains_after_failed_retries() -> None:
    generator, fake_llm = build_generator(
        [
            "First unsupported answer.",
            "Second unsupported answer.",
        ]
    )

    result = generator.generate(
        query="What should be maintained?",
        documents=[make_document()],
    )

    assert result["answer"] == INSUFFICIENT_RESPONSE
    assert result["citation_valid"] is False
    assert result["generation_attempts"] == 2
    assert result["validation_error"] == (
        "The answer contains no evidence citations."
    )
    assert len(fake_llm.calls) == 2


def test_generate_converts_blank_response_to_abstention() -> None:
    generator, _ = build_generator(["   "])

    result = generator.generate(
        query="What should be maintained?",
        documents=[make_document()],
    )

    assert result["answer"] == INSUFFICIENT_RESPONSE
    assert result["citation_valid"] is True
    assert result["generation_attempts"] == 1


def test_generator_rejects_non_positive_attempts() -> None:
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        ComplianceGenerator(
            llm=FakeLLM([]),
            system_prompt="Test prompt",
            max_attempts=0,
        )


def test_generate_rejects_empty_question() -> None:
    generator, _ = build_generator([])

    with pytest.raises(
        ValueError,
        match="Question cannot be empty",
    ):
        generator.generate(
            query="   ",
            documents=[make_document()],
        )


def test_generate_rejects_unsupported_model_content() -> None:
    generator, _ = build_generator(
        [["structured", "content"]]
    )

    with pytest.raises(
        TypeError,
        match="unsupported content",
    ):
        generator.generate(
            query="What should be maintained?",
            documents=[make_document()],
        )