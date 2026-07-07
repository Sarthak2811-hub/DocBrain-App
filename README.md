# 🧠 DocBrain — Production-Grade Document RAG System

DocBrain is a high-performance, full-stack **Retrieval-Augmented Generation (RAG)** web application that enables users to securely upload documents (PDF, TXT, DOCX) and have contextual, real-time conversations with them.

Built using **FastAPI**, **ChromaDB**, and **Google Gemini API**, DocBrain is optimized for speed, reliability, cost, and resilience — featuring rate limiting, semantic caching, exponential retry backoffs, and robust error-tolerant document parsing.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+, FastAPI, Uvicorn (ASGI), Pydantic v2, SQLAlchemy |
| **AI & LLM** | Google GenAI SDK — Gemini `gemini-2.5-flash` (chat) & `text-embedding-004` (embeddings) |
| **Database** | SQLite (metadata & chat history), ChromaDB (vector store) |
| **Security** | OAuth2 + JWT Bearer tokens, Bcrypt password hashing |
| **Frontend** | Vanilla HTML5, CSS3 (Flexbox, Animations, Glassmorphism), JavaScript ES6+ (SSE, Marked.js) |
| **Deployment** | Docker, Docker Volumes for persistent storage |

---

## ⚡ Core Engineering Features

### 1. Robust Multi-Format Document Processing
- **Asynchronous Processing** — Documents are parsed, chunked, and embedded in the background using FastAPI's `BackgroundTasks`, keeping the API responsive.
- **Resilient DOCX Fallback Parser** — Custom ZIP + ElementTree XML parser for `.docx` files. If `python-docx` fails due to corrupted media CRC-32 checksums, the pipeline falls back to raw XML parsing of `word/document.xml`.
- **Sliding-Window Chunking** — Splits text into 500-character blocks with 50-character overlaps to preserve context at chunk boundaries.

### 2. Semantic RAG Pipeline
- Computes **768-dimensional vector embeddings** using Google's `text-embedding-004` model and stores them in ChromaDB.
- Retrieves the **top 5 most relevant chunks** via cosine similarity for each user query.
- Streams answers **word-by-word** to the client in real-time using **Server-Sent Events (SSE)**.

### 3. System Optimizations & Cost Control
- **Semantic Response Caching** — In-memory TTL cache keyed on `(user_id, document_id, question)`. Caches both answers and source citations for 5 minutes, eliminating redundant LLM calls.
- **Sliding-Window Rate Limiter** — Per-user request throttling via FastAPI middleware to prevent API abuse.

### 4. API Resilience
- **Exponential Backoff with Jitter** — All Gemini API calls (streaming + embeddings) are wrapped in a retry mechanism with additive random jitter to handle HTTP 429 rate limits and transient failures.

### 5. Interactive Split-Screen UI
- **Responsive Design** — 3 breakpoints (tablet ≤1024px, mobile ≤768px, small ≤480px) with adaptive sidebar collapse and layout restructuring.
- **Glassmorphic Dark Theme** — Frosted glass panels with `backdrop-filter: blur()`, subtle animations, and CSS custom properties design system.
- **Drag & Drop Upload** — File upload via drag-and-drop or click-to-browse with format validation (PDF, TXT, DOCX).
- **Real-time Chat Streaming** — Character-by-character typing animation with adaptive render speed and ChatGPT-style blinking cursor.
- **Document Preview Panel** — Collapsible right panel rendering PDFs/TXT inline via iframe with download fallback for DOCX.
- **Markdown Rendering** — AI responses rendered with Marked.js (bold, lists, code blocks, headings).
- **Message Actions** — Copy, edit & resubmit (user), like/dislike feedback (assistant).
- **Accessibility** — ARIA labels, `role="log"`, `aria-live="polite"`, keyboard focus-visible outlines.

---

## 📁 Project Structure

