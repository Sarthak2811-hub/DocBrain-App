import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_current_user_optional_query, get_db
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_processor import process_document
from app.services.vector_store import VectorStore
logger = logging.getLogger(__name__)
router = APIRouter()
# Background task helper function
def process_document_task(document_id: int) -> None:
    db = SessionLocal()
    try:
        process_document(db, document_id)
    finally:
        db.close()
# 1. Upload File Endpoint
@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # File validation check (PDF, TXT, DOCX)
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in [".pdf", ".txt", ".docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, TXT, and DOCX files are supported"
        )

    
    # Target directory setup
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
    # Unique file storage path generate
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    # File save operation
    try:
        file_size = 0
        with open(file_path, "wb") as f:
            while content := file.file.read(1024 * 1024):  # 1MB chunks
                file_size += len(content)
                if file_size > settings.MAX_FILE_SIZE * 1024 * 1024:
                    # Cleanup on size overflow
                    f.close()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE}MB"
                    )
                f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file on server"
        )

    # Database pending state insert
    new_doc = Document(
        owner_id=current_user.id,
        original_filename=file.filename,
        file_size=file_size,
        storage_path=file_path,
        status="pending"
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # Asynchronous background processing
    background_tasks.add_task(process_document_task, new_doc.id)
    return new_doc


#2. List Documents Endpoint
@router.get("/", response_model = list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    docs = db.query(Document).filter(Document.owner_id == current_user.id).all()
    return docs

# 3. Get Specific Document Status
@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    if doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    return doc

# 4. Delete Document Endpoint (ChromaDB + Disk cleanup cascade)
@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document, its physical file, and its vector store entries."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    if doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    # A. Physical file clean karo
    if os.path.exists(doc.storage_path):
        try:
            os.remove(doc.storage_path)
        except Exception as e:
            logger.error(f"Error removing physical file {doc.storage_path}: {str(e)}")
    # B. ChromaDB Chunks clean karo
    try:
        vs = VectorStore()
        vs.delete_document_chunks(doc.id)
    except Exception as e:
        logger.error(f"Error removing chunks from ChromaDB for doc ID {doc.id}: {str(e)}")
    # C. Database entry drop karo
    db.delete(doc)
    db.commit()
    
    return status.HTTP_204_NO_CONTENT


# 5. Download/View Document File Endpoint
@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    disposition: str = "inline",
    current_user: User = Depends(get_current_user_optional_query)
):
    """Serve the physical document file for download or in-browser preview."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    if doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
        
    if not os.path.exists(doc.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file not found on server"
        )
        
    # Correct media type/mime type determine karo
    media_type = "application/octet-stream"
    filename_lower = doc.original_filename.lower()
    if filename_lower.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename_lower.endswith(".txt"):
        media_type = "text/plain; charset=utf-8"
    elif filename_lower.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
    headers = {
        "Content-Disposition": f'inline; filename="{doc.original_filename}"'
    }
    if disposition == "attachment":
        headers["Content-Disposition"] = f'attachment; filename="{doc.original_filename}"'
        
    return FileResponse(
        path=doc.storage_path,
        media_type=media_type,
        headers=headers
    )
