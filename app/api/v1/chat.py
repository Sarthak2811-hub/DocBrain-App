import asyncio
import json
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.rate_limiter import check_rate_limit
from app.core.cache import get_cached_answer, set_cached_answer

from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ChatRequest, ConversationResponse, ConversationDetailResponse
from app.services.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/ask")
def ask_question(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Ask a question based on a PDF document.
    Streams back word-by-word answer via Server-Sent Events (SSE).
    """
    check_rate_limit(current_user.email)
    async def event_generator():
        # Check cache
        cached = get_cached_answer(
            user_id=current_user.id,
            document_id=request.document_id,
            question=request.question
        )

        if cached is not None:
            cached_answer, sources = cached
            logger.info(f"Serving cached answer for user {current_user.email}")

            # Get or create the Conversation record
            conv_id = request.conversation_id
            if conv_id:
                conversation = db.query(Conversation).filter(
                    Conversation.id == conv_id,
                    Conversation.user_id == current_user.id
                ).first()
                if not conversation:
                    yield {"event": "error", "data": "Conversation not found"}
                    return
            else:
                title = request.question[:50] + "..." if len(request.question) > 50 else request.question
                conversation = Conversation(
                    user_id=current_user.id,
                    document_id=request.document_id,
                    title=title
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)

            # Save User Message to Database
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=request.question
            )
            db.add(user_message)
            db.commit()

            # Stream metadata first (conversation ID and citation sources)
            yield {
                "event": "metadata",
                "data": json.dumps({
                    "conversation_id": conversation.id,
                    "sources": sources
                })
            }

            # Stream cached answer in simulated chunks
            chunks = re.split(r"(\s+)", cached_answer)
            for chunk in chunks:
                if chunk:
                    yield {
                        "event": "chunk",
                        "data": chunk
                    }
                    await asyncio.sleep(0.01)

            # Save Assistant Response Message to Database
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=cached_answer,
                sources=json.dumps(sources)
            )
            db.add(assistant_message)
            db.commit()

            yield {
                "event": "done",
                "data": ""
            }
            return

        pipeline = RAGPipeline()
        
        # 1. Start RAG pipeline and get stream/sources
        try:
            sources, stream = pipeline.run_rag_stream(
                db=db,
                user_id=current_user.id,
                document_id=request.document_id,
                question=request.question
            )
        except Exception as e:
            logger.error(f"Error starting RAG stream: {str(e)}")
            yield {"event": "error", "data": str(e)}
            return

        # 2. Get or create the Conversation record
        conv_id = request.conversation_id
        if conv_id:
            conversation = db.query(Conversation).filter(
                Conversation.id == conv_id,
                Conversation.user_id == current_user.id
            ).first()
            if not conversation:
                yield {"event": "error", "data": "Conversation not found"}
                return
        else:
            # Generate short title from the user's question
            title = request.question[:50] + "..." if len(request.question) > 50 else request.question
            conversation = Conversation(
                user_id=current_user.id,
                document_id=request.document_id,
                title=title
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        # 3. Save User Message to Database
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.question
        )
        db.add(user_message)
        db.commit()

        # 4. Stream metadata to client first (conversation ID and citation sources)
        yield {
            "event": "metadata",
            "data": json.dumps({
                "conversation_id": conversation.id,
                "sources": sources
            })
        }

        # 5. Stream words/chunks from Gemini LLM
        accumulated_answer = ""
        try:
            for chunk in stream:
                accumulated_answer += chunk
                yield {
                    "event": "chunk",
                    "data": chunk
                }
        except Exception as e:
            logger.error(f"Error reading Gemini stream: {str(e)}")
            yield {"event": "error", "data": "Failed during stream generation"}
            return

        # 6. Save Assistant Response Message to Database
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=accumulated_answer,
            sources=json.dumps(sources)
        )
        db.add(assistant_message)
        db.commit()

        # Cache the result for future identical questions
        try:
            set_cached_answer(
                user_id=current_user.id,
                document_id=request.document_id,
                question=request.question,
                answer=accumulated_answer,
                sources=sources
            )
        except Exception as e:
            logger.error(f"Error setting cache: {str(e)}")

        # 7. Close SSE connection
        yield {
            "event": "done",
            "data": ""
        }


    return EventSourceResponse(event_generator())


@router.get("/conversations", response_model=list[ConversationResponse])
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all conversations for the current logged-in user."""
    return db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve full messages list for a specific conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation and all its messages."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    db.delete(conversation)
    db.commit()
    return
