"""SQLAlchemy-backed persistence for BharatSetu AI (SQLite / PostgreSQL ready).
Maintains backwards-compatible PROFILE, AUDIT, PENDING, KPI exports while providing
per-MSME data isolation, audit logging, consent tracking, and approval lifecycle.
"""
import json
import time
import uuid
import datetime as dt
from pathlib import Path
from typing import Optional, Dict, Any, List
from . import config
from .db.database import engine, Base, SessionLocal
from .db.models import MSME as MSMEModel, User as UserModel, AuditLog as AuditLogModel, Approval as ApprovalModel, KPI as KPIModel, ChatMessage as ChatMessageModel

DATA_DIR = Path(__file__).parent / "data"
RAW_PROFILE = json.loads((DATA_DIR / "profile.json").read_text())
SCHEMES = json.loads((DATA_DIR / "schemes.json").read_text())

# Create all tables on module load
Base.metadata.create_all(bind=engine)

def seed_default_data():
    if not config.DEMO_MODE:
        return
    db = SessionLocal()
    try:
        demo = db.query(MSMEModel).filter(MSMEModel.id == "demo").first()
        if not demo:
            demo = MSMEModel(
                id="demo",
                name=RAW_PROFILE.get("name", "Sharma Auto Components"),
                city=RAW_PROFILE.get("city", "Pithampur, Indore"),
                sector=RAW_PROFILE.get("sector", "auto components"),
                udyam=RAW_PROFILE.get("udyam", "UDYAM-MP-23-0012345"),
                category=RAW_PROFILE.get("category", "small"),
                cluster=RAW_PROFILE.get("cluster", "Pithampur Auto Cluster"),
                monthly_kwh=RAW_PROFILE.get("monthly_kwh", 18400.0),
                tariff_rs_kwh=RAW_PROFILE.get("tariff_rs_kwh", 7.2),
                peak_tariff=RAW_PROFILE.get("peak_tariff", 8.5),
                offpeak_tariff=RAW_PROFILE.get("offpeak_tariff", 6.2),
                grid_factor_tco2_mwh=RAW_PROFILE.get("grid_factor_tco2_mwh", 0.71),
                monthly_revenue_rs=RAW_PROFILE.get("monthly_revenue_rs", 4200000.0),
                overdue_receivables_rs=RAW_PROFILE.get("overdue_receivables_rs", 680000.0),
                overdue_days=RAW_PROFILE.get("overdue_days", 47),
                rejection_rate_pct=RAW_PROFILE.get("rejection_rate_pct", 4.1),
                scrap_cost_rs=RAW_PROFILE.get("scrap_cost_rs", 110000.0),
                power_cost_rise_pct=RAW_PROFILE.get("power_cost_rise_pct", 14.0),
                load_kw_json=json.dumps(RAW_PROFILE.get("load_kw", []))
            )
            db.add(demo)

            # Seed default demo owner user
            from .auth import hash_password
            user = UserModel(
                id="user_demo",
                msme_id="demo",
                username="owner",
                password_hash=hash_password("setu123"),
                role="owner",
                phone_number="+919876543210"
            )
            db.add(user)

            # Seed default KPI record
            kpi = KPIModel(
                msme_id="demo",
                rs_saved_per_year=0.0,
                kwh_cut_per_month=0.0,
                hours_saved=0.0,
                seen_keys_json="[]"
            )
            db.add(kpi)

            # Additional Pithampur Auto Cluster MSMEs (to achieve cohort >= 5 for privacy-compliant aggregation)
            pithampur_units = [
                ("msme_pith_02", "Malwa Precision Gears", "UDYAM-MP-23-0020002", 3800000.0, 16200.0, 3.4),
                ("msme_pith_03", "Narmada Forgings Pvt Ltd", "UDYAM-MP-23-0020003", 5600000.0, 24500.0, 4.2),
                ("msme_pith_04", "Indore Auto Stampings", "UDYAM-MP-23-0020004", 4100000.0, 19100.0, 3.9),
                ("msme_pith_05", "Dhar Fasteners LLP", "UDYAM-MP-23-0020005", 2900000.0, 12800.0, 2.8),
                ("msme_pith_06", "Avantika Heat Treaters", "UDYAM-MP-23-0020006", 4700000.0, 28000.0, 4.6),
            ]
            for uid, uname, udy, rev, kwh, rej in pithampur_units:
                m = MSMEModel(
                    id=uid,
                    name=uname,
                    city="Pithampur",
                    sector="auto components",
                    udyam=udy,
                    category="small",
                    cluster="Pithampur Auto Cluster",
                    monthly_revenue_rs=rev,
                    monthly_kwh=kwh,
                    rejection_rate_pct=rej,
                    overdue_receivables_rs=round(rev * 0.16),
                    grid_factor_tco2_mwh=0.71
                )
                db.add(m)

            # Palda Cluster MSMEs (cohort = 2 < 5 to demonstrate privacy suppression rule)
            palda_units = [
                ("msme_palda_01", "Palda Agro Processors", "UDYAM-MP-23-0030001", 3100000.0, 14000.0, 2.5),
                ("msme_palda_02", "Kshipra Food Packagers", "UDYAM-MP-23-0030002", 2400000.0, 11500.0, 3.1)
            ]
            for uid, uname, udy, rev, kwh, rej in palda_units:
                m = MSMEModel(
                    id=uid,
                    name=uname,
                    city="Palda, Indore",
                    sector="food processing",
                    udyam=udy,
                    category="micro",
                    cluster="Palda Food & Engineering Cluster",
                    monthly_revenue_rs=rev,
                    monthly_kwh=kwh,
                    rejection_rate_pct=rej,
                    overdue_receivables_rs=round(rev * 0.12),
                    grid_factor_tco2_mwh=0.71
                )
                db.add(m)

            db.commit()
    finally:
        db.close()

