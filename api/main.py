from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from retrieval.hybrid_retriever import HybridRetriever
from langchain_ollama import ChatOllama

from config.prompt_loader import load_prompt

app = FastAPI(
    title="Compliance RAG"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = HybridRetriever()

llm = ChatOllama(
    model="llama3.2:1b",
    temperature=0
)

SYSTEM_PROMPT = load_prompt()


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {
        "message": "Compliance RAG Running"
    }


@app.post("/chat")
def chat(request: QuestionRequest):

    query = request.question

    docs = retriever.search(
        query=query,
        k=2
    )

    context = ""

    for doc in docs:

        meta = doc["metadata"]

        context += f"""
Control ID: {meta['control_id']}
Safeguard ID: {meta['safeguard_id']}
Page: {meta['page']}

{doc['content']}

------------------------------------
"""

    prompt = f"""
You are a cybersecurity compliance auditor.

Answer ONLY using the provided context.

Rules:

- Give a concise answer.
- Use bullet points whenever possible.
- Do NOT explain your reasoning.
- Do NOT discuss retrieved chunks.
- Do NOT mention irrelevant controls.
- If the answer is not present, respond exactly:

Insufficient compliance data found.

Context:

{context}

Question:
{query}
"""

    response = llm.invoke(prompt)

    sources = []

    for doc in docs:
        meta = doc["metadata"]

        sources.append({
            "control_id": meta["control_id"],
            "control_name": meta["control_name"],
            "safeguard_id": meta["safeguard_id"],
            "safeguard_name": meta["safeguard_name"],
            "page": meta["page"]
        })

    return {
        "answer": response.content,
        "sources": sources
    }