```
DocBrain/
├── app/
│   ├── api/v1/
│   │   ├── auth.py              # Login, Signup, Profile endpoints
│   │   ├── chat.py              # RAG chat with SSE streaming
│   │   └── documents.py         # Upload, list, delete, download
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── security.py          # JWT creation & verification
│   │   ├── deps.py              # Auth dependency injection
│   │   ├── cache.py             # In-memory TTL semantic cache
│   │   ├── rate_limiter.py      # Sliding-window rate limiter
│   │   └── retry.py             # Exponential backoff + jitter
│   ├── db/
│   │   ├── session.py           # SQLAlchemy engine & session
│   │   └── models/
│   │       ├── user.py          # User model (email, hashed password)
│   │       ├── document.py      # Document model (status, chunks)
│   │       ├── conversation.py  # Conversation model (title, doc link)
│   │       └── message.py       # Message model (role, content, sources)
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── services/
│   │   ├── ai_service.py        # Gemini API wrapper (stream + embed)
│   │   ├── document_processor.py # Parse, chunk, embed pipeline
│   │   ├── rag_pipeline.py      # Query → retrieve → generate
│   │   └── vector_store.py      # ChromaDB CRUD operations
│   ├── static/
│   │   ├── index.html           # Single-page frontend
│   │   ├── style.css            # Design system + responsive
│   │   └── app.js               # SPA logic (auth, chat, SSE)
│   └── main.py                  # FastAPI app setup & middleware
├── main.py                      # Uvicorn entry point
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container image definition
├── .dockerignore                # Build context exclusions
├── .env.example                 # Environment variable template
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))
- Docker (optional, for containerized deployment)

### Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sarthakt28/DocBrain-App.git
   cd DocBrain-App
   ```

2. **Create virtual environment & install dependencies:**
   ```bash
   python -m venv venv

   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Gemini API key:
   ```env
   SECRET_KEY=your-random-secret-key
   GEMINI_API_KEY=your_gemini_api_key_here
   DATABASE_URL=sqlite:///./docbrain.db
   CHROMA_PATH=./chroma_data
   UPLOAD_DIR=./uploads
   ```

4. **Start the server:**
   ```bash
   python main.py
   ```
   Open **http://localhost:8000** in your browser.

---

## 🐳 Docker Deployment

DocBrain is fully containerized with Docker volumes for persistent storage across restarts.

1. **Build the image:**
   ```bash
   docker build -t docbrain-app .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     -p 8000:8000 \
     --name docbrain-container \
     --env-file .env \
     -v docbrain_uploads:/code/uploads \
     -v docbrain_chroma:/code/chroma_data \
     docbrain-app
   ```
   The application will be live at **http://localhost:8000**.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/signup` | Register new user |
| `POST` | `/api/v1/auth/login` | Login (returns JWT) |
| `GET` | `/api/v1/auth/me` | Get current user profile |
| `POST` | `/api/v1/documents/` | Upload document (multipart) |
| `GET` | `/api/v1/documents/` | List user's documents |
| `DELETE` | `/api/v1/documents/{id}` | Delete document |
| `GET` | `/api/v1/documents/{id}/download` | Download/preview document |
| `POST` | `/api/v1/chat/ask` | Ask question (SSE stream) |
| `GET` | `/api/v1/chat/conversations` | List conversations |
| `GET` | `/api/v1/chat/conversations/{id}` | Get conversation messages |
| `DELETE` | `/api/v1/chat/conversations/{id}` | Delete conversation |

> Interactive API docs available at **http://localhost:8000/docs** (Swagger UI)

---

## 🗄️ Database Schema

| Model | Purpose |
|-------|---------|
| **User** | Email, bcrypt-hashed password, created_at |
| **Document** | Filename, storage path, status (`pending` → `processing` → `completed`/`failed`), page & chunk counts |
| **Conversation** | Chat session title, linked to user & document |
| **Message** | Role (`user`/`assistant`), content, source citations (JSON) |

---

## 📄 License

This project is for educational and portfolio purposes.
