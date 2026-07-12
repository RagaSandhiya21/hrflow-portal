"""
AI Policy Chatbot — real RAG pipeline (Module 5).

PDF Upload flow:
  HR Admin uploads PDF -> PyMuPDF extracts text -> LangChain
  RecursiveCharacterTextSplitter chunks it -> Sentence-Transformers
  (all-MiniLM-L6-v2) embeds each chunk -> upserted into ChromaDB. Chunks are
  ALSO mirrored into the `rag_document_chunks` SQL table (chunk text +
  ChromaDB chunk ID) so the app has a durable record even if the ChromaDB
  container is recreated.

Query flow:
  Employee question -> embedded -> ChromaDB similarity search (top-k,
  org-scoped) -> LangChain assembles the retrieved chunks into a grounding
  prompt -> Gemini 2.5 Flash generates the answer -> groundedness is scored
  from retrieval relevance, and low-confidence answers get Retry/Escalate.

If the ChromaDB service isn't reachable (e.g. running the API outside
`docker compose`), this transparently falls back to a SQL keyword-search
retriever (see rag_pipeline.is_available()) so local dev never hard-fails -
but the default docker-compose stack in this repo runs the real pipeline.
"""
import os, re, time, uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import rag_pipeline
from app.config import settings
from app.database import get_db
from app.deps import get_current_employee, require_role
from app.models import (
    Employee, HRPolicyDocument, RagDocumentChunk, ChatbotSession,
    ChatbotQueryLog, EscalationTicket,
)
from app.schemas import ChatQueryCreate, ChatQueryOut, EscalateRequest, EscalationOut
from app.notification_service import notify

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

CONFIDENCE_THRESHOLD = 0.35

CATEGORY_KEYWORDS = {
    "leave_policy":     ["leave","casual","sick","privilege","wfh","work from home","comp off","holiday","carryover","carry over"],
    "compensation":     ["salary","payslip","bonus","pf","provident","tax","tds","reimbursement","ctc","gross","net","deduction"],
    "code_of_conduct":  ["conduct","harassment","dress code","ethics","discipline","behaviour","code"],
    "attendance":       ["attendance","check-in","check in","late","shift","biometric","working hours","punch"],
    "it_assets":        ["laptop","asset","software","vpn","password","access","wifi","hardware","device"],
    "legal_compliance": ["pf act","esi act","compliance","statutory","labour law","posh","maternity","gratuity"],
}


def _guess_category(text: str) -> str:
    lower = text.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in lower for k in kws):
            return cat
    return "general"


def _tokenize(text: str) -> set[str]:
    stop = {"the","a","an","is","are","do","does","i","to","of","for",
            "what","how","can","in","on","my","me","please","tell","about","and","or"}
    return set(re.findall(r"[a-z0-9]+", text.lower())) - stop


