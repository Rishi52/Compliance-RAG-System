import chromadb
from sentence_transformers import SentenceTransformer
from langchain_ollama import ChatOllama
import time
import os
import sys
sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)
from config.prompt_loader import load_prompt

SYSTEM_PROMPT = load_prompt()
# ------------------------
# Models
# ------------------------

embedding_model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

llm = ChatOllama(
    model="llama3.2:3b",
    temperature=0
)

# ------------------------
# ChromaDB
# ------------------------

client = chromadb.PersistentClient(
    path="chroma_db"
)

collection = client.get_collection(
    "cis_controls"
)

# ------------------------
# Chat Loop
# ------------------------

while True:

    query = input("\nQuestion: ")

    if query.lower() == "exit":
        break

    query_embedding = embedding_model.encode(
        query
    ).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5
    )

    context = ""

    for doc, meta in zip(
        results["documents"][0],
        results["metadatas"][0]
    ):

        context += f"""

Control ID: {meta['control_id']}
Control Name: {meta['control_name']}

Safeguard ID: {meta['safeguard_id']}
Safeguard Name: {meta['safeguard_name']}

Page: {meta['page']}

Content:
{doc}

==================================================
"""

    final_prompt = f"""
{SYSTEM_PROMPT}

CONTEXT:

{context}

QUESTION:

{query}
"""

    start = time.time()

    response = llm.invoke(final_prompt)

    end = time.time()

    print(f"\nTime Taken: {end-start:.2f} sec")

    print("\nAnswer:\n")
    print(response.content)