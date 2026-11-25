"""WhatsApp Inbound Webhook Channel: Handles Meta WhatsApp Cloud API and Twilio Sandbox.
Provides:
- Cryptographic signature validation (Meta X-Hub-Signature-256 HMAC-SHA256, Twilio X-Twilio-Signature HMAC-SHA1)
- Tenant isolation via phone-hash mapping in `whatsapp_links` (never defaults to demo)
- One-time pairing code flow for linking mobile numbers
- Human-in-the-loop loan approvals over WhatsApp for linked phones
- PII protection: masked phone numbers (e.g. **********10) and truncated message previews in audit logs
"""
import io
import json
import hmac
import base64
import hashlib
import logging
import datetime as dt
from typing import Dict, Any, Optional, Tuple
from PIL import Image

from .. import config, orchestrator
from ..agents import quality, finance
from ..channels.voice import voice_adapter
from ..store import log, get_approval, update_approval_status
from ..db.database import SessionLocal
from ..db.models import WhatsAppLink, WhatsAppLinkThrottle
from ..auth import hash_phone, mask_phone

logger = logging.getLogger("bharatsetu.whatsapp")

def verify_meta_webhook(mode: str, token: str, challenge: str) -> Optional[str]:
    """Verifies Meta WhatsApp Cloud API webhook registration handshake."""
    if not config.WHATSAPP_VERIFY_TOKEN:
        if config.DEMO_MODE and token == "bharatsetu_verify_token":
            return challenge
        return None
    if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
        logger.info("Meta WhatsApp Cloud API webhook verified successfully.")
        return challenge
    return None

