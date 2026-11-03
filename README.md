# DocuMind AI — PostgreSQL Edition

An AI-powered PDF question-answering application built with React + Vite, FastAPI, PostgreSQL, hybrid retrieval (BM25 + FAISS), and Gemini.

## Features

- Upload text-based PDFs (up to 25 MB)
- Extract text, split it into overlapping chunks, and store documents/chunks in PostgreSQL
- Hybrid retrieval: semantic search (Sentence Transformers + FAISS) and keyword search (BM25), fused with Reciprocal Rank Fusion
- Gemini-generated answers grounded in retrieved PDF excerpts
- Page-level source references
- Conversation history persisted in PostgreSQL
- Retrieval indexes rebuilt from PostgreSQL when the backend starts

## 1. Install prerequisites

Install:
- Python 3.10 or 3.11
- Node.js LTS (includes npm)
- PostgreSQL 15 or newer
- Git (optional)

Check versions in PowerShell:
```powershell
py --version
node --version
npm --version
psql --version
```

## 2. Create the PostgreSQL database

Open pgAdmin:
1. Connect to your local PostgreSQL server.
2. Right-click **Databases** → **Create** → **Database**.
3. Name it `documind`.
4. Save.

Or open SQL Shell (psql) and run:
```sql
CREATE DATABASE documind;
```

The app creates its tables automatically on first backend startup. You do not need to manually create tables.

## 3. Extract the ZIP

1. Download `DocuMind-AI-PostgreSQL.zip`.
2. In Windows File Explorer, right-click it → **Extract All…**
3. Choose a convenient location, e.g. `C:\Projects\`.
4. You should see the `DocuMind-AI-PostgreSQL` folder.
5. Open that folder in VS Code: **File → Open Folder**.

Do not run the project while it is still inside the ZIP preview.

## 4. Configure the backend

Open VS Code terminal (PowerShell):
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `backend/.env` and edit:
```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/documind
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
```
Replace `YOUR_POSTGRES_PASSWORD` with the password you created for the PostgreSQL `postgres` user. Do not add angle brackets or quotes. If your PostgreSQL username is not `postgres`, replace that too.

### Get a Gemini API key
1. Open https://aistudio.google.com/
2. Sign in with your Google account.
3. Open **Get API key** / **API keys**.
4. Create an API key in a Google Cloud project.
5. Copy it into `GEMINI_API_KEY` in `backend/.env`.

Keep the key private. Never commit `.env` to GitHub. Gemini availability and free quotas depend on model, region, and account.

## 5. Start the backend

Make sure PostgreSQL is running. In the backend terminal:
```powershell
uvicorn main:app --reload
```
Expected:
- API: http://127.0.0.1:8000
- Interactive API docs: http://127.0.0.1:8000/docs

On first run, Sentence Transformers downloads `all-MiniLM-L6-v2`; this can take a few minutes. PostgreSQL tables are created automatically.

## 6. Start the React frontend

Open a **second** VS Code terminal at the project root:
```powershell
cd frontend
npm install
npm run dev
```
Open the URL printed by Vite, normally http://localhost:5173.

## 7. Test the app

1. Upload a text-based PDF.
2. Select its checkbox in the left sidebar.
3. Ask a question whose answer is present in the PDF.
4. Check the page number and source excerpt under the answer.
5. Refresh the browser. Conversation history should remain.
6. Stop and restart the backend. Documents and chunks remain in PostgreSQL; retrieval indexes rebuild from stored chunks.

## Folder structure

```text
DocuMind-AI-PostgreSQL/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── uploads/              # created automatically; PDFs saved here
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       └── style.css
├── README.md
└── .gitignore
```

## Troubleshooting

**`password authentication failed for user postgres`**
- Recheck the password in `backend/.env`.
- Try connecting in pgAdmin with the same username/password.
- Make sure PostgreSQL service is running.

**`database "documind" does not exist`**
- Create it using pgAdmin or `CREATE DATABASE documind;`.

**`GEMINI_API_KEY is missing`**
- Check that the file is named exactly `.env`, is inside `backend/`, and contains the key.

**Gemini model error**
- Check which model is enabled for your account in Google AI Studio and update `GEMINI_MODEL`.

**`No selectable text found`**
- This MVP extracts embedded/selectable PDF text. Scanned PDFs need OCR, which is not included.

**PowerShell blocks activation**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**FAISS / sentence-transformers installation issue**
- Use Python 3.10 or 3.11 in a 64-bit environment, then recreate the virtual environment.

## Important MVP limitations

- No user authentication or multi-user access control.
- Scanned PDF OCR is not implemented.
- Uploaded PDF files and extracted chunks persist on the backend machine; this is a local demo, not a production deployment.
- Embeddings and FAISS/BM25 indexes are rebuilt in memory from PostgreSQL at backend startup.
- The Gemini API is called for answer generation; embeddings and retrieval run locally.
- The app is a portfolio MVP. Add authentication, migrations, rate limiting, tests, cloud deployment, and stronger file validation before production use.
