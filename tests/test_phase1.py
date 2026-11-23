import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db.database import SessionLocal
from backend.db.models import MSME, User, Approval

client = TestClient(app)

def test_auth_and_isolation():
    # Register MSME 1
    r1 = client.post("/api/auth/register", json={
        "username": "owner_pithampur",
        "password": "password123",
        "msme_name": "Pithampur Castings Pvt Ltd",
        "city": "Pithampur",
        "udyam": "UDYAM-MP-23-9999001",
        "sector": "metal castings"
    })
    assert r1.status_code == 200
    token1 = r1.json()["token"]

    # Register MSME 2
    r2 = client.post("/api/auth/register", json={
        "username": "owner_sanwer",
        "password": "password123",
        "msme_name": "Sanwer Gears LLP",
        "city": "Sanwer Road, Indore",
        "udyam": "UDYAM-MP-23-9999002",
        "sector": "gear manufacturing"
    })
    assert r2.status_code == 200
    token2 = r2.json()["token"]

    # Check /api/auth/me for user 1
    me1 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token1}"})
    assert me1.status_code == 200
    assert me1.json()["msme"]["name"] == "Pithampur Castings Pvt Ltd"

    # Check /api/auth/me for user 2
    me2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert me2.status_code == 200
    assert me2.json()["msme"]["name"] == "Sanwer Gears LLP"

    # User 1 chats about loan
    chat1 = client.post(
        "/api/chat",
        json={"text": "I need a subsidy and loan"},
        headers={"Authorization": f"Bearer {token1}"}
    ).json()
    pid1 = chat1["approval_id"]

    # User 2 tries to access User 1's pending approval
    state2 = client.get("/api/state", headers={"Authorization": f"Bearer {token2}"}).json()
    pending_ids_2 = [p["id"] for p in state2["pending"]]
    assert pid1 not in pending_ids_2

    # User 2 cannot approve User 1's loan
    bad_approve = client.post(f"/api/approve/{pid1}", headers={"Authorization": f"Bearer {token2}"})
    assert bad_approve.status_code == 404

    # User 1 approves their own loan
    good_approve = client.post(f"/api/approve/{pid1}", headers={"Authorization": f"Bearer {token1}"})
    assert good_approve.status_code == 200
    assert good_approve.json()["status"] == "submitted"

def test_login_invalid_password():
    r = client.post("/api/auth/login", json={"username": "owner", "password": "wrongpassword"})
    assert r.status_code == 401

def test_login_success():
    r = client.post("/api/auth/login", json={"username": "owner", "password": "setu123"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_human_in_the_loop_decline():
    chat = client.post("/api/chat", json={"text": "loan application"}).json()
    pid = chat["approval_id"]
    r = client.post(f"/api/approve/{pid}?ok=false")
    assert r.status_code == 200
    assert r.json()["status"] == "declined"
    # Cannot approve after decline
    assert client.post(f"/api/approve/{pid}").status_code == 404

def test_upload_cap():
    huge_data = b"0" * (8 * 1024 * 1024 + 1024)
    r = client.post("/api/inspect", files={"file": ("huge.png", huge_data, "image/png")})
    assert r.status_code == 413