def verify_meta_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Verifies X-Hub-Signature-256 as HMAC-SHA256 of raw request body using WHATSAPP_APP_SECRET."""
    if not signature_header:
        return False
    secret = config.WHATSAPP_APP_SECRET
    if not secret:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.strip())

def verify_twilio_signature(url: str, params: Dict[str, Any], signature_header: Optional[str]) -> bool:
    """Validates X-Twilio-Signature using TWILIO_AUTH_TOKEN and the full request URL."""
    if not signature_header:
        return False
    auth_token = config.TWILIO_AUTH_TOKEN
    if not auth_token:
        return False
    s = url
    for k in sorted(params.keys()):
        s += k + str(params[k])
    mac = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1)
    expected = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(expected, signature_header.strip())

def resolve_tenant_from_phone(sender_phone: str, text_message: str = "") -> Tuple[Optional[str], Optional[str]]:
    """Resolves the msme_id bound to the sender phone via whatsapp_links table.
    If unlinked, handles LINK <code> pairing with brute-force throttling or returns link guidance reply.
    """
    db = SessionLocal()
    try:
        p_hash = hash_phone(sender_phone)
        link = db.query(WhatsAppLink).filter(WhatsAppLink.phone_hash == p_hash, WhatsAppLink.verified_at.isnot(None)).first()
        if link:
            return link.msme_id, None

        # Check for pairing command: e.g. "LINK ABCD-EFGH" or "LINK abcdefgh"
        clean_text = text_message.strip().upper()
        if clean_text.startswith("LINK "):
            now_utc = dt.datetime.now(dt.timezone.utc)
            now_naive = now_utc.replace(tzinfo=None)

            # 1. Check brute-force lockout for this sender phone (5 failed attempts in 30m -> 60m lockout)
            throttle = db.query(WhatsAppLinkThrottle).filter(WhatsAppLinkThrottle.phone_hash == p_hash).first()
            if throttle and throttle.locked_until:
                locked_exp = throttle.locked_until
                if locked_exp.tzinfo is not None:
                    locked_exp = locked_exp.astimezone(dt.timezone.utc).replace(tzinfo=None)
                if locked_exp > now_naive:
                    logger.warning(f"Throttled WhatsApp pairing attempt from {mask_phone(sender_phone)}")
                    return None, "⚠️ Too many failed attempts. Please try again later."
                else:
                    # Lockout expired, reset counters
                    throttle.failed_count = 0
                    throttle.first_failed_at = None
                    throttle.locked_until = None
                    db.commit()

            raw_code = clean_text.split(" ", 1)[1].strip()
            # Accept case-insensitively with dashes and spaces removed
            clean_code = raw_code.replace("-", "").replace(" ", "").upper()

            # Compare against pending unverified links using constant-time hmac.compare_digest
            pending_links = db.query(WhatsAppLink).filter(
                WhatsAppLink.verified_at.is_(None),
                WhatsAppLink.otp_code.isnot(None)
            ).all()

            matched_link = None
            for pl in pending_links:
                if pl.otp_code and hmac.compare_digest(pl.otp_code.upper(), clean_code):
                    exp = pl.otp_expires_at
                    if exp:
                        if exp.tzinfo is not None:
                            exp = exp.astimezone(dt.timezone.utc).replace(tzinfo=None)
                        if exp > now_naive:
                            matched_link = pl
                            break

            if matched_link:
                # Success! Link phone, reset throttle, make code single-use
                matched_link.phone_hash = p_hash
                matched_link.verified_at = now_utc
                matched_link.otp_code = None  # Single-use: invalidates code immediately
                matched_link.otp_expires_at = None
                if throttle:
                    db.delete(throttle)
                db.commit()
                logger.info(f"WhatsApp successfully linked for {mask_phone(sender_phone)} to {matched_link.msme_id}")
                return matched_link.msme_id, (
                    "✅ *WhatsApp Linked Successfully!*\n"
                    "Aapka WhatsApp number ab aapki factory profile se jud gaya hai. "
                    "Ab aap loan status, carbon reports, machine alerts aur compliance deadlines yahan dekh sakte hain."
                )

            # Verification failed: code wrong, expired, or already used
            # Never reveal whether code exists, expired, or was wrong.
            logger.warning(f"Failed WhatsApp pairing attempt from {mask_phone(sender_phone)}")
            if not throttle:
                throttle = WhatsAppLinkThrottle(phone_hash=p_hash, failed_count=1, first_failed_at=now_utc)
                db.add(throttle)
            else:
                first_fail = throttle.first_failed_at
                if first_fail and first_fail.tzinfo is not None:
                    first_fail = first_fail.astimezone(dt.timezone.utc).replace(tzinfo=None)
                if first_fail and (now_naive - first_fail) > dt.timedelta(minutes=30):
                    throttle.failed_count = 1
                    throttle.first_failed_at = now_utc
                else:
                    throttle.failed_count += 1

                if throttle.failed_count >= 5:
                    throttle.locked_until = now_utc + dt.timedelta(minutes=60)
                    logger.warning(f"WhatsApp pairing locked out for 60m for {mask_phone(sender_phone)} after 5 failed attempts")
            db.commit()

            if throttle.failed_count >= 5:
                return None, "⚠️ Too many failed attempts. Please try again later."
            return None, "⚠️ Invalid pairing code. Please generate a new code from your web dashboard and try again."

        # Unlinked mobile number -> Reject data access and provide linking instructions
        unlinked_msg = (
            "⚠️ *Namaste! Phone Not Linked*\n\n"
            "Aapka WhatsApp number kisi registered MSME se linked nahi hai.\n"
            "Apni factory ko connect karne ke liye:\n"
            "1. Web dashboard me login karein.\n"
            "2. 'Link WhatsApp' par click karein aur mila hua code yahan bhejein:\n"
            "   (Jaise: *LINK ABCD-EFGH*)\n\n"
            "Data security hetu bina link kiye koi jankari sajha nahi ki ja sakti."
        )
        return None, unlinked_msg
    finally:
        db.close()

def handle_whatsapp_approval(cmd: str, pid: str, msme_id: str, sender_phone: str) -> Dict[str, Any]:
    """Processes loan or filing approvals received via WhatsApp from a verified linked phone."""
    is_ok = cmd.upper() == "APPROVE"
    appr = get_approval(pid, msme_id=msme_id)
    if not appr or appr.get("status") != "pending":
        return {
            "type": "approval",
            "reply": f"⚠️ Approval `{pid}` not found or already processed for your enterprise."
        }

    masked = mask_phone(sender_phone)
    if not is_ok:
        update_approval_status(pid, "declined", resolved_by=f"whatsapp:{masked}")
        log("Finance Agent", f"Owner declined application via WhatsApp ({masked})", consent="human declined", msme_id=msme_id)
        return {"type": "approval", "reply": f"❌ Loan application `{pid}` has been DECLINED. Nothing was submitted."}

    update_approval_status(pid, "submitted", resolved_by=f"whatsapp:{masked}")
    res = finance.execute(appr, msme_id=msme_id)
    return {
        "type": "approval",
        "reply": f"✅ Loan application `{pid}` APPROVED and submitted to {res.get('lender', 'lender')}. Application reference: {res.get('application_id')}"
    }

def process_inbound_whatsapp(
    payload: Dict[str, Any],
    raw_media: Optional[bytes] = None
) -> Dict[str, Any]:
    """Processes incoming WhatsApp messages from either Meta Cloud API or Twilio.
    Resolves tenant strictly from whatsapp_links table; never defaults to demo.
    """
    sender_phone = ""
    msg_type = "text"
    text_body = ""

    # 1. Twilio Sandbox Format check
    if "Body" in payload or "MediaUrl0" in payload or "MediaContentType0" in payload:
        sender_phone = payload.get("From", "").replace("whatsapp:", "").strip()
        media_type = payload.get("MediaContentType0", "")
        text_body = payload.get("Body", "").strip()

        if media_type.startswith("image/"):
            msg_type = "image"
        elif media_type.startswith("audio/") or "voice" in media_type:
            msg_type = "voice"
        else:
            msg_type = "text"

    # 2. Meta WhatsApp Cloud API Format check
    elif "entry" in payload:
        entry = payload.get("entry", [])
        if entry:
            changes = entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                if messages:
                    msg = messages[0]
                    sender_phone = msg.get("from", "").strip()
                    msg_type = msg.get("type", "text")
                    if msg_type == "text":
                        text_body = msg.get("text", {}).get("body", "").strip()

    if not sender_phone:
        return {"type": "error", "reply": "Invalid WhatsApp payload: sender phone missing."}

    # Resolve tenant isolation via salted phone hash
    msme_id, link_reply = resolve_tenant_from_phone(sender_phone, text_message=text_body)
    if not msme_id:
        return {"type": "unlinked_phone", "reply": link_reply}

    # If the user just completed linking, send the welcome/link confirmation
    if link_reply:
        return {"type": "link_success", "reply": link_reply}

    masked = mask_phone(sender_phone)
    preview = (text_body[:24] + "…") if len(text_body) > 24 else text_body

    # Check for direct loan approval commands over WhatsApp: e.g. "APPROVE appr_loan_01" or "DECLINE appr_loan_01"
    parts = text_body.split()
    if len(parts) == 2 and parts[0].upper() in ("APPROVE", "DECLINE"):
        return handle_whatsapp_approval(parts[0].upper(), parts[1], msme_id, sender_phone)

    # Route based on message type
    if msg_type == "image":
        log("WhatsApp", f"Received part photo from {masked}; routing to Quality Agent", msme_id=msme_id)
        media_bytes = raw_media
        if not media_bytes:
            buf = io.BytesIO()
            Image.new("RGB", (360, 200), (170, 175, 180)).save(buf, "PNG")
            media_bytes = buf.getvalue()
        inspection = quality.inspect_image(media_bytes, msme_id=msme_id)
        reply_text = (
            f"🔍 *Quality Inspection Result ({inspection['model_used']})*\n"
            f"Verdict: *{inspection['verdict']}*\n"
            f"Defect Score: {inspection['defect_score']}/100\n"
            f"Note: {inspection['note']}"
        )
        return {"type": "image_inspection", "reply": reply_text, "inspection": inspection}

    elif msg_type == "voice":
        log("WhatsApp", f"Received voice note from {masked}; transcribing via Bhashini", msme_id=msme_id)
        media_bytes = raw_media or b"FAKE_AUDIO_BYTES_FOR_TESTING"
        trans_res = voice_adapter.transcribe(media_bytes, source_lang="hi", msme_id=msme_id)
        transcript = trans_res.get("transcript", "")
        out = orchestrator.chat(session_id=f"wa_{masked}", text=transcript, msme_id=msme_id)
        reply_text = f"🎙️ *Voice Note:* \"{transcript}\"\n\n🤖 *Setu:* {out['reply']}"
        return {"type": "voice_chat", "transcript": transcript, "reply": reply_text, "trace": out.get("trace", [])}

    else:
        log("WhatsApp", f"Received text message from {masked}: '{preview}'", msme_id=msme_id)
        out = orchestrator.chat(session_id=f"wa_{masked}", text=text_body, msme_id=msme_id)
        return {
            "type": "text_chat",
            "reply": out["reply"],
            "trace": out.get("trace", []),
            "pending": out.get("pending", [])
        }
