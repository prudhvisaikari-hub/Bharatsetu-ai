"""Finance Agent: Account Aggregator bank analytics, working-capital loan drafting (human-in-the-loop),
and TReDS trade receivables discounting.
"""
from ..store import PROFILE as P, log, gain, new_approval, get_msme_profile
from ..dpi import get_adapter

def aa_summary(msme_id="demo"):
    aa = get_adapter("account_aggregator")
    fin = aa.fetch_financial_data("AUTO_CONSENT", msme_id=msme_id)
    profile = get_msme_profile(msme_id)
    return {
        "monthly_revenue_rs": profile.get("monthly_revenue_rs", P["monthly_revenue_rs"]),
        "overdue_receivables_rs": profile.get("overdue_receivables_rs", P["overdue_receivables_rs"]),
        "overdue_days": profile.get("overdue_days", P["overdue_days"]),
        "suggested_limit_rs": 1500000,
        "aa_status": fin.get("status"),
        "accounts": fin.get("accounts", [])
    }

def draft_loan(amount_rs=1500000, msme_id="demo"):
    """Never submits. Creates a pending approval the owner must confirm (human in the loop)."""
    pid = new_approval("working_capital_loan", {"amount_rs": amount_rs}, msme_id=msme_id)
    log("Finance Agent", f"Drafted Rs {amount_rs:,} working-capital application, awaiting owner", "human approval pending", msme_id=msme_id)
    return {"status": "pending_owner_approval", "approval_id": pid, "amount_rs": amount_rs}

def execute(pending, msme_id="demo"):
    gain("apply", 0, 0, 3, msme_id=msme_id)
    log("Finance Agent", f"Submitted Rs {pending['payload']['amount_rs']:,} application (simulated)", "human approved", msme_id=msme_id)
    return {"status": "submitted", "eta_hours": 48}

def discount_receivables_treds(
    invoice_number: str = "INV-2026-089",
    buyer_name: str = "VE Commercial Vehicles Ltd",
    buyer_gstin: str = "23AABCV1290K1Z9",
    amount_rs: float = 680000.0,
    due_days: int = 47,
    msme_id: str = "demo"
):
    """Facilitates invoice factoring via TReDS (M1xchange / RXIL)."""
    treds = get_adapter("treds")
    res = treds.upload_invoice_for_discounting(
        invoice_number=invoice_number,
        buyer_name=buyer_name,
        buyer_gstin=buyer_gstin,
        amount_rs=amount_rs,
        due_days=due_days,
        msme_id=msme_id
    )
    gain("treds_discounting", rs=45000, hrs=5.0, msme_id=msme_id)
    return res