def _retrieve_keyword_fallback(db: Session, org_id: int, query_text: str, top_k: int) -> list[dict]:
    """SQL ILIKE keyword-overlap retrieval - only used when the real ChromaDB
    RAG pipeline (rag_pipeline.is_available()) can't be reached."""
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []
    candidates = (
        db.query(RagDocumentChunk, HRPolicyDocument)
        .join(HRPolicyDocument, HRPolicyDocument.document_id == RagDocumentChunk.document_id)
        .filter(HRPolicyDocument.org_id == org_id, HRPolicyDocument.is_active.is_(True))
        .filter(or_(*[RagDocumentChunk.chunk_text.ilike(f"%{t}%") for t in query_tokens]))
        .limit(200)
        .all()
    )
    scored = []
    for chunk, doc in candidates:
        ct = _tokenize(chunk.chunk_text)
        if ct:
            scored.append({
                "chunk_text": chunk.chunk_text,
                "document_name": doc.document_name,
                "document_id": doc.document_id,
                "chromadb_chunk_id": chunk.chromadb_chunk_id,
                "score": len(query_tokens & ct) / len(query_tokens),
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _retrieve(db: Session, org_id: int, query_text: str, top_k: int = 3) -> list[dict]:
    """
    Retrieves the top-k most relevant policy chunks for `query_text`.
    Prefers the real ChromaDB semantic-search pipeline (embeddings via
    Sentence-Transformers, scored by cosine similarity); falls back to SQL
    keyword overlap only if ChromaDB/the embedding model aren't reachable.
    """
    if rag_pipeline.is_available():
        try:
            return rag_pipeline.retrieve(org_id, query_text, top_k=top_k)
        except Exception as e:
            print(f"[rag] ChromaDB retrieval failed, falling back to keyword search: {e}")
    return _retrieve_keyword_fallback(db, org_id, query_text, top_k)


def _generate_answer(query_text: str, retrieved: list[dict]) -> tuple[str, float, str | None]:
    if not retrieved:
        return (
            "I couldn't find relevant information in the indexed policy documents. "
            "Try rephrasing your question, or escalate to HR for a direct answer.",
            0.0, None,
        )
    top_score  = retrieved[0]["score"]
    gemini_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")

    if gemini_key:
        try:
            if rag_pipeline.is_available():
                # Real LangChain-orchestrated Gemini call over the semantically
                # retrieved chunks (see rag_pipeline.generate_grounded_answer).
                answer, model_name = rag_pipeline.generate_grounded_answer(query_text, retrieved, gemini_key)
                return answer, min(0.95, top_score + 0.25), model_name

            # ChromaDB unavailable but Gemini key present: still generate a
            # grounded answer over the keyword-retrieved chunks directly.
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            context = "\n\n".join(f"[Source: {r['document_name']}]\n{r['chunk_text']}" for r in retrieved)
            prompt = (
                "You are an HR policy assistant for a company. "
                "Answer the employee's question using ONLY the context provided below. "
                "Be concise, friendly, and accurate. "
                "If the context doesn't contain the answer, say you're not sure and suggest escalating to HR.\n\n"
                f"Context:\n{context}\n\n"
                f"Employee question: {query_text}\n\n"
                "Answer:"
            )
            model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)
            resp  = model.generate_content(prompt)
            return resp.text.strip(), min(0.95, top_score + 0.25), settings.GEMINI_MODEL_NAME
        except Exception as e:
            print(f"[gemini] error: {e}")

    # Keyword-search extractive fallback (no LLM key configured)
    snippet = retrieved[0]["chunk_text"].strip()
    if len(snippet) > 700:
        snippet = snippet[:700] + "…"
    model_label = "chromadb-semantic-search" if rag_pipeline.is_available() else "keyword-search"
    answer = f"Based on **{retrieved[0]['document_name']}**:\n\n{snippet}"
    return answer, top_score, model_label


def _esc_out(ticket: EscalationTicket, db: Session) -> EscalationOut:
    out = EscalationOut.model_validate(ticket)
    emp = db.query(Employee).filter(Employee.employee_id == ticket.employee_id).first()
    out.employee_name = emp.full_name if emp else None
    return out


# ── Policy documents ──────────────────────────────────────────────────────────

@router.get("/policy-docs")
def list_policy_docs(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    docs = (
        db.query(HRPolicyDocument)
        .filter(HRPolicyDocument.org_id == current.org_id, HRPolicyDocument.is_active.is_(True))
        .all()
    )
    return [
        {
            "document_id":         d.document_id,
            "document_name":       d.document_name,
            "document_type":       d.document_type,
            "indexed_in_chromadb": d.indexed_in_chromadb,
        }
        for d in docs
    ]


def _extract_text_from_file(content: bytes, filename: str) -> str:
    """
    Extract plain text from uploaded file.
    Supports PDF (via PyMuPDF/fitz) and plain text files.
    PyMuPDF is the Module 5 requirement — installs via: pip install pymupdf
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        try:
            import fitz  # PyMuPDF
            doc  = fitz.open(stream=content, filetype="pdf")
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            # PyMuPDF not installed — fall back to treating as text
            print("[chatbot] PyMuPDF not installed. Install with: pip install pymupdf")
            return content.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[chatbot] PDF extraction error: {e}")
            return content.decode("utf-8", errors="ignore")
    else:
        return content.decode("utf-8", errors="ignore")


@router.post("/policy-docs/upload")
async def upload_policy_doc(
    document_name: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    """
    Upload HR policy document (PDF or TXT).
    PyMuPDF extracts text from PDFs; content is chunked into paragraphs
    and stored in rag_document_chunks for chatbot retrieval.
    """
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    text = _extract_text_from_file(content, file.filename)

    upload_dir = "policy_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)
    file_path = f"{upload_dir}/{safe_name}"
    with open(file_path, "wb") as f:
        f.write(content)

    doc = HRPolicyDocument(
        org_id             = current.org_id,
        document_name      = document_name,
        document_type      = document_type,
        file_path          = file_path,
        is_active          = True,
        indexed_in_chromadb= False,
    )
    db.add(doc); db.flush()

    use_real_rag = rag_pipeline.is_available()
    if use_real_rag:
        # LangChain's RecursiveCharacterTextSplitter: paragraph/sentence-aware,
        # with overlap so facts split across a boundary stay retrievable.
        chunks = rag_pipeline.chunk_text(text)
    else:
        # Fallback chunking (paragraphs, min 50 chars; max 50 chunks) used only
        # when ChromaDB isn't reachable - see rag_pipeline.is_available().
        chunks = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) >= 50]
        if not chunks:
            chunks = [text[i:i+500].strip() for i in range(0, len(text), 500) if text[i:i+500].strip()]
        chunks = chunks[:50]

    if not chunks:
        raise HTTPException(status_code=400, detail="No extractable text content found in this file.")

    chromadb_ids = None
    if use_real_rag:
        try:
            chromadb_ids = rag_pipeline.index_document(doc.document_id, current.org_id, document_name, chunks)
        except Exception as e:
            print(f"[rag] ChromaDB indexing failed, storing chunks SQL-only: {e}")
            chromadb_ids = None

    chunks_added = 0
    for idx, chunk in enumerate(chunks):
        cid = chromadb_ids[idx] if chromadb_ids else f"upload-{doc.document_id}-{idx}-{uuid.uuid4().hex[:8]}"
        db.add(RagDocumentChunk(
            document_id      = doc.document_id,
            chunk_index      = idx,
            chunk_text       = chunk,
            token_count      = len(chunk.split()),
            chromadb_chunk_id= cid,
        ))
        chunks_added += 1

    doc.indexed_in_chromadb = bool(chromadb_ids)
    db.commit()
    return {
        "document_id":   doc.document_id,
        "document_name": document_name,
        "chunks_indexed": chunks_added,
        "indexed_in_chromadb": doc.indexed_in_chromadb,
        "file_type":     file.filename.rsplit(".", 1)[-1].upper() if "." in file.filename else "TXT",
        "message":       (
            f"Successfully embedded and indexed {chunks_added} chunks from {file.filename} in ChromaDB"
            if doc.indexed_in_chromadb else
            f"Stored {chunks_added} chunks in Postgres (ChromaDB unreachable - keyword search will be used "
            f"for this document until it's re-indexed)"
        ),
    }


@router.delete("/policy-docs/{document_id}")
def delete_policy_doc(
    document_id: int,
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    doc = db.query(HRPolicyDocument).filter(
        HRPolicyDocument.document_id == document_id,
        HRPolicyDocument.org_id      == current.org_id,
    ).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_active = False   # soft delete — preserve chunks for audit
    if doc.indexed_in_chromadb and rag_pipeline.is_available():
        try:
            rag_pipeline.delete_document(doc.document_id)
        except Exception as e:
            print(f"[rag] ChromaDB delete failed (SQL soft-delete still applied): {e}")
    db.commit()
    return {"message": f"'{doc.document_name}' removed from chatbot search"}


# ── Chat query ────────────────────────────────────────────────────────────────

@router.post("/query", response_model=ChatQueryOut)
def ask(
    body: ChatQueryCreate,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    start   = time.time()
    session = None
    if body.session_id:
        session = db.query(ChatbotSession).filter(
            ChatbotSession.session_id  == body.session_id,
            ChatbotSession.employee_id == current.employee_id,
        ).first()
    if session is None:
        session = ChatbotSession(
            employee_id=current.employee_id,
            started_at=datetime.utcnow(),
            total_messages=0,
        )
        db.add(session); db.commit(); db.refresh(session)

    retrieved               = _retrieve(db, current.org_id, body.query_text)
    answer, confidence, mdl = _generate_answer(body.query_text, retrieved)
    is_grounded             = confidence >= CONFIDENCE_THRESHOLD
    category                = _guess_category(body.query_text)

    log = ChatbotQueryLog(
        session_id        = session.session_id,
        employee_id       = current.employee_id,
        query_text        = body.query_text,
        query_category    = category,
        retrieved_chunk_ids= [r["chromadb_chunk_id"] for r in retrieved if r.get("chromadb_chunk_id")],
        source_documents  = list({r["document_name"] for r in retrieved if r.get("document_name")}),
        llm_model_used    = mdl,
        llm_response      = answer,
        confidence_score  = round(confidence, 3),
        is_grounded       = is_grounded,
        is_escalated      = False,
        asked_at          = datetime.utcnow(),
        response_latency_ms = int((time.time() - start) * 1000),
    )
    db.add(log)
    session.total_messages = (session.total_messages or 0) + 1
    db.commit(); db.refresh(log)

    return ChatQueryOut(
        session_id     = session.session_id,
        query_id       = log.query_id,
        answer         = answer,
        confidence_score = float(log.confidence_score),
        is_grounded    = is_grounded,
        query_category = category,
        source_documents = log.source_documents or [],
    )


# ── Escalations ───────────────────────────────────────────────────────────────

@router.post("/escalate", response_model=EscalationOut, status_code=201)
def escalate(
    body: EscalateRequest,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    log = db.query(ChatbotQueryLog).filter(ChatbotQueryLog.query_id == body.query_id).first()
    if log is None or log.employee_id != current.employee_id:
        raise HTTPException(status_code=404, detail="Query not found")

    ticket = EscalationTicket(
        query_id          = log.query_id,
        employee_id       = current.employee_id,
        escalated_query   = log.query_text,
        escalation_reason = body.reason,
        status            = "open",
        escalated_at      = datetime.utcnow(),
    )
    db.add(ticket)
    log.is_escalated = True
    db.commit(); db.refresh(ticket)
    return _esc_out(ticket, db)


@router.get("/escalations/mine", response_model=list[EscalationOut])
def my_escalations(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_employee),
):
    tickets = (
        db.query(EscalationTicket)
        .filter(EscalationTicket.employee_id == current.employee_id)
        .order_by(EscalationTicket.escalated_at.desc())
        .all()
    )
    return [_esc_out(t, db) for t in tickets]


@router.get("/escalations/queue", response_model=list[EscalationOut])
def escalation_queue(
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    tickets = (
        db.query(EscalationTicket)
        .filter(EscalationTicket.status != "resolved")
        .order_by(EscalationTicket.escalated_at.asc())
        .all()
    )
    return [_esc_out(t, db) for t in tickets]


@router.post("/escalations/{escalation_id}/respond", response_model=EscalationOut)
def respond_to_escalation(
    escalation_id: int,
    response_text: str = Form(...),
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    ticket = db.query(EscalationTicket).filter(
        EscalationTicket.escalation_id == escalation_id
    ).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Escalation not found")

    ticket.status           = "resolved"
    ticket.resolved_at      = datetime.utcnow()
    ticket.resolution_notes = response_text
    ticket.assigned_to      = current.employee_id
    notify(db, ticket.employee_id, "escalation_resolved",
           "HR answered your escalated question",
           response_text[:200],
           deep_link="/chatbot")
    db.commit(); db.refresh(ticket)
    return _esc_out(ticket, db)


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationOut)
def resolve_escalation(
    escalation_id: int,
    notes: str = "",
    db: Session = Depends(get_db),
    current: Employee = Depends(require_role("hr_admin")),
):
    ticket = db.query(EscalationTicket).filter(
        EscalationTicket.escalation_id == escalation_id
    ).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    ticket.status           = "resolved"
    ticket.resolved_at      = datetime.utcnow()
    ticket.resolution_notes = notes
    ticket.assigned_to      = current.employee_id
    db.commit(); db.refresh(ticket)
    return _esc_out(ticket, db)
