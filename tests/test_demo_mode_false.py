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

def test_jwt_secret_validation_enforcement():
    from backend.config import validate_jwt_secret
    # In production (is_demo=False), short or missing secret must raise RuntimeError
    with pytest.raises(RuntimeError) as exc_missing:
        validate_jwt_secret("", is_demo=False)
    assert "FATAL: JWT_SECRET" in str(exc_missing.value)

    with pytest.raises(RuntimeError) as exc_short:
        validate_jwt_secret("short-secret-key", is_demo=False)
    assert "FATAL: JWT_SECRET" in str(exc_short.value)

    # In DEMO_MODE, it generates an ephemeral secret
    ephemeral = validate_jwt_secret("", is_demo=True)
    assert len(ephemeral) >= 32

    # A valid long secret passes in both modes
    long_secret = "super-secret-production-key-at-least-32-chars-long"
    assert validate_jwt_secret(long_secret, is_demo=False) == long_secret
    assert validate_jwt_secret(long_secret, is_demo=True) == long_secret
