import pytest
import os
from fastapi.testclient import TestClient
from backend import config
from backend.main import app

def test_demo_mode_false_strict_security(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "ENABLE_DOCS", False)

    client = TestClient(app)

    # 1. Anonymous requests to protected routes must be rejected with 401
    r_chat = client.post("/api/chat", json={"text": "Hello"})
    assert r_chat.status_code == 401

    r_inspect = client.post("/api/inspect", files={"file": ("test.png", b"fake", "image/png")})
    assert r_inspect.status_code == 401

    r_approve = client.post("/api/approve/test_id")
    assert r_approve.status_code == 401

    r_owner = client.get("/api/dashboard/owner")
    assert r_owner.status_code == 401

    r_cluster = client.get("/api/dashboard/cluster")
    assert r_cluster.status_code == 401

    r_state = client.get("/api/state")
    assert r_state.status_code == 401

    r_pdf = client.get("/api/energy/carbon-report-pdf")
    assert r_pdf.status_code == 401

    # 2. Authenticated user works and gets isolated data
    r_reg = client.post("/api/auth/register", json={
        "username": "prod_owner_01",
        "password": "Password123#",
        "msme_name": "Pithampur Heavy Forgings",
        "city": "Pithampur",
        "udyam": "UDYAM-MP-23-7777001",
        "sector": "forging"
    })
    assert r_reg.status_code == 200
    token = r_reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r_auth_state = client.get("/api/state", headers=headers)
    assert r_auth_state.status_code == 200
    assert r_auth_state.json()["demo_mode"] is False

    r_auth_chat = client.post("/api/chat", json={"text": "hello"}, headers=headers)
    assert r_auth_chat.status_code == 200
