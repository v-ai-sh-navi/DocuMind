import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import fitz
import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, ForeignKey, Integer,
    select, desc
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from groq import Groq

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Set it in backend/.env")

# SQLAlchemy expects postgresql+psycopg2:// for psycopg2.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    page_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    document = relationship("Document", back_populates="chunks")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True)
    title = Column(String, default="New conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    sources_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DocuMind", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedder = SentenceTransformer("all-MiniLM-L6-v2")
groq_key = os.getenv("GROQ_API_KEY", "")
groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
groq_client = Groq(api_key=groq_key) if groq_key else None

# In-memory retrieval indexes are rebuilt from PostgreSQL at startup.
chunk_records = []
faiss_index = None
bm25_index = None

def split_into_chunks(text: str, max_words: int = 180, overlap: int = 35):
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks

def rebuild_indexes():
    global chunk_records, faiss_index, bm25_index
    db = SessionLocal()
    try:
        rows = db.execute(
            select(DocumentChunk.id, DocumentChunk.document_id,
                   DocumentChunk.page_number, DocumentChunk.content)
        ).all()
        chunk_records = [
            {"id": r.id, "document_id": r.document_id,
             "page": r.page_number, "text": r.content}
            for r in rows
        ]
    finally:
        db.close()

    if not chunk_records:
        faiss_index, bm25_index = None, None
        return

    vectors = embedder.encode(
        [x["text"] for x in chunk_records],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    ).astype("float32")
    faiss_index = faiss.IndexFlatIP(vectors.shape[1])
    faiss_index.add(vectors)
    tokenized = [x["text"].lower().split() for x in chunk_records]
    bm25_index = BM25Okapi(tokenized)

rebuild_indexes()

class AskRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    document_ids: Optional[List[str]] = None

def serialize_conversation(c):
    return {"id": c.id, "title": c.title, "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()}

@app.get("/")
def health():
    return {"status": "ok", "app": "DocuMind AI", "database": "PostgreSQL"}

@app.get("/api/documents")
def list_documents():
    db = SessionLocal()
    try:
        docs = db.scalars(select(Document).order_by(desc(Document.created_at))).all()
        return [{"id": d.id, "filename": d.filename, "page_count": d.page_count,
                 "created_at": d.created_at.isoformat()} for d in docs]
    finally:
        db.close()

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "PDF must be smaller than 25 MB.")

    doc_id = str(uuid.uuid4())
    safe_name = Path(file.filename).name
    stored_path = UPLOAD_DIR / f"{doc_id}.pdf"
    stored_path.write_bytes(content)

    try:
        pdf = fitz.open(stream=content, filetype="pdf")
        page_count = len(pdf)
        pending = []
        for page_idx, page in enumerate(pdf):
            page_text = page.get_text("text")
            for chunk_idx, chunk in enumerate(split_into_chunks(page_text)):
                pending.append(DocumentChunk(
                    id=str(uuid.uuid4()), document_id=doc_id,
                    page_number=page_idx + 1, chunk_index=chunk_idx, content=chunk
                ))
        pdf.close()
        if not pending:
            raise HTTPException(422, "No selectable text found. This may be a scanned PDF; OCR is not included in this MVP.")

        db = SessionLocal()
        try:
            doc = Document(id=doc_id, filename=safe_name,
                           stored_path=str(stored_path), page_count=page_count)
            db.add(doc)
            db.add_all(pending)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        rebuild_indexes()
        return {"id": doc_id, "filename": safe_name, "page_count": page_count,
                "chunks_created": len(pending)}
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Could not process PDF: {exc}")

@app.get("/api/conversations")
def list_conversations():
    db = SessionLocal()
    try:
        rows = db.scalars(select(Conversation).order_by(desc(Conversation.updated_at))).all()
        return [serialize_conversation(c) for c in rows]
    finally:
        db.close()

@app.post("/api/conversations")
def create_conversation():
    db = SessionLocal()
    try:
        c = Conversation(id=str(uuid.uuid4()), title="New conversation")
        db.add(c)
        db.commit()
        db.refresh(c)
        return serialize_conversation(c)
    finally:
        db.close()

@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str):
    db = SessionLocal()
    try:
        c = db.get(Conversation, conversation_id)
        if not c:
            raise HTTPException(404, "Conversation not found.")
        rows = db.scalars(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        ).all()
        return [{
            "id": m.id, "role": m.role, "content": m.content,
            "sources": json.loads(m.sources_json or "[]"),
            "created_at": m.created_at.isoformat()
        } for m in rows]
    finally:
        db.close()

