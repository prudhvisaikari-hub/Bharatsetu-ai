import datetime as dt
import json
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class MSME(Base):
    __tablename__ = "msmes"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    city = Column(String(128), default="Pithampur, Indore")
    sector = Column(String(128), default="auto components")
    udyam = Column(String(64), unique=True, nullable=False)
    category = Column(String(32), default="small")
    cluster = Column(String(64), default="Pithampur Auto Cluster")
    
    monthly_kwh = Column(Float, default=18400.0)
    tariff_rs_kwh = Column(Float, default=7.2)
    peak_tariff = Column(Float, default=8.5)
    offpeak_tariff = Column(Float, default=6.2)
    grid_factor_tco2_mwh = Column(Float, default=0.71)
    
    monthly_revenue_rs = Column(Float, default=4200000.0)
    overdue_receivables_rs = Column(Float, default=680000.0)
    overdue_days = Column(Integer, default=47)
    rejection_rate_pct = Column(Float, default=4.1)
    scrap_cost_rs = Column(Float, default=110000.0)
    power_cost_rise_pct = Column(Float, default=14.0)
    load_kw_json = Column(Text, default="[]")
    
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    users = relationship("User", back_populates="msme", cascade="all, delete-orphan")
    audits = relationship("AuditLog", back_populates="msme", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="msme", cascade="all, delete-orphan")
    kpi = relationship("KPI", back_populates="msme", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "sector": self.sector,
            "udyam": self.udyam,
            "category": self.category,
            "cluster": self.cluster,
            "monthly_kwh": self.monthly_kwh,
            "tariff_rs_kwh": self.tariff_rs_kwh,
            "peak_tariff": self.peak_tariff,
            "offpeak_tariff": self.offpeak_tariff,
            "grid_factor_tco2_mwh": self.grid_factor_tco2_mwh,
            "monthly_revenue_rs": self.monthly_revenue_rs,
            "overdue_receivables_rs": self.overdue_receivables_rs,
            "overdue_days": self.overdue_days,
            "rejection_rate_pct": self.rejection_rate_pct,
            "scrap_cost_rs": self.scrap_cost_rs,
            "power_cost_rise_pct": self.power_cost_rise_pct,
            "load_kw": json.loads(self.load_kw_json or "[]")
        }


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    msme_id = Column(String(36), ForeignKey("msmes.id"), nullable=False)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="owner")  # "owner", "official", "worker"
    phone_number = Column(String(32), default="")
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))

    msme = relationship("MSME", back_populates="users")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msme_id = Column(String(36), ForeignKey("msmes.id"), nullable=False)
    timestamp = Column(String(32), nullable=False)
    agent = Column(String(64), nullable=False)
    action = Column(Text, nullable=False)
    consent = Column(String(128), default="consent logged")
    details_json = Column(Text, default="{}")

    msme = relationship("MSME", back_populates="audits")

    def to_dict(self):
        return {
            "id": self.id,
            "t": self.timestamp,
            "agent": self.agent,
            "action": self.action,
            "consent": self.consent,
            "details": json.loads(self.details_json or "{}")
        }


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True)
    msme_id = Column(String(36), ForeignKey("msmes.id"), nullable=False)
    kind = Column(String(64), nullable=False)
    payload_json = Column(Text, nullable=False)
    status = Column(String(32), default="pending")  # "pending", "submitted", "declined"
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(64), nullable=True)

    msme = relationship("MSME", back_populates="approvals")

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind,
            "payload": json.loads(self.payload_json or "{}"),
            "status": self.status
        }


class KPI(Base):
    __tablename__ = "kpis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msme_id = Column(String(36), ForeignKey("msmes.id"), unique=True, nullable=False)
    rs_saved_per_year = Column(Float, default=0.0)
    kwh_cut_per_month = Column(Float, default=0.0)
    hours_saved = Column(Float, default=0.0)
    seen_keys_json = Column(Text, default="[]")
    updated_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc), onupdate=lambda: dt.datetime.now(dt.timezone.utc))

    msme = relationship("MSME", back_populates="kpi")

    def to_dict(self):
        return {
            "rs_saved_per_year": self.rs_saved_per_year,
            "kwh_cut_per_month": self.kwh_cut_per_month,
            "hours_saved": self.hours_saved
        }


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msme_id = Column(String(36), ForeignKey("msmes.id"), nullable=False)
    session_id = Column(String(64), nullable=False)
    role = Column(String(16), nullable=False)  # "user", "assistant"
    content = Column(Text, nullable=False)
    trace_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: dt.datetime.now(dt.timezone.utc))


class WhatsAppLink(Base):
    __tablename__ = "whatsapp_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_hash = Column(String(128), unique=True, nullable=False, index=True)
    msme_id = Column(String(36), ForeignKey("msmes.id"), nullable=False)
    verified_at = Column(DateTime, nullable=True)
    otp_code = Column(String(32), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)

    msme = relationship("MSME")

    def to_dict(self):
        return {
            "id": self.id,
            "phone_hash": self.phone_hash,
            "msme_id": self.msme_id,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None
        }


class WhatsAppLinkThrottle(Base):
    __tablename__ = "whatsapp_link_throttles"

    phone_hash = Column(String(128), primary_key=True, index=True)
    failed_count = Column(Integer, default=0, nullable=False)
    first_failed_at = Column(DateTime, nullable=True)
    locked_until = Column(DateTime, nullable=True)

