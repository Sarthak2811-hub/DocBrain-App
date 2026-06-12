import json
import logging
from typing import Generator, Tuple, List
from sqlalchemy.orm import Session
from app.models.document import Document
from app.services.vector_store import VectorStore
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Orchestrates retrieval of relevant text chunks and answer generation using Gemini."""

    def __init__(self):
        self.vector_store = VectorStore()
        self.ai_service = AIService()

    def run_rag_stream(
        self, 
        db: Session, 
        user_id: int, 
        document_id: int, 
        question: str
    ) -> Tuple[List[int], Generator[str, None, None]]:
        """
        Execute RAG pipeline:
        1. Retrieve top similar chunks from ChromaDB for the document
        2. Construct system instructions and prompt with context
        3. Stream answer from Gemini
        4. Return cited page numbers list and response text generator
        """
        # Validate document ownership and readiness
        doc = db.query(Document).filter(
            Document.id == document_id, 
            Document.owner_id == user_id
        ).first()
        
        if not doc:
            raise ValueError("Document not found or access denied.")
        if doc.status != "completed":
            raise ValueError(f"Document is not ready for chat. Current status: {doc.status}")

        # 1. Retrieve similar chunks
        try:
            chunks = self.vector_store.search_similar_chunks(
                query_text=question,
                document_ids=[document_id],
                limit=5
            )
        except Exception as e:
            logger.error(f"Failed to query vector store: {str(e)}")
            chunks = []

        # 2. Extract context and compile sources
        context_parts = []
        sources = []
        for chunk in chunks:
            context_parts.append(chunk["text"])
            meta = chunk.get("metadata", {})
            page = meta.get("page_number")
            if page and page not in sources:
                sources.append(page)

        context = "\n\n---\n\n".join(context_parts)
        sources.sort()

        # 3. Augment prompt and run generation
        system_instruction = (
            "You are DocBrain, an advanced AI document assistant. Your job is to answer "
            "questions based ONLY on the provided context. If the answer cannot be found "
            "in the context, politely state that the answer is not present in the document. "
            "Do not use external knowledge or fabricate facts. Always reference the page "
            "numbers of the context you used in your response."
        )

        prompt = f"Document Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        # Stream generator
        stream = self.ai_service.generate_stream(
            prompt=prompt,
            system_instruction=system_instruction
        )

        return sources, stream
