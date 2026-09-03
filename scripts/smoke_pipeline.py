import re

from config.settings import settings
from generation.context_selector import SafeguardContextSelector
from generation.generator import ComplianceGenerator
from retrieval.hybrid_retriever import HybridRetriever


QUESTION = (
    "How often should the enterprise asset inventory "
    "be reviewed and updated?"
)
EXPECTED_SAFEGUARD_ID = "1.1"


def main() -> None:
    """Run one deterministic end-to-end pipeline smoke test."""

    print("Loading pipeline...")

    retriever = HybridRetriever()
    context_selector = SafeguardContextSelector()
    generator = ComplianceGenerator()

    ranked_documents = retriever.search(
        query=QUESTION,
        k=settings.final_top_k,
    )

    if not ranked_documents:
        raise RuntimeError("Retrieval returned no documents.")

    top_safeguard_id = str(
        ranked_documents[0]["metadata"]["safeguard_id"]
    )

    if top_safeguard_id != EXPECTED_SAFEGUARD_ID:
        raise RuntimeError(
            "Unexpected top safeguard: "
            f"{top_safeguard_id}. "
            f"Expected: {EXPECTED_SAFEGUARD_ID}"
        )

    selected_documents = context_selector.select(
        ranked_documents
    )

    selected_safeguard_ids = {
        str(document["metadata"]["safeguard_id"])
        for document in selected_documents
    }

    if selected_safeguard_ids != {
        EXPECTED_SAFEGUARD_ID
    }:
        raise RuntimeError(
            "Context selection included unexpected safeguards: "
            f"{sorted(selected_safeguard_ids)}"
        )

    result = generator.generate(
        query=QUESTION,
        documents=selected_documents,
    )

    if not result["citation_valid"]:
        raise RuntimeError(
            "Generation returned invalid citations."
        )

    normalized_answer = re.sub(
        r"[^a-z]",
        "",
        result["answer"].lower(),
    )

    if "biannually" not in normalized_answer:
        raise RuntimeError(
            "Answer did not contain the expected "
            "bi-annual review frequency."
        )

    print(
        "Ranked safeguards:",
        [
            document["metadata"]["safeguard_id"]
            for document in ranked_documents
        ],
    )
    print(
        "Selected chunks:",
        [
            document["chunk_id"]
            for document in selected_documents
        ],
    )
    print("Answer:", result["answer"])
    print("Sources:", result["sources"])
    print("Citation valid:", result["citation_valid"])
    print("Smoke test passed.")


if __name__ == "__main__":
    main()