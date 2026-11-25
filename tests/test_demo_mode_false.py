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

    # DPI routes must all reject anonymous requests with 401
    dpi_routes = [
        ("POST", "/api/dpi/aa/consent", {"phone": "+919876543210"}),
        ("GET", "/api/dpi/aa/financials?consent_handle=test", None),
        ("GET", "/api/dpi/gst/status", None),
        ("POST", "/api/dpi/gst/eway-bill", {"invoice_no": "INV-100", "to_pincode": "452001"}),
        ("GET", "/api/dpi/digilocker/document?doc_type=udyam", None),
        ("GET", "/api/dpi/udyam/verify", None),
        ("POST", "/api/dpi/einvoicing/irn", {"invoice_num": "INV-001", "amount": 50000}),
        ("POST", "/api/dpi/upi/payment-link", {"amount": 1000, "description": "Test"}),
        ("GET", "/api/dpi/ulip/track?vehicle_no=MP09AB1234", None),
        ("POST", "/api/dpi/treds/discount", {"invoice_irn": "IRN-123", "bid_rate": 8.5}),
    ]
    for method, route, payload in dpi_routes:
        if method == "POST":
            res = client.post(route, json=payload)
        else:
            res = client.get(route)
        assert res.status_code == 401, f"Route {route} did not return 401 for anonymous caller"

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

    r_auth_chat = client.post("/api/chat", json={"text": "I need a loan for machinery"}, headers=headers)
    assert r_auth_chat.status_code == 200
    pid = r_auth_chat.json()["approval_id"]

    # 3. Unauthenticated approve returns 401 and the loan stays pending
    anon_approve = client.post(f"/api/approve/{pid}")
    assert anon_approve.status_code == 401

    # Loan stays pending
    check_state = client.get("/api/state", headers=headers).json()
    pending_item = next((p for p in check_state["pending"] if p["id"] == pid), None)
    assert pending_item is not None
    assert pending_item["status"] == "pending"

    # Authenticated approve succeeds
    auth_approve = client.post(f"/api/approve/{pid}", headers=headers)
    assert auth_approve.status_code == 200
    assert auth_approve.json()["status"] == "submitted"

def test_approval_id_randomness_and_length():
    import math
    import re
    from collections import Counter
    from backend import store

    ids = [store.new_approval("loan", {"test": True}, msme_id="test_tenant") for _ in range(1000)]
    
    # 1. All generated IDs must be unique
    assert len(set(ids)) == 1000

    # 2. Length must be at least 21 characters (secrets.token_urlsafe(16) is 22 chars)
    for aid in ids:
        assert len(aid) >= 21
        assert re.match(r"^[A-Za-z0-9_-]+$", aid)

    # 3. Shannon entropy check across sample to confirm high randomness (>4.5 bits/char)
    all_chars = "".join(ids)
    counts = Counter(all_chars)
    n = len(all_chars)
    entropy = -sum((count / n) * math.log2(count / n) for count in counts.values())
    assert entropy > 4.5

def test_jwt_secret_validation_enforcement():
    from backend.config import validate_jwt_secret
    # In production (is_demo=False), short or missing secret must raise RuntimeError
    with pytest.raises(RuntimeError) as exc_missing:
        validate_jwt_secret("", is_demo=False)
    assert "FATAL: JWT_SECRET" in str(exc_missing.value)

    with pytest.raises(RuntimeError) as exc_short:
        validate_jwt_secret("short-secret-key", is_demo=False)
    assert "FATAL: JWT_SECRET" in str(exc_short.value)

    # Known repository default secrets must be rejected in non-demo mode
    for forbidden in config.KNOWN_FORBIDDEN_JWT_SECRETS:
        with pytest.raises(RuntimeError) as exc_forbidden:
            validate_jwt_secret(forbidden, is_demo=False)
        assert "FATAL: JWT_SECRET" in str(exc_forbidden.value)
        assert "known public default" in str(exc_forbidden.value)

    # In DEMO_MODE, it generates an ephemeral secret
    ephemeral = validate_jwt_secret("", is_demo=True)
    assert len(ephemeral) >= 32

    # A valid long secret passes in both modes
    long_secret = "super-secret-production-key-at-least-32-chars-long"
    assert validate_jwt_secret(long_secret, is_demo=False) == long_secret
    assert validate_jwt_secret(long_secret, is_demo=True) == long_secret

