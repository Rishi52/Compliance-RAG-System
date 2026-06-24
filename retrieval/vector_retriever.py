import chromadb
from sentence_transformers import SentenceTransformer


class VectorRetriever:

    def __init__(
        self,
        db_path="chroma_db",
        collection_name="cis_controls",
        embedding_model="BAAI/bge-small-en-v1.5"
    ):

        self.model = SentenceTransformer(embedding_model)

        self.client = chromadb.PersistentClient(
            path=db_path
        )

        self.collection = self.client.get_collection(
            collection_name
        )

    def search(self, query, k=5):

        query_embedding = self.model.encode(
            query
        ).tolist()

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )

        formatted_results = []

        for doc, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):

            formatted_results.append(
                {
                    "score": 1 - distance,
                    "content": doc,
                    "metadata": metadata
                }
            )

        return formatted_results