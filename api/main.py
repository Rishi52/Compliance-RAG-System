import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from config.settings import settings


logger = logging.getLogger(__name__)
router = APIRouter()

Services = tuple[Any, Any, Any]
ServiceFactory = Callable[[], Services]


class QuestionRequest(BaseModel):
    """Incoming compliance question."""

    question: str = Field(
        min_length=1,
        max_length=settings.max_question_length,
    )

    @field_validator("question")
    @classmethod
    def strip_and_validate_question(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Question cannot be empty.")

        return value


class SourceResponse(BaseModel):
    """Evidence source returned to the client."""

    source_id: str
    chunk_id: str
    control_id: str
    control_name: str
    safeguard_id: str
    safeguard_name: str
    page: int


class ChatResponse(BaseModel):
    """Grounded answer with its source records."""

    answer: str
    sources: list[SourceResponse]
    citation_valid: bool
    generation_attempts: int


def build_services() -> Services:
    """Construct production services only during API startup."""

    from generation.context_selector import (
        SafeguardContextSelector,
    )
    from generation.generator import ComplianceGenerator
    from retrieval.hybrid_retriever import HybridRetriever

    return (
        HybridRetriever(),
        SafeguardContextSelector(),
        ComplianceGenerator(),
    )


def clear_services(application: FastAPI) -> None:
    """Remove application service references."""

    application.state.retriever = None
    application.state.context_selector = None
    application.state.generator = None


def get_services(request: Request) -> Services:
    """Return initialized services or report unavailability."""

    services = (
        getattr(request.app.state, "retriever", None),
        getattr(
            request.app.state,
            "context_selector",
            None,
        ),
        getattr(request.app.state, "generator", None),
    )

    if any(service is None for service in services):
        raise HTTPException(
            status_code=503,
            detail="Application services are not ready.",
        )

    return services


def create_lifespan(service_factory: ServiceFactory):
    """Create an application lifespan using supplied services."""

    @asynccontextmanager
    async def application_lifespan(
        application: FastAPI,
    ):
        clear_services(application)

        logger.info(
            "Loading retrieval and generation services."
        )

        try:
            services = service_factory()

            if (
                not isinstance(services, tuple)
                or len(services) != 3
                or any(
                    service is None
                    for service in services
                )
            ):
                raise RuntimeError(
                    "The service factory must return three "
                    "initialized services."
                )

            (
                application.state.retriever,
                application.state.context_selector,
                application.state.generator,
            ) = services
        except Exception:
            clear_services(application)
            logger.exception(
                "Compliance RAG service startup failed."
            )
            raise

        logger.info("Compliance RAG services are ready.")

        try:
            yield
        finally:
            clear_services(application)
            logger.info(
                "Compliance RAG services were released."
            )

    return application_lifespan


def create_app(
    service_factory: ServiceFactory = build_services,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Evidence-grounded CIS Controls "
            "question-answering API."
        ),
        lifespan=create_lifespan(service_factory),
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    application.include_router(router)

    return application


@router.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Compliance RAG is running.",
        "version": settings.app_version,
    }


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Confirm that the API process is running."""

    return {"status": "alive"}


@router.get("/health/ready")
def readiness(request: Request) -> dict[str, Any]:
    """Confirm retrieval and generation are initialized."""

    retriever, _, _ = get_services(request)

    try:
        indexed_chunks = int(
            retriever.vector.collection.count()
        )
    except Exception as error:
        logger.exception(
            "Retrieval index readiness check failed."
        )

        raise HTTPException(
            status_code=503,
            detail="Unable to verify retrieval index.",
        ) from error

    return {
        "status": "ready",
        "indexed_chunks": indexed_chunks,
        "generation_model": settings.ollama_model,
    }


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    payload: QuestionRequest,
    request: Request,
) -> ChatResponse:
    """Retrieve evidence and generate a grounded answer."""

    retriever, context_selector, generator = (
        get_services(request)
    )

    try:
        ranked_documents = retriever.search(
            query=payload.question,
            k=settings.final_top_k,
        )

        selected_documents = context_selector.select(
            ranked_documents
        )

        result = generator.generate(
            query=payload.question,
            documents=selected_documents,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception(
            "Compliance question processing failed."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to process the compliance question."
            ),
        ) from error

    sources = [
        SourceResponse(**source)
        for source in result["sources"]
    ]

    return ChatResponse(
        answer=result["answer"],
        sources=sources,
        citation_valid=result["citation_valid"],
        generation_attempts=result["generation_attempts"],
    )


app = create_app()