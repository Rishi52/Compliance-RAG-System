from time import perf_counter

from config.settings import settings
from generation.context_selector import SafeguardContextSelector
from generation.generator import ComplianceGenerator
from retrieval.hybrid_retriever import HybridRetriever


EXIT_COMMANDS = {"exit", "quit", "q"}


def display_sources(sources: list[dict]) -> None:
    """Print source information for a generated answer."""

    if not sources:
        print("\nSources: None")
        return

    print("\nSources:")

    for source in sources:
        print(
            f"- [{source['source_id']}] "
            f"Control {source['control_id']}, "
            f"Safeguard {source['safeguard_id']}, "
            f"Page {source['page']}: "
            f"{source['safeguard_name']}"
        )


def main() -> None:
    """Run the grounded Compliance RAG command-line chat."""

    print("Loading Compliance RAG services...")

    retriever = HybridRetriever()
    context_selector = SafeguardContextSelector()
    generator = ComplianceGenerator()

    print(
        f"Ready. Model: {settings.ollama_model}. "
        "Type 'exit' to stop."
    )

    while True:
        try:
            query = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if query.lower() in EXIT_COMMANDS:
            print("Exiting.")
            break

        if not query:
            print("Please enter a question.")
            continue

        started_at = perf_counter()

        try:
            ranked_documents = retriever.search(
                query=query,
                k=settings.final_top_k,
            )

            selected_documents = context_selector.select(
                ranked_documents
            )

            result = generator.generate(
                query=query,
                documents=selected_documents,
            )
        except Exception as error:
            print(
                f"\nUnable to process the question: {error}"
            )
            continue

        elapsed_seconds = perf_counter() - started_at

        print(f"\nAnswer:\n{result['answer']}")
        display_sources(result["sources"])

        print(
            f"\nCitation valid: "
            f"{result['citation_valid']}"
        )
        print(
            f"Generation attempts: "
            f"{result['generation_attempts']}"
        )
        print(f"Time: {elapsed_seconds:.2f} seconds")


if __name__ == "__main__":
    main()