import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status, Query, Response, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import orchestrator, config
from .agents import (
    finance, quality, energy, market, maintenance,
    supply_chain, compliance, wellness
)
from .dpi import get_adapter
from .store import (
    AUDIT, KPI, PENDING, PROFILE, log,
    get_approval, update_approval_status,
    get_msme_profile, get_msme_kpi, get_msme_audit, get_msme_pending
)
from .db.database import get_db
from .db.models import User, MSME, ChatMessage
from .auth import (
    get_current_user_optional, get_current_user,
    hash_password, verify_password, create_access_token
)
from .deps import resolve_msme_id, require_official_role
from .channels.voice import voice_adapter
from .channels.whatsapp import verify_meta_webhook, process_inbound_whatsapp
from .dashboard import get_owner_dashboard, get_cluster_dashboard
from .middleware import StructuredLoggingAndRateLimitMiddleware

app = FastAPI(
    title="BharatSetu AI",
    description="Agentic DPI Copilot for MSMEs in Indore & Pithampur",
    version="1.0.0"
)

# Add structured logging and rate limiting middleware
app.add_middleware(StructuredLoggingAndRateLimitMiddleware)

FRONT = Path(__file__).resolve().parent.parent / "frontend"

# Schemas
class ChatIn(BaseModel):
    session_id: str = Field(default="demo", description="Session identifier for multi-turn conversation")
    text: str = Field(..., min_length=1, max_length=4000, description="User prompt in Hindi, English or Hinglish")

class LoginIn(BaseModel):
    username: str
    password: str

class RegisterIn(BaseModel):
    username: str
    password: str
    msme_name: str
    city: str = "Pithampur, Indore"
    udyam: str
    sector: str = "auto components"
    phone_number: str = ""

class CircularIn(BaseModel):
    content: str
    title: Optional[str] = "Pasted Notification"

class MarketListingIn(BaseModel):
    product_name: str
    price_inr: float
    moq: int = 500
    hsn_code: str = "8483"
    lead_time_days: int = 14

class AAConsentIn(BaseModel):
    customer_vpa: str = "owner@sbi"
    purpose: str = "Working Capital Credit Assessment"

class EwayBillIn(BaseModel):
    invoice_number: str
    to_gstin: str
    consignee_pincode: str = "454775"
    vehicle_number: str = "MP-09-GH-8219"
    value_inr: float = 450000.0

class EInvoicingIn(BaseModel):
    invoice_number: str
    buyer_gstin: str
    total_amount_inr: float
    tax_amount_inr: float = 0.0

class UPIPaymentIn(BaseModel):
    invoice_id: str
    amount_inr: float
    note: str = "Component Invoice Settlement"

class TReDSIn(BaseModel):
    invoice_number: str
    buyer_name: str
    buyer_gstin: str
    amount_rs: float
    due_days: int = 45

# --- Authentication Endpoints ---
@app.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == body.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    existing_udyam = db.query(MSME).filter(MSME.udyam == body.udyam).first()
    if existing_udyam:
        raise HTTPException(status_code=400, detail="Udyam registration already registered")

    import uuid
    msme_id = f"msme_{uuid.uuid4().hex[:8]}"
    new_msme = MSME(
        id=msme_id,
        name=body.msme_name,
        city=body.city,
        sector=body.sector,
        udyam=body.udyam,
        category="small"
    )
    db.add(new_msme)

    new_user = User(
        id=f"user_{uuid.uuid4().hex[:8]}",
        msme_id=msme_id,
        username=body.username,
        password_hash=hash_password(body.password),
        role="owner",
        phone_number=body.phone_number
    )
    db.add(new_user)
    db.commit()

    token = create_access_token({"sub": new_user.username, "msme_id": msme_id})
    return {"token": token, "username": new_user.username, "msme_id": msme_id}

