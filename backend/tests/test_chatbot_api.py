"""
Integration tests for the RAG chatbot — QA §10.2/10.3 requirements:
retrieval relevance, groundedness, and escalation routing.

These run the SQL keyword-search fallback path (no live ChromaDB container
in the test environment — see app/rag_pipeline.is_available()), which is
enough to validate the retrieval/escalation contract end-to-end. The real
ChromaDB path is exercised the same way once `docker compose up` is running
(see the RAG-specific eval notes in README.md).
"""
from app.models import HRPolicyDocument, RagDocumentChunk


def _seed_policy_doc(db_session, org_id, name, chunks):
    doc = HRPolicyDocument(org_id=org_id, document_name=name, document_type="leave_policy",
                            file_path=f"{name}.pdf", is_active=True, indexed_in_chromadb=False)
    db_session.add(doc); db_session.flush()
    for i, chunk in enumerate(chunks):
        db_session.add(RagDocumentChunk(document_id=doc.document_id, chunk_index=i,
                                         chunk_text=chunk, chromadb_chunk_id=f"test-{doc.document_id}-{i}"))
    db_session.commit()
    return doc


def test_query_retrieves_relevant_chunk_by_keyword_overlap(client, seeded, db_session):
    _seed_policy_doc(db_session, seeded.org.org_id, "Leave Policy", [
        "Employees are entitled to 10 days of Casual Leave and 10 days of Sick Leave per year.",
        "Provident Fund is deducted at 12 percent of Basic Salary as the employee contribution.",
    ])
    token = seeded.token_for(seeded.employee)
    res = client.post("/chatbot/query", json={"query_text": "How many casual leave days do I get?"},
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "Leave Policy" in body["source_documents"]
    assert body["query_category"] == "leave_policy"


def test_query_with_no_matching_policy_returns_ungrounded_low_confidence(client, seeded, db_session):
    _seed_policy_doc(db_session, seeded.org.org_id, "Code of Conduct", [
        "Employees must treat colleagues with respect and avoid conflicts of interest.",
    ])
    token = seeded.token_for(seeded.employee)
    res = client.post("/chatbot/query", json={"query_text": "What is the capital of France?"},
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    # No policy content is relevant to this question — must not be presented
    # as a confident, grounded answer (hallucination-prevention contract).
    assert body["is_grounded"] is False


def test_escalation_flow_creates_ticket_visible_to_hr_admin(client, seeded, db_session):
    token = seeded.token_for(seeded.employee)
    query_res = client.post("/chatbot/query", json={"query_text": "obscure question nothing matches"},
                             headers={"Authorization": f"Bearer {token}"})
    query_id = query_res.json()["query_id"]

    esc_res = client.post("/chatbot/escalate", json={"query_id": query_id, "reason": "low_confidence"},
                           headers={"Authorization": f"Bearer {token}"})
    assert esc_res.status_code == 201, esc_res.text

    hr_token = seeded.token_for(seeded.hr_admin)
    queue_res = client.get("/chatbot/escalations/queue", headers={"Authorization": f"Bearer {hr_token}"})
    assert queue_res.status_code == 200
    assert any(t["employee_name"] == seeded.employee.full_name for t in queue_res.json())


def test_groq_fallback_used_when_gemini_rate_limited(client, seeded, db_session, monkeypatch):
    """
    Proposal Risk #2 mitigation: 'Gemini API free tier rate limits hit
    during testing -> Switch to Groq free tier (llama3 70b) as backup LLM.'
    Never implemented until now (see app/rag_pipeline.generate_grounded_answer_groq).
    This simulates a Gemini 429/quota failure and asserts the chatbot
    transparently answers via Groq instead of dropping to the bare
    keyword-extraction fallback.
    """
    _seed_policy_doc(db_session, seeded.org.org_id, "Leave Policy", [
        "Employees are entitled to 10 days of Casual Leave and 10 days of Sick Leave per year.",
    ])
    from app import rag_pipeline
    from app.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-groq-key")

    class _FakeGeminiModel:
        def __init__(self, *a, **kw): pass
        def generate_content(self, prompt):
            raise Exception("429 Resource has been exhausted (e.g. check quota).")

    import google.generativeai as genai
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", _FakeGeminiModel)
    monkeypatch.setattr(
        rag_pipeline, "generate_grounded_answer_groq",
        lambda query_text, retrieved, groq_key: (
            "Per the Leave Policy, you get 10 days of Casual Leave per year.",
            "llama-3.3-70b-versatile (groq-fallback)",
        ),
    )

    token = seeded.token_for(seeded.employee)
    res = client.post("/chatbot/query", json={"query_text": "How many casual leave days do I get?"},
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "Casual Leave" in body["answer"]
    assert body["is_grounded"] is True


def test_gemini_non_rate_limit_error_does_not_trigger_groq(client, seeded, db_session, monkeypatch):
    """A non-quota Gemini failure (bad prompt, network blip, etc.) should NOT
    burn Groq quota — it should fall through to the plain keyword-extraction
    answer, same as before this fallback existed."""
    _seed_policy_doc(db_session, seeded.org.org_id, "Leave Policy", [
        "Employees are entitled to 10 days of Casual Leave and 10 days of Sick Leave per year.",
    ])
    from app import rag_pipeline
    from app.config import settings

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "fake-groq-key")

    class _FakeGeminiModel:
        def __init__(self, *a, **kw): pass
        def generate_content(self, prompt):
            raise Exception("500 internal server error")

    groq_called = {"value": False}

    def _fake_groq(*a, **kw):
        groq_called["value"] = True
        return "should not be used", "groq"

    import google.generativeai as genai
    monkeypatch.setattr(genai, "configure", lambda **kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", _FakeGeminiModel)
    monkeypatch.setattr(rag_pipeline, "generate_grounded_answer_groq", _fake_groq)

    token = seeded.token_for(seeded.employee)
    res = client.post("/chatbot/query", json={"query_text": "How many casual leave days do I get?"},
                       headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert groq_called["value"] is False


def test_only_hr_admin_can_upload_policy_documents(client, seeded):
    token = seeded.token_for(seeded.employee)
    res = client.post(
        "/chatbot/policy-docs/upload",
        data={"document_name": "Test Doc", "document_type": "other"},
        files={"file": ("test.txt", b"Some policy content here.", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
