import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from config.settings import settings
from generation.context_selector import SafeguardContextSelector
from generation.generator import ComplianceGenerator
from retrieval.hybrid_retriever import HybridRetriever


logger = logging.getLogger(__name__)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load expensive application services once at startup."""

    logger.info("Loading retrieval and generation services.")

    app.state.retriever = HybridRetriever()
    app.state.context_selector = SafeguardContextSelector()
    app.state.generator = ComplianceGenerator()

    logger.info("Compliance RAG services are ready.")

    yield

    app.state.retriever = None
    app.state.context_selector = None
    app.state.generator = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Evidence-grounded CIS Controls question-answering API."
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    return application


app = create_app()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Compliance RAG is running.",
        "version": settings.app_version,
    }


@app.get("/health/live")
def liveness() -> dict[str, str]:
    """Confirm that the API process is running."""

    return {"status": "alive"}


@app.get("/health/ready")
def readiness(request: Request) -> dict[str, Any]:
    """Confirm that retrieval and generation are initialized."""

    retriever = getattr(
        request.app.state,
        "retriever",
        None,
    )
    context_selector = getattr(
        request.app.state,
        "context_selector",
        None,
    )
    generator = getattr(
        request.app.state,
        "generator",
        None,
    )

    if any(
        service is None
        for service in (
            retriever,
            context_selector,
            generator,
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Application services are not ready.",
        )

    return {
        "status": "ready",
        "indexed_chunks": (
            retriever.vector.collection.count()
        ),
        "generation_model": settings.ollama_model,
    }


@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    payload: QuestionRequest,
    request: Request,
) -> ChatResponse:
    """Retrieve evidence and generate a grounded answer."""

    retriever = getattr(
        request.app.state,
        "retriever",
        None,
    )
    context_selector = getattr(
        request.app.state,
        "context_selector",
        None,
    )
    generator = getattr(
        request.app.state,
        "generator",
        None,
    )

    if any(
        service is None
        for service in (
            retriever,
            context_selector,
            generator,
        )
    ):
        raise HTTPException(
            status_code=503,
            detail="Application services are not ready.",
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
            detail="Unable to process the compliance question.",
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