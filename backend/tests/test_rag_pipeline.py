"""
Unit tests for the pure/no-network parts of app/rag_pipeline.py — chunking
logic doesn't need ChromaDB or an embedding model to be reachable.
"""
import pytest

rag_pipeline = pytest.importorskip("app.rag_pipeline", reason="RAG deps (langchain/chromadb) not installed")


def test_chunk_text_splits_long_document():
    text = ("Paragraph one about leave policy. " * 30) + "\n\n" + ("Paragraph two about payslips. " * 30)
    chunks = rag_pipeline.chunk_text(text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 260 for c in chunks)  # allow a little slack for overlap/splitter behaviour
    assert all(c.strip() for c in chunks)


def test_chunk_text_handles_short_document():
    text = "Short policy note."
    chunks = rag_pipeline.chunk_text(text)
    assert chunks == ["Short policy note."]


def test_chunk_text_empty_input():
    assert rag_pipeline.chunk_text("") == []


def test_is_available_false_when_chroma_unreachable():
    """With no ChromaDB service running in the unit-test environment, the
    pipeline must report unavailable rather than raising — the caller
    (routers/chatbot.py) depends on this to fall back to keyword search."""
    assert rag_pipeline.is_available() is False


def test_reindex_all_from_postgres_noop_when_chroma_unreachable(db_session):
    """The startup self-heal hook (app/main.py) must never block API
    startup — reindex_all_from_postgres() has to no-op safely (return 0,
    not raise) when ChromaDB isn't reachable, exactly like every other
    entry point in this module."""
    assert rag_pipeline.reindex_all_from_postgres(db_session) == 0
