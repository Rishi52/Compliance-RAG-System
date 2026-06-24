import json
import chromadb

from sentence_transformers import SentenceTransformer

DATA_PATH = "data/processed/cis_safeguards.json"

CHROMA_PATH = "chroma_db"

COLLECTION_NAME = "cis_controls"

print("Loading safeguards...")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    safeguards = json.load(f)

print(f"Loaded {len(safeguards)} safeguards")

print("Loading embedding model...")

model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

print("Creating Chroma client...")

client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)

documents = []
metadatas = []
ids = []

for item in safeguards:

    documents.append(item["content"])

    metadatas.append(
        {
            "page": item["page"],
            "control_id": item["control_id"],
            "control_name": item["control_name"],
            "safeguard_id": item["safeguard_id"],
            "safeguard_name": item["safeguard_name"]
        }
    )

    ids.append(item["safeguard_id"])

print("Generating embeddings...")

embeddings = model.encode(
    documents,
    show_progress_bar=True
).tolist()

print("Storing in ChromaDB...")

collection.add(
    ids=ids,
    documents=documents,
    embeddings=embeddings,
    metadatas=metadatas
)

print("Done!")
print(f"Stored {len(ids)} safeguards")