seed_default_data()

# In-memory mirrors for backward compatibility
PROFILE = RAW_PROFILE.copy()
AUDIT: List[Dict[str, Any]] = []
PENDING: Dict[str, Dict[str, Any]] = {}
KPI_DICT: Dict[str, float] = {"rs_saved_per_year": 0.0, "kwh_cut_per_month": 0.0, "hours_saved": 0.0}
_seen = set()

def reload_state(msme_id: str = "demo"):
    """Reloads in-memory mirrors from database for given MSME."""
    global AUDIT, PENDING, KPI_DICT, _seen, PROFILE
    db = SessionLocal()
    try:
        m = db.query(MSMEModel).filter(MSMEModel.id == msme_id).first()
        if m:
            PROFILE.update(m.to_dict())

        audits = db.query(AuditLogModel).filter(AuditLogModel.msme_id == msme_id).order_by(AuditLogModel.id.desc()).limit(50).all()
        AUDIT.clear()
        for a in audits:
            AUDIT.append(a.to_dict())

        pends = db.query(ApprovalModel).filter(ApprovalModel.msme_id == msme_id, ApprovalModel.status == "pending").all()
        PENDING.clear()
        for p in pends:
            PENDING[p.id] = p.to_dict()

        k = db.query(KPIModel).filter(KPIModel.msme_id == msme_id).first()
        if k:
            KPI_DICT["rs_saved_per_year"] = k.rs_saved_per_year
            KPI_DICT["kwh_cut_per_month"] = k.kwh_cut_per_month
            KPI_DICT["hours_saved"] = k.hours_saved
            try:
                _seen = set(json.loads(k.seen_keys_json or "[]"))
            except Exception:
                _seen = set()
    finally:
        db.close()

reload_state("demo")

# Backward compatibility alias
KPI = KPI_DICT

