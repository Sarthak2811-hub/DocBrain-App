# DocBrain - Production-Grade Document RAG System

DocBrain is a high-performance, full-stack Retrieval-Augmented Generation (RAG) web application that enables users to securely upload documents (PDF, TXT, DOCX) and have contextual, real-time conversations with them. 

Built using **FastAPI**, **ChromaDB**, and **Google Gemini API**, DocBrain is optimized for speed, reliability, cost, and resilience, featuring rate limiting, semantic caching, exponential retry backoffs, and robust error-tolerant document parsing.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, FastAPI (Uvicorn), Pydantic, SQLAlchemy
- **AI & LLM**: Google GenAI SDK (Gemini `gemini-2.5-flash` & `text-embedding-004`), Prompt Engineering
- **Database & Vector Store**: SQLite (Metadata & Chat history), ChromaDB (Vector database)
- **Security**: OAuth2 with JWT tokens, Bcrypt password encryption
- **Deployment**: Docker, Docker Volumes for Persistent Storage
- **Frontend**: Vanilla HTML5, CSS3 (Flexbox/Grid, Animations), JavaScript (ES6+, SSE Event Reader)

---

## ⚡ Core Engineering Features

### 1. **Robust Multi-Format Processing (PDF, TXT, DOCX)**
- **Asynchronous Processing**: Uploaded documents are parsed, chunked, and embedded asynchronously using FastAPI’s `BackgroundTasks`, keeping the main thread free.
- **Resilient Parsing Fallback**: Includes a custom ZIP + ElementTree XML parser for `.docx` files. If `python-docx` fails due to corrupted images or bad media CRC-32 checksums, the pipeline automatically falls back to raw XML parsing of `word/document.xml`, extracting the text without interrupting operations.
- **Sliding-Window Chunking**: Splits text into 500-character blocks with 50-character overlaps to preserve contextual continuity at chunk boundaries.

### 2. **Efficient Semantic RAG Pipeline**
- Computes 768-dimensional vector embeddings of text chunks and stores them in ChromaDB.
- Searches and retrieves the top 5 most relevant context passages based on cosine similarity for any user query.
- Streams answers word-by-word to the client in real-time using Server-Sent Events (SSE).

### 3. **System Optimizations & Cost Control**
- **Semantic Response Caching**: Implements an in-memory TTL (Time-To-Live) cache matching `(user_id, document_id, question)`. It caches both text answers and their matching sources (citations) for 5 minutes, eliminating redundant LLM calls and reducing API costs.
- **Token-Bucket Rate Limiter**: Restricts API abuse with a per-user, sliding-window request logger configured inside a FastAPI middleware layer.

### 4. **API Resilience (Backoff & Jitter)**
- To handle third-party API rate limits (HTTP 429 warnings) or transient network hiccups, all Gemini API calls (text stream and embeddings) are wrapped in an **exponential backoff retry algorithm with random jitter**.

### 5. **Interactive Split-Screen UI**
- A responsive, glassmorphic layout featuring drag-and-drop file upload, dynamic format-specific icons, a live chat stream panel, and an inline collapsible **Document Preview Panel** displaying PDF and TXT contents inside the browser seamlessly.

---

## 🚀 Getting Started

### 📋 Prerequisites
- Python 3.11+ installed locally.
- A Google Gemini API Key (get one from [Google AI Studio](https://aistudio.google.com/)).
- Docker (optional, for containerized running).

### 💻 Local Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd Crypto_Alert
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Create a `.env` file in the root directory and add the following settings:
   ```env
   SECRET_KEY=docbrain-super-secret-key-change-in-production
   GEMINI_API_KEY=your_gemini_api_key_here
   DATABASE_URL=sqlite:///./docbrain.db
   CHROMA_PATH=./chroma_data
   UPLOAD_DIR=./uploads
   ```

4. **Start the application:**
   ```bash
   python main.py
   ```
   Open your browser and navigate to `http://localhost:8000`.

---

## 🐳 Docker Deployment

DocBrain is fully containerized and uses Docker volumes to preserve uploaded documents and vector data across container restarts.

1. **Build the Docker Image:**
   ```bash
   docker build -t docbrain-app .
   ```

2. **Run the Docker Container:**
   ```bash
   docker run -d \
     -p 8000:8000 \
     --name docbrain-container \
     --env-file .env \
     -v docbrain_uploads:/code/uploads \
     -v docbrain_chroma:/code/chroma_data \
     docbrain-app
   ```
   The application will be live at `http://localhost:8000`.

---

## 🗄️ Database Models Schema

The application structures relational data across four primary SQLAlchemy models:
- **`User`**: Manages credentials (hashed via bcrypt) and ownership constraints.
- **`Document`**: Tracks original file names, storage paths, processing status (`pending`, `processing`, `completed`, `failed`), and page/chunk counts.
- **`Conversation`**: Grouping entity representing chat sessions.
- **`Message`**: Persists roles (`user` or `assistant`), content text, and source page citation JSON lists.
