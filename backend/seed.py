"""Demo Data Seeder for BharatSetu AI.
Resets and populates the database with Sharma Auto Components (Pithampur),
demo credentials, sample audit logs, DPI consent records, and cluster MSMEs.
"""
import json
import os
import sys
import secrets
import uuid
import datetime as dt
from pathlib import Path
from . import config
from .db.database import engine, Base, SessionLocal
from .db.models import MSME, User, AuditLog, Approval, KPI, ChatMessage, WhatsAppLink
from .channels.whatsapp import hash_phone
from .auth import hash_password

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_PROFILE = json.loads((DATA_DIR / "profile.json").read_text())

def seed_database(reset: bool = True, force: bool = False):
    if not config.DEMO_MODE and not force:
        print("❌ Seeding aborted: DEMO_MODE is False. Run with --force or set DEMO_MODE=true to seed demo data.")
        return False

    print("🌱 Initializing BharatSetu AI database...")
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    owner_password = os.getenv("SEED_OWNER_PASSWORD")
    if not owner_password:
        owner_password = secrets.token_urlsafe(12)
        print(f"🔑 Generated random owner password for seeded demo account: {owner_password}")
    else:
        print("🔑 Using SEED_OWNER_PASSWORD from environment.")

    db = SessionLocal()
    try:
        # 1. Primary MSME: Sharma Auto Components (Pithampur)
        demo = MSME(
            id="demo",
            name=RAW_PROFILE.get("name", "Sharma Auto Components"),
            city="Pithampur, Indore",
            sector="auto components",
            udyam="UDYAM-MP-23-0012345",
            category="small",
            cluster="Pithampur Auto Cluster",
            monthly_kwh=18400.0,
            tariff_rs_kwh=7.2,
            peak_tariff=8.5,
            offpeak_tariff=6.2,
            grid_factor_tco2_mwh=0.71,
            monthly_revenue_rs=4200000.0,
            overdue_receivables_rs=680000.0,
            overdue_days=47,
            rejection_rate_pct=3.6,
            scrap_cost_rs=88000.0,
            power_cost_rise_pct=14.0,
            load_kw_json=json.dumps(RAW_PROFILE.get("load_kw", [30, 45, 60, 80, 92, 56]))
        )
        db.add(demo)

        # 2. Demo User: owner
        owner = User(
            id="user_owner_demo",
            msme_id="demo",
            username="owner",
            password_hash=hash_password(owner_password),
            role="owner",
            phone_number="+919876543210"
        )
        db.add(owner)

        # 3. KPI Baseline
        kpi = KPI(
            msme_id="demo",
            rs_saved_per_year=549360.0,
            kwh_cut_per_month=5400.0,
            hours_saved=18.5,
            seen_keys_json=json.dumps(["energy", "scheme", "qa", "comply", "market"])
        )
        db.add(kpi)

        # 3b. Seed Verified WhatsApp link for demo phone +919876543210
        demo_wa = WhatsAppLink(
            phone_hash=hash_phone("+919876543210"),
            msme_id="demo",
            verified_at=dt.datetime.now(dt.timezone.utc)
        )
        db.add(demo_wa)

        # 4. Pending Approval: Rs 15,00,000 Working Capital Loan (Human-in-the-loop ready)
        pending_loan = Approval(
            id="appr_loan_01",
            msme_id="demo",
            kind="working_capital_loan",
            payload_json=json.dumps({"amount_rs": 1500000, "lender": "State Bank of India", "interest_rate_pct": 8.75}),
            status="pending"
        )
        db.add(pending_loan)

        # 5. Sample Audit Log & DPI Consent Trail
        t_now = dt.datetime.now()
        audits = [
            ("DPI:AccountAggregator", "Acquired user consent for Working Capital Credit Assessment", "Consent ID: CONSENT-ACC-9821 [Exp: 2027-01-01]"),
            ("Energy Agent", "Built monthly Scope 2 carbon report from smart-meter feed", "Consent verified: Location-based accounting"),
            ("Quality Agent", "Inspected machined flange batch via YOLOv8 (0 defects detected)", "Shopfloor verified: PASS"),
            ("Market Agent", "Found 4 matching Tier-1 buyers on ONDC/GeM in Pithampur cluster", "Consent verified: ONDC Beckn Gateway"),
            ("Finance Agent", "Drafted Rs 15,00,000 working-capital application, awaiting owner approval", "Human approval pending")
        ]
        for idx, (ag, act, con) in enumerate(audits):
            time_str = (t_now - dt.timedelta(minutes=15 * (len(audits) - idx))).strftime("%H:%M:%S")
            db.add(AuditLog(
                msme_id="demo",
                timestamp=time_str,
                agent=ag,
                action=act,
                consent=con,
                details_json="{}"
            ))

        # 6. Additional Cluster MSMEs (Pithampur Auto Cluster: 6 units >= 5 threshold)
        pithampur_cohort = [
            ("msme_pith_02", "Malwa Precision Gears", "UDYAM-MP-23-0020002", 3800000.0, 16200.0, 3.4),
            ("msme_pith_03", "Narmada Forgings Pvt Ltd", "UDYAM-MP-23-0020003", 5600000.0, 24500.0, 4.2),
            ("msme_pith_04", "Indore Auto Stampings", "UDYAM-MP-23-0020004", 4100000.0, 19100.0, 3.9),
            ("msme_pith_05", "Dhar Fasteners LLP", "UDYAM-MP-23-0020005", 2900000.0, 12800.0, 2.8),
            ("msme_pith_06", "Avantika Heat Treaters", "UDYAM-MP-23-0020006", 4700000.0, 28000.0, 4.6),
        ]
        for uid, uname, udy, rev, kwh, rej in pithampur_cohort:
            db.add(MSME(
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
            ))

        # 7. Palda Cluster MSMEs (2 units < 5 threshold for privacy suppression demo)
        palda_cohort = [
            ("msme_palda_01", "Palda Agro Processors", "UDYAM-MP-23-0030001", 3100000.0, 14000.0, 2.5),
            ("msme_palda_02", "Kshipra Food Packagers", "UDYAM-MP-23-0030002", 2400000.0, 11500.0, 3.1)
        ]
        for uid, uname, udy, rev, kwh, rej in palda_cohort:
            db.add(MSME(
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
            ))

        db.commit()
        print("✅ Database successfully seeded with demo profile, owner credentials, and cluster cohorts.")
    finally:
        db.close()

if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    seed_database(force=force_flag)