def log(agent: str, action: str, consent: str = "consent logged", details: Optional[Dict[str, Any]] = None, msme_id: str = "demo"):
    t = time.strftime("%H:%M:%S")
    entry = {"t": t, "agent": agent, "action": action, "consent": consent, "details": details or {}}
    AUDIT.insert(0, entry)
    
    db = SessionLocal()
    try:
        audit_row = AuditLogModel(
            msme_id=msme_id,
            timestamp=t,
            agent=agent,
            action=action,
            consent=consent,
            details_json=json.dumps(details or {})
        )
        db.add(audit_row)
        db.commit()
    finally:
        db.close()

def gain(key: str, rs: float = 0.0, kwh: float = 0.0, hrs: float = 0.0, msme_id: str = "demo"):
    """Count each benefit once so repeated questions don't inflate the dashboard."""
    if key in _seen:
        return
    _seen.add(key)
    KPI_DICT["rs_saved_per_year"] += rs
    KPI_DICT["kwh_cut_per_month"] += kwh
    KPI_DICT["hours_saved"] += hrs

    db = SessionLocal()
    try:
        k = db.query(KPIModel).filter(KPIModel.msme_id == msme_id).first()
        if not k:
            k = KPIModel(msme_id=msme_id, rs_saved_per_year=rs, kwh_cut_per_month=kwh, hours_saved=hrs, seen_keys_json=json.dumps(list(_seen)))
            db.add(k)
        else:
            k.rs_saved_per_year += rs
            k.kwh_cut_per_month += kwh
            k.hours_saved += hrs
            k.seen_keys_json = json.dumps(list(_seen))
        db.commit()
    finally:
        db.close()

import secrets

def new_approval(kind: str, payload: dict, msme_id: str = "demo") -> str:
    pid = secrets.token_urlsafe(16)
    item = {"id": pid, "kind": kind, "payload": payload, "status": "pending"}
    PENDING[pid] = item

    db = SessionLocal()
    try:
        appr = ApprovalModel(
            id=pid,
            msme_id=msme_id,
            kind=kind,
            payload_json=json.dumps(payload),
            status="pending"
        )
        db.add(appr)
        db.commit()
    finally:
        db.close()
    return pid

def get_approval(pid: str, msme_id: Optional[str] = None):
    db = SessionLocal()
    try:
        q = db.query(ApprovalModel).filter(ApprovalModel.id == pid)
        if msme_id:
            q = q.filter(ApprovalModel.msme_id == msme_id)
        appr = q.first()
        return appr.to_dict() if appr else None
    finally:
        db.close()

def update_approval_status(pid: str, status: str, resolved_by: Optional[str] = None):
    PENDING.pop(pid, None)
    db = SessionLocal()
    try:
        appr = db.query(ApprovalModel).filter(ApprovalModel.id == pid).first()
        if appr:
            appr.status = status
            appr.resolved_by = resolved_by
            appr.resolved_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
    finally:
        db.close()

def get_msme_profile(msme_id: str = "demo") -> dict:
    db = SessionLocal()
    try:
        m = db.query(MSMEModel).filter(MSMEModel.id == msme_id).first()
        return m.to_dict() if m else PROFILE
    finally:
        db.close()

def get_msme_kpi(msme_id: str = "demo") -> dict:
    db = SessionLocal()
    try:
        k = db.query(KPIModel).filter(KPIModel.msme_id == msme_id).first()
        return k.to_dict() if k else KPI_DICT
    finally:
        db.close()

def get_msme_audit(msme_id: str = "demo", limit: int = 30) -> list:
    db = SessionLocal()
    try:
        audits = db.query(AuditLogModel).filter(AuditLogModel.msme_id == msme_id).order_by(AuditLogModel.id.desc()).limit(limit).all()
        return [a.to_dict() for a in audits]
    finally:
        db.close()

def get_msme_pending(msme_id: str = "demo") -> list:
    db = SessionLocal()
    try:
        pends = db.query(ApprovalModel).filter(ApprovalModel.msme_id == msme_id, ApprovalModel.status == "pending").all()
        return [p.to_dict() for p in pends]
    finally:
        db.close()