@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token = create_access_token({"sub": user.username, "msme_id": user.msme_id, "role": user.role})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "msme_id": user.msme_id
    }

@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msme = db.query(MSME).filter(MSME.id == user.msme_id).first()
    return {
        "username": user.username,
        "role": user.role,
        "phone_number": user.phone_number,
        "msme": msme.to_dict() if msme else None
    }

# --- Core Interaction Endpoints ---
@app.post("/api/chat")
def chat(
    body: ChatIn,
    current_user: Optional[User] = Depends(get_current_user_optional),
    msme_id: str = Depends(resolve_msme_id),
    db: Session = Depends(get_db)
):
    out = orchestrator.chat(body.session_id, body.text, msme_id=msme_id)
    out["pending"] = get_msme_pending(msme_id)

    # Persist chat history in database
    try:
        import json
        msg_user = ChatMessage(
            msme_id=msme_id,
            session_id=body.session_id,
            role="user",
            content=body.text,
            trace_json="[]"
        )
        msg_asst = ChatMessage(
            msme_id=msme_id,
            session_id=body.session_id,
            role="assistant",
            content=out.get("reply", ""),
            trace_json=json.dumps(out.get("trace", []))
        )
        db.add_all([msg_user, msg_asst])
        db.commit()
    except Exception:
        db.rollback()

    return out

@app.post("/api/approve/{pid}")
def approve(
    pid: str,
    ok: bool = True,
    current_user: Optional[User] = Depends(get_current_user_optional),
    msme_id: str = Depends(resolve_msme_id)
):
    if current_user:
        if current_user.role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Only owner or admin may approve")
        if current_user.msme_id != msme_id:
            raise HTTPException(status_code=404, detail="No such pending approval")
    else:
        if not config.DEMO_MODE or msme_id != "demo":
            raise HTTPException(status_code=401, detail="Authentication required")

    appr = get_approval(pid, msme_id=msme_id)
    if not appr or appr.get("status") != "pending":
        raise HTTPException(status_code=404, detail="No such pending approval")

    resolved_by = current_user.username if current_user else "owner"
    action_msme_id = appr.get("msme_id", msme_id)
    if action_msme_id != msme_id:
        raise HTTPException(status_code=404, detail="No such pending approval")

    if not ok:
        update_approval_status(pid, "declined", resolved_by=resolved_by)
        log("Finance Agent", "Owner declined application", consent="human declined", msme_id=action_msme_id)
        return {"status": "declined"}

    update_approval_status(pid, "submitted", resolved_by=resolved_by)
    return finance.execute(appr, msme_id=action_msme_id)

