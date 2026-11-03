# DocuMind – AI-Powered PDF Question Answering

DocuMind is a full-stack AI-powered PDF question-answering application that allows users to upload PDF documents and ask questions about their contents.

It combines semantic search, keyword-based retrieval and Large Language Model (LLM) response generation to provide context-aware answers with page-level source citations.

## Features

- Upload and manage text-based PDF documents (up to 25 MB).
- Extract PDF text using PyMuPDF.
- Split extracted text into overlapping chunks.
- Store documents, extracted chunks and conversation history in PostgreSQL.
- **Semantic retrieval:** Sentence Transformers (`all-MiniLM-L6-v2`) and FAISS.
- **Keyword retrieval:** BM25.
- **Hybrid retrieval:** Reciprocal Rank Fusion (RRF) combines semantic and keyword search results.
- **AI-generated answers:** Groq API generates answers grounded in retrieved document excerpts.
- Page-level source references for answers.
- Clickable citations that navigate to the relevant source excerpts.
- Persistent conversation history.
- Document deletion and retrieval-index rebuilding from PostgreSQL on backend startup.
- Markdown-formatted AI responses.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL, SQLAlchemy |
| PDF processing | PyMuPDF |
| Embeddings | Sentence Transformers |
| Vector search | FAISS |
| Keyword search | BM25 |
| Ranking fusion | Reciprocal Rank Fusion |
| LLM | Groq API |
| Response rendering | React Markdown |

## Project Architecture

1. **Document ingestion:** Users upload PDFs through the React frontend.
2. **Text extraction:** FastAPI processes the uploaded documents using PyMuPDF.
3. **Chunking:** Extracted text is divided into overlapping chunks.
4. **Storage:** Documents and chunks are stored in PostgreSQL.
5. **Embedding generation:** Sentence Transformers converts chunks into vector embeddings.
6. **Indexing:** FAISS indexes semantic vectors, while BM25 indexes document text.
7. **Hybrid retrieval:** Semantic and keyword search results are combined using Reciprocal Rank Fusion.
8. **Answer generation:** Retrieved excerpts are passed to Groq to generate context-aware answers.
9. **Source attribution:** Responses include page-level citations linked to the corresponding PDF excerpts.

## Project Structure

```text
DocuMind/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── uploads/
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       └── style.css
│
├── README.md
└── .gitignore
```

## Installation and Setup

### Prerequisites

Install the following:

- Python 3.10 or 3.11 (64-bit)
- Node.js LTS and npm
- PostgreSQL 15 or newer
- Git

Check the installed versions:

```powershell
py --version
node --version
npm --version
psql --version
```

### 1. Create the PostgreSQL database

Open pgAdmin:

1. Connect to your local PostgreSQL server.
2. Right-click **Databases**.
3. Select **Create → Database**.
4. Enter `documind` as the database name.
5. Save.

Alternatively, execute:

```sql
CREATE DATABASE documind;
```

The application automatically creates its database tables when the backend starts.

### 2. Configure the backend

Open a terminal in the project root:

```powershell
cd backend

py -3.11 -m venv .venv

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

pip install -r requirements.txt

Copy-Item .env.example .env
```

Open `backend/.env` and configure:

```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/documind

GROQ_API_KEY=YOUR_GROQ_API_KEY
```

Replace the PostgreSQL password and Groq API key with your own credentials.

### 3. Obtain a Groq API key

1. Visit [Groq Console](https://console.groq.com/).
2. Sign in or create an account.
3. Navigate to API Keys.
4. Generate an API key.
5. Add it to `backend/.env` as `GROQ_API_KEY`.

Keep your API key private. Never commit your `.env` file to GitHub.

The Groq model is configured in the backend.

### 4. Start the backend

Ensure PostgreSQL is running.

From the `backend` directory, execute:

```powershell
uvicorn main:app --reload
```

Backend API:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

On first startup, Sentence Transformers downloads the `all-MiniLM-L6-v2` embedding model. This may take a few minutes.

### 5. Start the frontend

Open a second terminal at the project root:

```powershell
cd frontend

npm install

npm run dev
```

Open the local URL displayed by Vite, normally:

`http://localhost:5173`

## Testing the Application

1. Open DocuMind in your browser.
2. Upload a text-based PDF document.
3. Select the uploaded document.
4. Ask a question related to its contents.
5. Review the generated answer.
6. Check the page-level source citations.
7. Click a citation to navigate to its corresponding source excerpt.
8. Refresh the browser and verify that conversation history persists.
9. Restart the backend and verify that documents and chunks remain available through PostgreSQL.

## Environment Variables

The backend requires the following environment variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `GROQ_API_KEY` | API key for Groq-based answer generation |

Refer to `backend/.env.example` for the configuration template.

## Current Limitations

- OCR for scanned PDFs is not implemented. The application currently processes PDFs containing selectable text.
- User authentication and multi-user access control are not implemented.
- Uploaded PDFs are stored in the backend's local uploads directory.
- FAISS and BM25 retrieval indexes are rebuilt in memory from stored PostgreSQL chunks when the backend starts.
- The application is currently configured as a locally running portfolio MVP and requires additional infrastructure and security work before production deployment.

## Future Improvements

- Cloud-based PDF storage.
- User authentication and access control.
- OCR support for scanned documents.
- Production deployment with persistent storage.
- Automated testing and improved error handling.
- Retrieval and response performance optimisation.

---

