"""Task API (src/api/agent_routes.py) without LLM calls: lifecycle, uploads, samples, guards."""
import pytest
from fastapi.testclient import TestClient

from src.api import agent_routes as R
from src.agents.service import TaskService


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(R, "_svc", TaskService(db_path=":memory:"))
    monkeypatch.setattr(R, "_runs", {})
    from src.api.main import app
    return TestClient(app)


def _pdf(text="FORM NO. 16"):
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_samples_listed_with_friendly_titles(client):
    d = client.get("/samples").json()
    assert [s["id"] for s in d["samples"]] == list(R.SAMPLE_TITLES)
    assert all(s["documents"] for s in d["samples"] if s["id"] != "P26") and "fictitious" in d["note"]


def test_create_upload_status_delete(client):
    tid = client.post("/tasks", json={"workflow": "document_check"}).json()["task_id"]
    r = client.post(f"/tasks/{tid}/documents", files={"file": ("f16.pdf", _pdf(), "application/pdf")})
    assert r.status_code == 200 and r.json()["documents"][0]["filename"] == "f16.pdf"
    st = client.get(f"/tasks/{tid}").json()
    assert st["status"] == "new" and st["goal"].startswith("Please check")
    assert client.delete(f"/tasks/{tid}").status_code == 200
    assert client.get(f"/tasks/{tid}").status_code == 404


def test_rejects_non_pdf_and_unknown_sample(client):
    tid = client.post("/tasks", json={}).json()["task_id"]
    r = client.post(f"/tasks/{tid}/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400 and "pdf" in r.json()["detail"]
    assert client.post("/tasks", json={"sample": "P99"}).status_code == 400


def test_sample_task_attaches_documents_and_answers(client):
    d = client.post("/tasks", json={"sample": "P23"}).json()
    assert len(d["documents"]) == 3 and "prepare my income tax return" in d["goal"]
    a = client.post("/samples/P23/answer", json={"fields": ["age", "rent_monthly"]}).json()
    assert "30 years old" in a["text"] and "rent" in a["text"]


def test_guards(client, monkeypatch):
    tid = client.post("/tasks", json={}).json()["task_id"]
    assert client.post(f"/tasks/{tid}/answer", json={"answer": "yes"}).status_code == 409   # not waiting
    assert client.get(f"/tasks/{tid}/ca_summary.md").status_code == 404
    started = []
    monkeypatch.setattr(R, "_launch", lambda t, fn: started.append(t))
    assert client.post(f"/tasks/{tid}/start").status_code == 200 and started == [tid]
    assert client.post(f"/tasks/{tid}/start").status_code == 409                          # only once
    r = client.post(f"/tasks/{tid}/documents", files={"file": ("f.pdf", _pdf(), "application/pdf")})
    assert r.status_code == 409                                                            # no uploads after start
