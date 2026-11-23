"""WhatsApp Inbound Webhook Channel: Handles Meta WhatsApp Cloud API and Twilio Sandbox.
Intelligently routes:
- Text messages -> Setu orchestrator
- Part photos/images -> Quality Agent (YOLO defect inspection)
- Voice notes -> Bhashini Speech-to-Text -> Setu orchestrator
"""
import io
import json
import logging
from typing import Dict, Any, Optional
from PIL import Image
from .. import config, orchestrator
from ..agents import quality
from ..channels.voice import voice_adapter
from ..store import log

logger = logging.getLogger("bharatsetu.whatsapp")

def verify_meta_webhook(mode: str, token: str, challenge: str) -> Optional[str]:
    """Verifies Meta WhatsApp Cloud API webhook registration handshake."""
    if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta WhatsApp Cloud API webhook verified successfully.")
        return challenge
    return None

def process_inbound_whatsapp(
    payload: Dict[str, Any],
    raw_media: Optional[bytes] = None,
    msme_id: str = "demo"
) -> Dict[str, Any]:
    """Processes incoming WhatsApp messages from either Meta Cloud API or Twilio."""
    # 1. Twilio Sandbox Format check (Form URL encoded / dict)
    if "Body" in payload or "MediaUrl0" in payload or "MediaContentType0" in payload:
        sender_phone = payload.get("From", "+919876543210")
        msg_type = payload.get("MediaContentType0", "")

        if msg_type.startswith("image/") and raw_media:
            log("WhatsApp", f"Received part photo from {sender_phone}; routing to Quality Agent", msme_id=msme_id)
            inspection = quality.inspect_image(raw_media, msme_id=msme_id)
            reply_text = (
                f"🔍 *Quality Inspection Result ({inspection['model_used']})*\n"
                f"Verdict: *{inspection['verdict']}*\n"
                f"Defect Score: {inspection['defect_score']}/100\n"
                f"Note: {inspection['note']}"
            )
            return {"type": "image_inspection", "reply": reply_text, "inspection": inspection}

        elif (msg_type.startswith("audio/") or "voice" in msg_type) and raw_media:
            log("WhatsApp", f"Received voice note from {sender_phone}; transcribing via Bhashini", msme_id=msme_id)
            trans_res = voice_adapter.transcribe(raw_media, source_lang="hi", msme_id=msme_id)
            transcript = trans_res.get("transcript", "")
            out = orchestrator.chat(session_id=f"wa_{sender_phone}", text=transcript, msme_id=msme_id)
            reply_text = f"🎙️ *Voice Note:* \"{transcript}\"\n\n🤖 *Setu:* {out['reply']}"
            return {"type": "voice_chat", "transcript": transcript, "reply": reply_text, "trace": out.get("trace", [])}

        text_body = payload.get("Body", "").strip()
        log("WhatsApp", f"Received text message from {sender_phone}: '{text_body}'", msme_id=msme_id)
        out = orchestrator.chat(session_id=f"wa_{sender_phone}", text=text_body, msme_id=msme_id)
        return {"type": "text_chat", "reply": out["reply"], "trace": out.get("trace", []), "pending": out.get("pending", [])}

    # 2. Meta WhatsApp Cloud API JSON Format check
    entry = payload.get("entry", [])
    if entry:
        changes = entry[0].get("changes", [])
        if changes:
            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if messages:
                msg = messages[0]
                msg_type = msg.get("type", "text")
                sender = msg.get("from", "+919876543210")

                if msg_type == "text":
                    body_text = msg.get("text", {}).get("body", "")
                    log("WhatsApp", f"Meta Cloud API text from {sender}: '{body_text}'", msme_id=msme_id)
                    out = orchestrator.chat(session_id=f"wa_{sender}", text=body_text, msme_id=msme_id)
                    return {"type": "text_chat", "reply": out["reply"], "trace": out.get("trace", [])}

                elif msg_type == "image":
                    log("WhatsApp", f"Meta Cloud API image from {sender}; routing to Quality Agent", msme_id=msme_id)
                    # When simulated or raw_media provided
                    media_bytes = raw_media
                    if not media_bytes:
                        # Synthetic test image
                        buf = io.BytesIO()
                        Image.new("RGB", (360, 200), (170, 175, 180)).save(buf, "PNG")
                        media_bytes = buf.getvalue()
                    inspection = quality.inspect_image(media_bytes, msme_id=msme_id)
                    reply_text = f"🔍 *Inspection Result:* {inspection['verdict']} (Defect score: {inspection['defect_score']}/100). {inspection['note']}"
                    return {"type": "image_inspection", "reply": reply_text, "inspection": inspection}

                elif msg_type in ("audio", "voice"):
                    log("WhatsApp", f"Meta Cloud API voice from {sender}; routing to Bhashini", msme_id=msme_id)
                    media_bytes = raw_media or b"FAKE_AUDIO_BYTES_FOR_TESTING"
                    trans_res = voice_adapter.transcribe(media_bytes, source_lang="hi", msme_id=msme_id)
                    transcript = trans_res.get("transcript", "")
                    out = orchestrator.chat(session_id=f"wa_{sender}", text=transcript, msme_id=msme_id)
                    return {"type": "voice_chat", "transcript": transcript, "reply": out["reply"], "trace": out.get("trace", [])}

    return {"type": "unknown", "reply": "Namaste! Send a text, voice note, or part photo to Setu."}