@app.post("/api/inspect")
async def inspect(
    file: UploadFile = File(...),
    msme_id: str = Depends(resolve_msme_id)
):
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Image too large (max {config.MAX_UPLOAD_BYTES // (1024*1024)} MB)")
    try:
        return quality.inspect_image(data, msme_id=msme_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read image")

# --- Specialist Endpoints ---
@app.get("/api/energy/carbon-report-pdf")
def download_carbon_pdf(msme_id: str = Depends(resolve_msme_id)):
    pdf_bytes = energy.generate_pdf(msme_id=msme_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Scope2_Carbon_Report_{msme_id}.pdf"}
    )

@app.post("/api/energy/smart-meter")
async def analyze_smart_meter(
    file: UploadFile = File(...),
    msme_id: str = Depends(resolve_msme_id)
):
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    return energy.analyze_smart_meter_csv(data.decode("utf-8", errors="ignore"), msme_id=msme_id)

@app.post("/api/maintenance/telemetry")
async def analyze_telemetry(
    file: Optional[UploadFile] = File(None),
    machine_id: str = Query("CNC Lathe #2 / 100T Press"),
    msme_id: str = Depends(resolve_msme_id)
):
    content = ""
    if file:
        data = await file.read()
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        content = data.decode("utf-8", errors="ignore")
    return maintenance.analyze_telemetry(content, machine_id=machine_id, msme_id=msme_id)

@app.post("/api/compliance/circular")
def analyze_circular(
    body: CircularIn,
    msme_id: str = Depends(resolve_msme_id)
):
    return compliance.summarize_circular(body.content, title=body.title or "Pasted Circular", msme_id=msme_id)

@app.get("/api/market/buyers")
def get_buyers(
    cluster: Optional[str] = None,
    msme_id: str = Depends(resolve_msme_id)
):
    return market.find_buyers(cluster=cluster, msme_id=msme_id)

@app.post("/api/market/listing")
def draft_market_listing(
    body: MarketListingIn,
    msme_id: str = Depends(resolve_msme_id)
):
    return market.draft_listing(
        product_name=body.product_name,
        price_inr=body.price_inr,
        moq=body.moq,
        hsn_code=body.hsn_code,
        lead_time_days=body.lead_time_days,
        msme_id=msme_id
    )

@app.get("/api/wellness/info")
def get_wellness_info(
    operation: Optional[str] = None,
    msme_id: str = Depends(resolve_msme_id)
):
    return {
        "reminders": wellness.get_reminders(operation, msme_id=msme_id),
        "facilities": wellness.find_healthcare(msme_id=msme_id),
        "summary_hi": wellness.summary_hi(operation or "shopfloor")
    }

@app.get("/api/supply-chain/forecast")
def get_supply_chain_forecast(
    growth: float = Query(15.0),
    msme_id: str = Depends(resolve_msme_id)
):
    return supply_chain.forecast_raw_materials(orders_growth_pct=growth, msme_id=msme_id)

# --- DPI Adapter Endpoints (Consent Required) ---
@app.post("/api/dpi/aa/consent")
def dpi_aa_consent(body: AAConsentIn, msme_id: str = Depends(resolve_msme_id)):
    aa = get_adapter("account_aggregator")
    return aa.request_consent(customer_vpa=body.customer_vpa, purpose=body.purpose, msme_id=msme_id)

@app.get("/api/dpi/aa/financials")
def dpi_aa_financials(consent_handle: str = "HANDLE_DEMO", msme_id: str = Depends(resolve_msme_id)):
    aa = get_adapter("account_aggregator")
    return aa.fetch_financial_data(consent_handle=consent_handle, msme_id=msme_id)

@app.get("/api/dpi/gst/status")
def dpi_gst_status(gstin: Optional[str] = None, msme_id: str = Depends(resolve_msme_id)):
    gst = get_adapter("gst")
    return gst.get_filing_status(gstin=gstin, msme_id=msme_id)

@app.post("/api/dpi/gst/eway-bill")
def dpi_gst_eway_bill(body: EwayBillIn, msme_id: str = Depends(resolve_msme_id)):
    gst = get_adapter("gst")
    return gst.generate_eway_bill(
        invoice_number=body.invoice_number,
        to_gstin=body.to_gstin,
        consignee_pincode=body.consignee_pincode,
        vehicle_number=body.vehicle_number,
        value_inr=body.value_inr,
        msme_id=msme_id
    )

@app.get("/api/dpi/digilocker/document")
def dpi_digilocker(doc_type: str = "UDYAM", msme_id: str = Depends(resolve_msme_id)):
    dl = get_adapter("digilocker")
    return dl.pull_document(doc_type=doc_type, msme_id=msme_id)

@app.get("/api/dpi/udyam/verify")
def dpi_udyam(udyam_number: Optional[str] = None, msme_id: str = Depends(resolve_msme_id)):
    ud = get_adapter("udyam")
    return ud.verify_registration(udyam_number=udyam_number, msme_id=msme_id)

@app.post("/api/dpi/einvoicing/irn")
def dpi_einvoicing(body: EInvoicingIn, msme_id: str = Depends(resolve_msme_id)):
    ei = get_adapter("einvoicing")
    return ei.generate_irn(
        invoice_number=body.invoice_number,
        buyer_gstin=body.buyer_gstin,
        total_amount_inr=body.total_amount_inr,
        tax_amount_inr=body.tax_amount_inr,
        msme_id=msme_id
    )

@app.post("/api/dpi/upi/payment-link")
def dpi_upi(body: UPIPaymentIn, msme_id: str = Depends(resolve_msme_id)):
    up = get_adapter("upi")
    return up.create_invoice_payment_link(
        invoice_id=body.invoice_id,
        amount_inr=body.amount_inr,
        note=body.note,
        msme_id=msme_id
    )

@app.get("/api/dpi/ulip/track")
def dpi_ulip(vehicle_number: str = "MP-09-GH-8219", msme_id: str = Depends(resolve_msme_id)):
    ul = get_adapter("ulip")
    return ul.track_consignment(vehicle_number=vehicle_number, msme_id=msme_id)

@app.post("/api/dpi/treds/discount")
def dpi_treds(body: TReDSIn, msme_id: str = Depends(resolve_msme_id)):
    tr = get_adapter("treds")
    return tr.upload_invoice_for_discounting(
        invoice_number=body.invoice_number,
        buyer_name=body.buyer_name,
        buyer_gstin=body.buyer_gstin,
        amount_rs=body.amount_rs,
        due_days=body.due_days,
        msme_id=msme_id
    )

# --- Channels: WhatsApp Webhook & Voice Processing ---
@app.get("/api/webhook/whatsapp")
def verify_whatsapp(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    challenge = verify_meta_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@app.post("/api/webhook/whatsapp")
async def inbound_whatsapp(
    request: Request
):
    content_type = request.headers.get("content-type", "")
    payload = {}
    raw_media = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = dict(form)
        upload = form.get("file")
        if upload and hasattr(upload, "read"):
            raw_media = await upload.read()
    elif "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    elif "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        payload = dict(form)

    return process_inbound_whatsapp(payload, raw_media=raw_media)

@app.post("/api/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    source_lang: str = Query("hi"),
    msme_id: str = Depends(resolve_msme_id)
):
    data = await file.read()
    return voice_adapter.transcribe(data, source_lang=source_lang, msme_id=msme_id)

@app.post("/api/voice/synthesize")
def voice_synthesize(
    text: str = Query(...),
    target_lang: str = Query("hi"),
    msme_id: str = Depends(resolve_msme_id)
):
    return voice_adapter.synthesize(text, target_lang=target_lang, msme_id=msme_id)

# --- Dashboards: Owner & District Official Cluster View ---
@app.get("/api/dashboard/owner")
def dashboard_owner(
    msme_id: str = Depends(resolve_msme_id),
    db: Session = Depends(get_db)
):
    return get_owner_dashboard(msme_id=msme_id, db=db)

@app.get("/api/dashboard/cluster")
def dashboard_cluster(
    cluster: str = Query("Pithampur Auto Cluster"),
    official: Optional[User] = Depends(require_official_role),
    db: Session = Depends(get_db)
):
    return get_cluster_dashboard(cluster_name=cluster, db=db)

@app.get("/dashboard")
def view_owner_dashboard():
    return FileResponse(FRONT / "dashboard.html")

@app.get("/cluster")
def view_cluster_dashboard():
    return FileResponse(FRONT / "cluster.html")

@app.get("/api/state")
def state(msme_id: str = Depends(resolve_msme_id)):
    return {
        "demo_mode": config.DEMO_MODE,
        "profile": get_msme_profile(msme_id),
        "kpi": get_msme_kpi(msme_id),
        "audit": get_msme_audit(msme_id, limit=30),
        "pending": get_msme_pending(msme_id)
    }

@app.get("/")
def index():
    return FileResponse(FRONT / "index.html")

app.mount("/static", StaticFiles(directory=FRONT), name="static")
