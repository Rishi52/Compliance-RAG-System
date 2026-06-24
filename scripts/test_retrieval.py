import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)

client = chromadb.PersistentClient(
    path="chroma_db"
)

collection = client.get_collection(
    "cis_controls"
)

query = "How should an organization maintain asset inventory?"

query_embedding = model.encode(query).tolist()

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

for i in range(3):

    print("=" * 80)

    print(
        results["metadatas"][0][i]
    )

    print()

    print(
        results["documents"][0][i][:500]
    )