@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    db = SessionLocal()
    try:
        c = db.get(Conversation, conversation_id)
        if not c:
            raise HTTPException(404, "Conversation not found.")
        db.delete(c)
        db.commit()
        return {"deleted": True}
    finally:
        db.close()

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if not document:
            raise HTTPException(404, "Document not found")
        stored_path = Path(document.stored_path)
        db.delete(document)
        db.commit()
        if stored_path.exists():
            stored_path.unlink()
        rebuild_indexes()
        return {"deleted": True}
    finally:
        db.close()

def retrieve(question: str, document_ids: Optional[List[str]], top_k: int = 6):
    if not chunk_records or faiss_index is None:
        return []
    eligible = [i for i, item in enumerate(chunk_records)
                if not document_ids or item["document_id"] in document_ids]
    if not eligible:
        return []

    # Semantic similarity scores from the FAISS index.
    q_vec = embedder.encode([question], convert_to_numpy=True,
                            normalize_embeddings=True).astype("float32")
    scores, indices = faiss_index.search(q_vec, len(chunk_records))
    semantic_rank = {}
    rank = 1
    for idx in indices[0]:
        idx = int(idx)
        if idx in eligible:
            semantic_rank[idx] = rank
            rank += 1
            if rank > top_k * 5:
                break

    # BM25 ranks only chunks belonging to selected documents.
    corpus = [chunk_records[i]["text"].lower().split() for i in eligible]
    bm25 = BM25Okapi(corpus)
    lexical_scores = bm25.get_scores(question.lower().split())
    lexical_order = np.argsort(lexical_scores)[::-1][:top_k * 5]
    lexical_rank = {eligible[int(pos)]: rank + 1
                    for rank, pos in enumerate(lexical_order)}

    # Reciprocal Rank Fusion combines both rankings.
    fused = {}
    for idx in set(semantic_rank) | set(lexical_rank):
        fused[idx] = (1 / (60 + semantic_rank.get(idx, 10_000)) +
                      1 / (60 + lexical_rank.get(idx, 10_000)))
    best = sorted(fused, key=fused.get, reverse=True)[:top_k]
    return [chunk_records[i] for i in best]

@app.post("/api/ask")
def ask_question(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty.")
    if not groq_client:
        raise HTTPException(503, "Groq API key is missing. Add GROQ_API_KEY to backend/.env.")

    db = SessionLocal()
    try:
        conversation = db.get(Conversation, payload.conversation_id) if payload.conversation_id else None
        if payload.conversation_id and not conversation:
            raise HTTPException(404, "Conversation not found.")
        if not conversation:
            conversation = Conversation(id=str(uuid.uuid4()), title=question[:55])
            db.add(conversation)
            db.flush()
        elif conversation.title == "New conversation":
            conversation.title = question[:55]

        user_msg = Message(id=str(uuid.uuid4()), conversation_id=conversation.id,
                           role="user", content=question)
        db.add(user_msg)
        db.flush()

        matches = retrieve(question, payload.document_ids)
        if not matches:
            answer = "I couldn't find relevant text in the selected PDFs. Upload a text-based PDF or select a document and try again."
            sources = []
        else:
            context = "\n\n".join(
                f"[Source {i+1} | Document: {m['document_id']} | Page: {m['page']}]\n{m['text']}"
                for i, m in enumerate(matches)
            )
            prompt = f"""You are DocuMind AI, a careful PDF research assistant.
Answer the user's question using ONLY the supplied PDF excerpts.
If the excerpts do not contain the answer, say that the documents do not provide enough information.
Do not invent facts. Be clear and concise. Cite claims using [Source 1], [Source 2], etc.

PDF EXCERPTS:
{context}

USER QUESTION:
{question}
"""
            try:
                response = groq_client.chat.completions.create(
                    model=groq_model,
                    messages=[
                        {"role":"user","content":prompt}
                    ]
                )
                answer = response.choices[0].message.content or "The AI model returned an empty response."
            except Exception as exc:
                raise HTTPException(502, f"Groq request failed: {exc}")
            sources = [{
                "document_id": m["document_id"], "page": m["page"],
                "text": m["text"][:350]
            } for m in matches]

        assistant_msg = Message(
            id=str(uuid.uuid4()), conversation_id=conversation.id,
            role="assistant", content=answer, sources_json=json.dumps(sources)
        )
        db.add(assistant_msg)
        conversation.updated_at = datetime.utcnow()
        db.commit()
        return {"conversation_id": conversation.id, "answer": answer, "sources": sources}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

@app.get("/api/stats")
def stats():
    db = SessionLocal()
    try:
        return {
            "documents": db.scalar(select(Document).count()) if False else len(db.scalars(select(Document.id)).all()),
            "chunks": len(db.scalars(select(DocumentChunk.id)).all()),
            "conversations": len(db.scalars(select(Conversation.id)).all())
        }
    finally:
        db.close()
