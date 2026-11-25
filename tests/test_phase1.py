import io
import os
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

    # User 2 cannot approve or decline User 1's loan (returns 404)
    bad_approve = client.post(f"/api/approve/{pid1}", headers={"Authorization": f"Bearer {token2}"})
    assert bad_approve.status_code == 404

    bad_decline = client.post(f"/api/approve/{pid1}?ok=false", headers={"Authorization": f"Bearer {token2}"})
    assert bad_decline.status_code == 404

    # B's approval is still pending afterwards
    state1 = client.get("/api/state", headers={"Authorization": f"Bearer {token1}"}).json()
    pending_ids_1 = [p["id"] for p in state1["pending"]]
    assert pid1 in pending_ids_1
    approval_obj = next(p for p in state1["pending"] if p["id"] == pid1)
    assert approval_obj["status"] == "pending"

    # Approval ID unguessability check
    assert len(pid1) >= 20
    import re
    assert re.match(r"^[A-Za-z0-9_-]+$", pid1)

    # User 1 approves their own loan
    good_approve = client.post(f"/api/approve/{pid1}", headers={"Authorization": f"Bearer {token1}"})
    assert good_approve.status_code == 200
    assert good_approve.json()["status"] == "submitted"

    # Approvals must be single-use: second approve returns 404
    second_approve = client.post(f"/api/approve/{pid1}", headers={"Authorization": f"Bearer {token1}"})
    assert second_approve.status_code == 404

def test_login_invalid_password():
    r = client.post("/api/auth/login", json={"username": "owner", "password": "wrongpassword"})
    assert r.status_code == 401

def test_login_success():
    pwd = os.getenv("SEED_OWNER_PASSWORD", "test_owner_secure_pass_123")
    r = client.post("/api/auth/login", json={"username": "owner", "password": pwd})
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

def test_password_hashing_and_legacy_upgrade():
    # 1. Enforce min length 10
    r_short = client.post("/api/auth/register", json={
        "username": "short_user",
        "password": "short",
        "msme_name": "Short Co",
        "udyam": "UDYAM-MP-23-0000101"
    })
    assert r_short.status_code == 422 or r_short.status_code == 400

    # 2. Register valid user -> uses bcrypt ($2b$)
    r_reg = client.post("/api/auth/register", json={
        "username": "bcrypt_user",
        "password": "StrongPassword123!",
        "msme_name": "Bcrypt Engineering",
        "udyam": "UDYAM-MP-23-0000102"
    })
    assert r_reg.status_code == 200
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "bcrypt_user").first()
        assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")

        # 3. Insert legacy SHA-256 user and verify it logs in and upgrades to bcrypt
        import hashlib, os
        salt = os.urandom(16).hex()
        sha_hash = hashlib.sha256((salt + "LegacyPass123!").encode()).hexdigest()
        legacy_user = User(
            id="user_legacy_01",
            msme_id="demo",
            username="legacy_user",
            password_hash=f"{salt}:{sha_hash}",
            role="owner"
        )
        db.add(legacy_user)
        db.commit()

        # Login with legacy user
        r_log = client.post("/api/auth/login", json={"username": "legacy_user", "password": "LegacyPass123!"})
        assert r_log.status_code == 200

        # Verify password_hash was automatically upgraded to bcrypt
        db.refresh(legacy_user)
        assert legacy_user.password_hash.startswith("$2b$") or legacy_user.password_hash.startswith("$2a$")
    finally:
        db.close()

def test_auth_rate_limiting_and_proxy_rules(monkeypatch):
    from backend import config
    from backend.middleware import auth_limiter

    test_ip = "192.168.1.99"
    # Reset timestamps for test_ip
    auth_limiter.requests[test_ip] = []

    # 10 attempts allowed
    for _ in range(10):
        assert auth_limiter.is_allowed(test_ip) is True

    # 11th attempt must be rejected
    assert auth_limiter.is_allowed(test_ip) is False

    # Stale eviction test
    old_time = 1000.0
    auth_limiter.requests["stale_ip_1"] = [old_time]
    auth_limiter.last_cleanup = 0.0  # Force cleanup on next call
    auth_limiter.is_allowed("active_ip")
    assert "stale_ip_1" not in auth_limiter.requests
