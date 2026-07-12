"""
Real RAG pipeline for the HR Policy Chatbot (Module 5).

Stack, exactly as specified in the proposal:
  PyMuPDF (text extraction) -> LangChain RecursiveCharacterTextSplitter
  (chunking) -> Sentence-Transformers all-MiniLM-L6-v2 (embeddings) ->
  ChromaDB (vector store, via the `chromadb` container in docker-compose.yml)
  -> LangChain retriever -> Gemini 2.5 Flash (grounded answer generation).

This module is the single place that talks to Chroma/LangChain/the
embedding model, so routers/chatbot.py stays thin. If the optional heavy
dependencies (chromadb / sentence-transformers / langchain) aren't
installed, or the ChromaDB service isn't reachable, `is_available()`
returns False and the caller (routers/chatbot.py) transparently falls back
to a SQL keyword-search retriever instead of crashing the request - useful
for a lightweight local dev loop, but the default `docker compose up` stack
has everything needed for the real pipeline to run.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)

_import_error: str | None = None
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
except Exception as e:  # pragma: no cover - exercised only when deps are missing
    _import_error = str(e)


@lru_cache(maxsize=1)
def _embeddings():
    """Sentence-Transformers all-MiniLM-L6-v2, loaded once per process."""
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def _chroma_client():
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


@lru_cache(maxsize=1)
def _vectorstore():
    return Chroma(
        client=_chroma_client(),
        collection_name=settings.CHROMA_COLLECTION,
        embedding_function=_embeddings(),
    )


def is_available() -> bool:
    """
    True once the RAG dependencies import cleanly AND the ChromaDB service
    actually answers a heartbeat. Called lazily (not at import time) so a
    missing/unreachable Chroma container degrades gracefully instead of
    crashing app startup.
    """
    if _import_error is not None:
        logger.warning("RAG pipeline dependencies unavailable: %s", _import_error)
        return False
    try:
        _chroma_client().heartbeat()
        return True
    except Exception as e:
        logger.warning("ChromaDB unreachable at %s:%s (%s) - falling back to keyword search",
                        settings.CHROMA_HOST, settings.CHROMA_PORT, e)
        return False


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 120) -> list[str]:
    """LangChain's recursive splitter - paragraph/sentence-aware, with overlap
    so a fact split across a chunk boundary is still retrievable. Falls back
    to a plain fixed-size splitter if langchain-text-splitters isn't
    importable (chatbot.py only calls this when is_available() is True, but
    this stays safe to call directly too, e.g. from tests)."""
    if _import_error is not None:
        return [text[i:i + chunk_size].strip() for i in range(0, len(text), chunk_size - chunk_overlap)
                if text[i:i + chunk_size].strip()]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if c.strip()]


def index_document(document_id: int, org_id: int, document_name: str, chunks: list[str]) -> list[str]:
    """
    Embeds `chunks` with Sentence-Transformers and upserts them into the
    org's ChromaDB collection. Returns the ChromaDB chunk IDs (persisted in
    rag_document_chunks.chromadb_chunk_id so we can re-sync / delete later).
    """
    ids = [f"doc{document_id}-chunk{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": document_id, "org_id": org_id, "document_name": document_name, "chunk_index": i}
        for i in range(len(chunks))
    ]
    docs = [Document(page_content=c, metadata=m) for c, m in zip(chunks, metadatas)]
    _vectorstore().add_documents(documents=docs, ids=ids)
    return ids


def delete_document(document_id: int) -> None:
    """Removes all of a document's chunks from ChromaDB (soft-delete on the SQL side happens in the router)."""
    _vectorstore()._collection.delete(where={"document_id": document_id})


def retrieve(org_id: int, query_text: str, top_k: int = 3) -> list[dict]:
    """
    Embeds the query and runs ChromaDB's similarity search scoped to this
    org, returning the top-k chunks with a 0-1 relevance score
    (1 - cosine distance) - this is the real semantic-search replacement for
    the SQL ILIKE fallback in routers/chatbot.py.
    """
    results = _vectorstore().similarity_search_with_relevance_scores(
        query_text, k=top_k, filter={"org_id": org_id},
    )
    return [
        {
            "chunk_text": doc.page_content,
            "document_name": doc.metadata.get("document_name"),
            "document_id": doc.metadata.get("document_id"),
            "chromadb_chunk_id": doc.id if hasattr(doc, "id") else None,
            "score": max(0.0, min(1.0, score)),
        }
        for doc, score in results
    ]


def generate_grounded_answer(query_text: str, retrieved: list[dict], gemini_key: str) -> tuple[str, str]:
    """
    LangChain-orchestrated call to Gemini 2.5 Flash: assembles the retrieved
    chunks into a grounding context and asks the model to answer using ONLY
    that context (the same groundedness contract the QA strategy's
    hallucination-detection eval script checks against). Returns
    (answer_text, model_name).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate

    context = "\n\n".join(f"[Source: {r['document_name']}]\n{r['chunk_text']}" for r in retrieved)
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an HR policy assistant. Answer the employee's question using ONLY the "
         "context provided. Be concise, friendly, and accurate. If the context doesn't "
         "contain the answer, say you're not sure and suggest escalating to HR."),
        ("human", "Context:\n{context}\n\nEmployee question: {question}\n\nAnswer:"),
    ])
    llm = ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL_NAME, google_api_key=gemini_key, temperature=0.2)
    chain = prompt | llm
    response = chain.invoke({"context": context, "question": query_text})
    return response.content.strip(), f"{settings.GEMINI_MODEL_NAME} (via LangChain)"
