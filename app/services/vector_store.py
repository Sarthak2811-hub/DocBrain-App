import logging
import chromadb
from chromadb.config import Settings as ChromaSettings
from google import genai
from app.core.config import settings
from app.core.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class VectorStore:
    """Wrapper around ChromaDB for semantic search indexing using Gemini embeddings."""

    def __init__(self):
        # 1. ChromaDB persistent client setup karo
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        # 2. Main collection create ya fetch karo
        self.collection = self.chroma_client.get_or_create_collection(
            name="docbrain_chunks"
        )

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of texts using Google Gemini API."""
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is missing! Please obtain one from Google AI Studio "
                "and set it in your .env file."
            )
        
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = retry_with_backoff(
                client.models.embed_content,
                model=settings.GEMINI_EMBEDDING_MODEL,
                contents=texts
            )
            # Embedding structures extract karke vectors return karo
            return [e.values for e in response.embeddings]
        except Exception as e:
            logger.error(f"Error generating embeddings with Gemini: {str(e)}")
            raise e

    def add_document_chunks(
        self, 
        document_id: int, 
        chunks: list[str], 
        metadatas: list[dict]
    ) -> None:
        if not chunks:
            return

        embeddings = self._get_embeddings(chunks)
        
        ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]
        
        
        for meta in metadatas:
            meta["document_id"] = document_id

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )
        logger.info(f"Successfully added {len(chunks)} chunks for document_id {document_id} to vector store.")

    def search_similar_chunks(
        self, 
        query_text: str, 
        document_ids: list[int], 
        limit: int = 5
    ) -> list[dict]:
        if not document_ids:
            return []

        query_embeddings = self._get_embeddings([query_text])[0]

        if len(document_ids) == 1:
            where_filter = {"document_id": document_ids[0]}
        else:
            where_filter = {"document_id": {"$in": document_ids}}

        results = self.collection.query(
            query_embeddings=[query_embeddings],
            n_results=limit,
            where=where_filter
        )

        retrieved_chunks = []
        if results and results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                retrieved_chunks.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0
                })
        
        return retrieved_chunks

    def delete_document_chunks(self, document_id: int) -> None:
        self.collection.delete(where={"document_id": document_id})
        logger.info(f"Cleaned up vector store chunks for document_id {document_id}.")