def test_health_endpoint_public_minimal(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    # Must not leak tenant or state information
    assert "demo_mode" not in r.json()
    assert "msme" not in r.json()


def test_phone_hash_key_validation_enforcement():
    from backend.config import validate_phone_hash_key
    # In production (is_demo=False), short or missing key must raise RuntimeError
    with pytest.raises(RuntimeError) as exc_missing:
        validate_phone_hash_key("", is_demo=False)
    assert "FATAL: PHONE_HASH_KEY" in str(exc_missing.value)

    with pytest.raises(RuntimeError) as exc_short:
        validate_phone_hash_key("short-key-less-32", is_demo=False)
    assert "FATAL: PHONE_HASH_KEY" in str(exc_short.value)

    # In DEMO_MODE, it generates an ephemeral key of at least 32 characters
    ephemeral = validate_phone_hash_key("", is_demo=True)
    assert len(ephemeral) >= 32

    # A valid long key passes in both modes
    valid_key = "secure-production-phone-hash-key-at-least-32-chars-long"
    assert validate_phone_hash_key(valid_key, is_demo=False) == valid_key
    assert validate_phone_hash_key(valid_key, is_demo=True) == valid_key


def test_phone_hash_hmac_properties(monkeypatch):
    from backend.auth import hash_phone
    key1 = "test_key_1_at_least_32_characters_long_12345"
    key2 = "test_key_2_at_least_32_characters_long_67890"

    monkeypatch.setattr(config, "PHONE_HASH_KEY", key1)
    phone_raw = "+91 98765 43210"
    phone_clean = "+919876543210"

    # Deterministic output for same key and normalized number
    h1 = hash_phone(phone_raw)
    h2 = hash_phone(phone_clean)
    assert len(h1) == 64
    assert h1 == h2

    # Different key produces different HMAC
    monkeypatch.setattr(config, "PHONE_HASH_KEY", key2)
    h3 = hash_phone(phone_clean)
    assert h3 != h1
    assert len(h3) == 64


def test_whatsapp_verify_token_enforcement(monkeypatch):
    from backend.channels.whatsapp import verify_meta_webhook

    # Empty token in config -> rejected
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "")
    assert verify_meta_webhook("subscribe", "", "challenge123") is None
    assert verify_meta_webhook("subscribe", "any_token", "challenge123") is None

    # Token under 16 characters -> rejected
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "short_token_12")
    assert verify_meta_webhook("subscribe", "short_token_12", "challenge123") is None

    # Valid token >= 16 characters -> succeeds on exact match, fails on mismatch or empty query
    valid_token = "valid_verify_token_16_chars_min"
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", valid_token)
    assert verify_meta_webhook("subscribe", "", "challenge123") is None
    assert verify_meta_webhook("subscribe", "wrong_token_1234", "challenge123") is None
    assert verify_meta_webhook("subscribe", valid_token, "challenge123") == "challenge123"


def test_lazy_phone_hash_migration(monkeypatch):
    from backend.auth import hash_phone, legacy_hash_phone
    from backend.channels.whatsapp import resolve_tenant_from_phone
    from backend.db.database import SessionLocal
    from backend.db.models import WhatsAppLink
    import datetime as dt

    test_key = "secure_key_for_testing_lazy_migration_32_chars"
    monkeypatch.setattr(config, "PHONE_HASH_KEY", test_key)

    phone_num = "+919123456789"
    leg_hash = legacy_hash_phone(phone_num)
    mod_hash = hash_phone(phone_num)
    assert leg_hash != mod_hash

    db = SessionLocal()
    # Insert link with legacy salted hash
    db.query(WhatsAppLink).filter(WhatsAppLink.msme_id == "demo").delete()
    link = WhatsAppLink(
        phone_hash=leg_hash,
        msme_id="demo",
        verified_at=dt.datetime.now(dt.timezone.utc)
    )
    db.add(link)
    db.commit()
    db.close()

    # Call resolve_tenant_from_phone: must resolve tenant AND upgrade hash to modern HMAC
    tenant_id, reply = resolve_tenant_from_phone(phone_num)
    assert tenant_id == "demo"
    assert reply is None

    # Verify that in database, phone_hash is now the modern HMAC
    db2 = SessionLocal()
    updated_link = db2.query(WhatsAppLink).filter(WhatsAppLink.msme_id == "demo").first()
    assert updated_link.phone_hash == mod_hash
    db2.close()

