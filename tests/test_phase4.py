import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from backend.main import app

client = TestClient(app)

def test_whatsapp_meta_webhook_verification():
    # Correct token
    r = client.get("/api/webhook/whatsapp?hub.mode=subscribe&hub.challenge=test_chal_123&hub.verify_token=bharatsetu_verify_token")
    assert r.status_code == 200
    assert r.text == "test_chal_123"

    # Bad token
    r_bad = client.get("/api/webhook/whatsapp?hub.mode=subscribe&hub.challenge=test_chal_123&hub.verify_token=wrong_token")
    assert r_bad.status_code == 403

def test_whatsapp_inbound_text():
    meta_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "wa_biz_01",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "+919876543210",
                                    "id": "wamid_001",
                                    "type": "text",
                                    "text": {"body": "Check GST and compliance deadlines"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    r = client.post("/api/webhook/whatsapp", json=meta_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "text_chat"
    assert "Compliance Agent" in data["trace"]
    assert "Upcoming compliance deadlines" in data["reply"]

def test_whatsapp_inbound_image_to_quality_agent():
    # Build test image with scratch defect
    bad = Image.new("RGB", (360, 200), (170, 175, 180))
    ImageDraw.Draw(bad).line((210, 60, 290, 150), fill=(40, 40, 40), width=4)
    buf = io.BytesIO()
    bad.save(buf, "PNG")

    # Twilio-style multipart format with image attachment
    r = client.post(
        "/api/webhook/whatsapp",
        data={"From": "+919876543210", "MediaContentType0": "image/png"},
        files={"file": ("part.png", buf.getvalue(), "image/png")}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "image_inspection"
    assert data["inspection"]["verdict"] == "FAIL"

def test_whatsapp_inbound_voice_note():
    audio_fake = b"RIFF....WAVEfmt...."
    r = client.post(
        "/api/webhook/whatsapp",
        data={"From": "+919876543210", "MediaContentType0": "audio/ogg"},
        files={"file": ("voice.ogg", audio_fake, "audio/ogg")}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "voice_chat"
    assert "transcript" in data
    assert len(data["reply"]) > 0

def test_voice_transcribe_and_synthesize():
    # 1. Transcribe endpoint
    audio_bytes = b"RIFF_FAKE_AUDIO_SAMPLE"
    r_tr = client.post(
        "/api/voice/transcribe?source_lang=hi",
        files={"file": ("sample.wav", audio_bytes, "audio/wav")}
    )
    assert r_tr.status_code == 200
    tr_data = r_tr.json()
    assert tr_data["status"] == "success"
    assert "transcript" in tr_data

    # 2. Synthesize endpoint
    r_syn = client.post("/api/voice/synthesize?text=नमस्ते&target_lang=hi")
    assert r_syn.status_code == 200
    syn_data = r_syn.json()
    assert syn_data["status"] == "success"
    assert "audio_base64" in syn_data

def test_frontend_index_and_bilingual_elements():
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    # Verify Devanagari Hindi presence
    assert "भारतसेतु एआई" in html
    assert "Pithampur Auto Cluster" in html
    # Verify bilingual toggle and voice mic button presence
    assert "toggleLang" in html
    assert "triggerVoiceInput" in html
    assert "auth-modal" in html
