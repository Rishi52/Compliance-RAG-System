from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from config.settings import settings


SOURCE = {
    "source_id": "S1",
    "chunk_id": "cis-controls-v8.1.2:1.1:001",
    "control_id": "1",
    "control_name": (
        "Inventory and Control of Enterprise Assets"
    ),
    "safeguard_id": "1.1",
    "safeguard_name": (
        "Establish and Maintain Detailed "
        "Enterprise Asset Inventory"
    ),
    "page": 22,
}


class FakeCollection:
    def count(self) -> int:
        return 155


class FakeVector:
    def __init__(self) -> None:
        self.collection = FakeCollection()


class FakeRetriever:
    def __init__(self) -> None:
        self.vector = FakeVector()
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None
        self.results = [
            {
                "chunk_id": SOURCE["chunk_id"],
                "content": "Retrieved evidence.",
                "metadata": {
                    "safeguard_id": "1.1",
                },
            }
        ]

    def search(
        self,
        query: str,
        k: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "query": query,
                "k": k,
            }
        )

        if self.error is not None:
            raise self.error

        return self.results


class FakeContextSelector:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self.results = [
            {
                "chunk_id": SOURCE["chunk_id"],
                "content": "Selected evidence.",
                "metadata": {
                    "safeguard_id": "1.1",
                },
            }
        ]

    def select(
        self,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.calls.append(documents)
        return self.results


class FakeGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = {
            "answer": (
                "Review the inventory bi-annually, "
                "or more frequently. [S1]"
            ),
            "sources": [SOURCE],
            "citation_valid": True,
            "generation_attempts": 1,
        }

    def generate(
        self,
        query: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "query": query,
                "documents": documents,
            }
        )
        return self.result


@pytest.fixture
def services():
    return (
        FakeRetriever(),
        FakeContextSelector(),
        FakeGenerator(),
    )


@pytest.fixture
def client(services):
    application = create_app(
        service_factory=lambda: services
    )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client, services


def test_root_returns_application_information(client) -> None:
    test_client, _ = client

    response = test_client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Compliance RAG is running.",
        "version": settings.app_version,
    }


def test_liveness_returns_alive(client) -> None:
    test_client, _ = client

    response = test_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_index_and_model(client) -> None:
    test_client, _ = client

    response = test_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "indexed_chunks": 155,
        "generation_model": settings.ollama_model,
    }


def test_chat_returns_grounded_response(client) -> None:
    test_client, _ = client

    response = test_client.post(
        "/chat",
        json={"question": "How often is it reviewed?"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["citation_valid"] is True
    assert body["generation_attempts"] == 1
    assert body["sources"] == [SOURCE]
    assert "[S1]" in body["answer"]


def test_chat_strips_question_and_uses_configured_k(
    client,
) -> None:
    test_client, services = client
    retriever, _, _ = services

    response = test_client.post(
        "/chat",
        json={"question": "  Asset inventory?  "},
    )

    assert response.status_code == 200
    assert retriever.calls == [
        {
            "query": "Asset inventory?",
            "k": settings.final_top_k,
        }
    ]


def test_chat_runs_retrieve_select_generate_pipeline(
    client,
) -> None:
    test_client, services = client
    retriever, selector, generator = services

    response = test_client.post(
        "/chat",
        json={"question": "Asset inventory?"},
    )

    assert response.status_code == 200
    assert selector.calls == [retriever.results]
    assert generator.calls == [
        {
            "query": "Asset inventory?",
            "documents": selector.results,
        }
    ]


def test_chat_rejects_missing_question(client) -> None:
    test_client, _ = client

    response = test_client.post("/chat", json={})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
    ],
)
def test_chat_rejects_blank_question(
    client,
    question: str,
) -> None:
    test_client, _ = client

    response = test_client.post(
        "/chat",
        json={"question": question},
    )

    assert response.status_code == 422


def test_chat_rejects_question_over_limit(client) -> None:
    test_client, _ = client

    response = test_client.post(
        "/chat",
        json={
            "question": "x"
            * (settings.max_question_length + 1)
        },
    )

    assert response.status_code == 422


def test_chat_maps_pipeline_value_error_to_422(
    client,
) -> None:
    test_client, services = client
    retriever, _, _ = services
    retriever.error = ValueError("Invalid retrieval query.")

    response = test_client.post(
        "/chat",
        json={"question": "Asset inventory?"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Invalid retrieval query."
    }


def test_chat_hides_internal_pipeline_error(client) -> None:
    test_client, services = client
    retriever, _, _ = services
    retriever.error = RuntimeError("Private failure detail.")

    response = test_client.post(
        "/chat",
        json={"question": "Asset inventory?"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": (
            "Unable to process the compliance question."
        )
    }
    assert "Private failure detail" not in response.text


def test_readiness_returns_503_when_service_missing(
    client,
) -> None:
    test_client, _ = client
    test_client.app.state.generator = None

    response = test_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Application services are not ready."
    }


def test_chat_returns_503_when_service_missing(
    client,
) -> None:
    test_client, _ = client
    test_client.app.state.context_selector = None

    response = test_client.post(
        "/chat",
        json={"question": "Asset inventory?"},
    )

    assert response.status_code == 503


def test_cors_allows_configured_frontend(client) -> None:
    test_client, _ = client

    response = test_client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers[
        "access-control-allow-origin"
    ] == "http://localhost:5500"


def test_lifespan_cleans_up_services(services) -> None:
    application = create_app(
        service_factory=lambda: services
    )

    with TestClient(application):
        assert application.state.retriever is services[0]
        assert (
            application.state.context_selector
            is services[1]
        )
        assert application.state.generator is services[2]

    assert application.state.retriever is None
    assert application.state.context_selector is None
    assert application.state.generator is None

def test_readiness_hides_index_failure(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_client, services = client
    retriever, _, _ = services

    def fail_count() -> int:
        raise RuntimeError("Private index failure.")

    monkeypatch.setattr(
        retriever.vector.collection,
        "count",
        fail_count,
    )

    response = test_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Unable to verify retrieval index."
    }
    assert "Private index failure" not in response.text


def test_lifespan_rejects_incomplete_services() -> None:
    application = create_app(
        service_factory=lambda: (
            FakeRetriever(),
            None,
            FakeGenerator(),
        )
    )

    with pytest.raises(
        RuntimeError,
        match="three initialized services",
    ):
        with TestClient(application):
            pass

    assert application.state.retriever is None
    assert application.state.context_selector is None
    assert application.state.generator is None


def test_lifespan_cleans_up_after_factory_failure() -> None:
    def broken_factory():
        raise RuntimeError("Synthetic startup failure.")

    application = create_app(
        service_factory=broken_factory
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic startup failure",
    ):
        with TestClient(application):
            pass

    assert application.state.retriever is None
    assert application.state.context_selector is None
    assert application.state.generator is None