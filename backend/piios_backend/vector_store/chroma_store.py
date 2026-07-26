import chromadb

from piios_backend.core.config import settings


class ResearchVectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=settings.vector_path)
        self.collection = self.client.get_or_create_collection(settings.vector_collection)

    def upsert_document(self, doc_id: str, text: str, metadata: dict) -> None:
        self.collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])

    def query(self, text: str, limit: int = 5) -> dict:
        return self.collection.query(query_texts=[text], n_results=limit)
