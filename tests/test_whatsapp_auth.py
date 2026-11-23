import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from backend import config
from backend.main import app
from backend.db.database import SessionLocal
from backend.db.models import MSME, User, Approval, WhatsAppLink
from backend.channels.whatsapp import hash_phone

client = TestClient(app)

def test_whatsapp_webhook_signature_and_tenant_isolation(monkeypatch):
    test_secret = "test_whatsapp_meta_app_secret_32_chars"
    monkeypatch.setattr(config, "WHATSAPP_APP_SECRET", test_secret)
    monkeypatch.setattr(config, "DEMO_MODE", False)

    body = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "+919111122222",
                        "type": "text",
                        "text": {"body": "Check my financial status"}
                    }]
                }
            }]
        }]
    }
    raw_body = json.dumps(body).encode("utf-8")

    # 1. Missing signature header -> 403
    r_no_sig = client.post("/api/webhook/whatsapp", data=raw_body, headers={"Content-Type": "application/json"})
    assert r_no_sig.status_code == 403

    # 2. Invalid signature header -> 403
    r_bad_sig = client.post(
        "/api/webhook/whatsapp",
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalidhex00000"}
    )
    assert r_bad_sig.status_code == 403

    # 3. Valid signature from UNLINKED phone -> returns link instructions, no data access
    valid_sig = "sha256=" + hmac.new(test_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    r_unlinked = client.post(
        "/api/webhook/whatsapp",
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig}
    )
    assert r_unlinked.status_code == 200
    res_data = r_unlinked.json()
    assert res_data["type"] == "unlinked_phone"
    assert "Phone Not Linked" in res_data["reply"]

    # 4. Authenticated owner requests WhatsApp pairing OTP code from web app
    r_reg = client.post("/api/auth/register", json={
        "username": "wa_owner_user",
        "password": "Password123#",
        "msme_name": "Indore Precision Tools",
        "udyam": "UDYAM-MP-23-8888001"
    })
    assert r_reg.status_code == 200
    token = r_reg.json()["token"]
    msme_id = r_reg.json()["msme_id"]

    r_otp = client.post("/api/whatsapp/link/request-otp", headers={"Authorization": f"Bearer {token}"})
    assert r_otp.status_code == 200
    otp_code = r_otp.json()["otp_code"]

    # 5. Owner sends "LINK <code>" from WhatsApp (+919111122222)
    link_body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "+919111122222",
                        "type": "text",
                        "text": {"body": f"LINK {otp_code}"}
                    }]
                }
            }]
        }]
    }
    raw_link = json.dumps(link_body).encode("utf-8")
    link_sig = "sha256=" + hmac.new(test_secret.encode("utf-8"), raw_link, hashlib.sha256).hexdigest()
    r_link = client.post("/api/webhook/whatsapp", data=raw_link, headers={"Content-Type": "application/json", "X-Hub-Signature-256": link_sig})
    assert r_link.status_code == 200
    assert r_link.json()["type"] == "link_success"

    # 6. Now sender is linked! Send a query -> routes to their msme_id
    query_body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "+919111122222",
                        "type": "text",
                        "text": {"body": "Check compliance deadlines"}
                    }]
                }
            }]
        }]
    }
    raw_query = json.dumps(query_body).encode("utf-8")
    query_sig = "sha256=" + hmac.new(test_secret.encode("utf-8"), raw_query, hashlib.sha256).hexdigest()
    r_query = client.post("/api/webhook/whatsapp", data=raw_query, headers={"Content-Type": "application/json", "X-Hub-Signature-256": query_sig})
    assert r_query.status_code == 200
    assert r_query.json()["type"] == "text_chat"

    # 7. WhatsApp Approval flow: create pending loan for this MSME
    from backend.store import new_approval
    pid = new_approval("working_capital_loan", {"amount_rs": 1000000, "lender": "SBI"}, msme_id=msme_id)

    appr_body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "+919111122222",
                        "type": "text",
                        "text": {"body": f"APPROVE {pid}"}
                    }]
                }
            }]
        }]
    }
    raw_appr = json.dumps(appr_body).encode("utf-8")
    appr_sig = "sha256=" + hmac.new(test_secret.encode("utf-8"), raw_appr, hashlib.sha256).hexdigest()
    r_appr = client.post("/api/webhook/whatsapp", data=raw_appr, headers={"Content-Type": "application/json", "X-Hub-Signature-256": appr_sig})
    assert r_appr.status_code == 200
    assert "APPROVED" in r_appr.json()["reply"]

    # Single-use check: cannot approve again
    r_appr_2 = client.post("/api/webhook/whatsapp", data=raw_appr, headers={"Content-Type": "application/json", "X-Hub-Signature-256": appr_sig})
    assert "not found or already processed" in r_appr_2.json()["reply"]
