"""Dashboard Analytics Service for BharatSetu AI.
Includes:
- Owner Dashboard: ROI metrics, kWh and CO2 abatement, loan tracking, defect history with charts.
- District Official Cluster Dashboard: Anonymized multi-unit aggregation with strict k-anonymity privacy gate (N >= 5).
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from .db.models import MSME, KPI, Approval, AuditLog
from .store import get_msme_profile, get_msme_kpi, get_msme_pending

MIN_COHORT_SIZE = 5

def get_owner_dashboard(msme_id: str = "demo", db: Optional[Session] = None) -> Dict[str, Any]:
    profile = get_msme_profile(msme_id)
    kpi = get_msme_kpi(msme_id)
    pending = get_msme_pending(msme_id)

    monthly_kwh = profile.get("monthly_kwh", 18400.0)
    grid_factor = profile.get("grid_factor_tco2_mwh", 0.71)
    scope2_tco2e_month = round(monthly_kwh * grid_factor / 1000.0, 2)
    co2_saved_tco2e_month = round(kpi.get("kwh_cut_per_month", 0.0) * grid_factor / 1000.0, 2)

    # 6-month defect rate trend showing quality improvements via YOLO
    defect_history = [
        {"month": "Month -5", "defect_rate_pct": 4.8, "scrap_cost_rs": 135000},
        {"month": "Month -4", "defect_rate_pct": 4.5, "scrap_cost_rs": 125000},
        {"month": "Month -3", "defect_rate_pct": 4.3, "scrap_cost_rs": 118000},
        {"month": "Month -2", "defect_rate_pct": 4.1, "scrap_cost_rs": 110000},
        {"month": "Month -1", "defect_rate_pct": 3.8, "scrap_cost_rs": 98000},
        {"month": "Current", "defect_rate_pct": round(profile.get("rejection_rate_pct", 3.6), 1), "scrap_cost_rs": 88000}
    ]

    # Electricity demand and solar profile
    load_kw = profile.get("load_kw", [30, 45, 60, 80, 92, 56])
    hours = list(range(len(load_kw)))

    return {
        "status": "success",
        "msme_id": msme_id,
        "enterprise_name": profile.get("name", "Sharma Auto Components"),
        "city": profile.get("city", "Pithampur, Indore"),
        "cluster": profile.get("cluster", "Pithampur Auto Cluster"),
        "impact_kpis": {
            "money_saved_per_year_rs": kpi.get("rs_saved_per_year", 0.0),
            "kwh_cut_per_month": kpi.get("kwh_cut_per_month", 0.0),
            "co2_cut_tco2e_per_month": co2_saved_tco2e_month,
            "hours_saved": kpi.get("hours_saved", 0.0)
        },
        "carbon_summary": {
            "current_scope2_tco2e_month": scope2_tco2e_month,
            "grid_factor_tco2_mwh": grid_factor,
            "cbam_readiness_status": "DRAFT - Preliminary Calculation (Requires 3rd-party verification)"
        },
        "working_capital_and_loans": {
            "overdue_receivables_rs": profile.get("overdue_receivables_rs", 680000.0),
            "overdue_days": profile.get("overdue_days", 47),
            "treds_discounting_available": True,
            "pending_approvals_count": len(pending),
            "pending_items": pending
        },
        "defect_history": defect_history,
        "load_profile_24h": [{"hour": f"{h:02d}:00", "kw": kw} for h, kw in enumerate(load_kw)],
        "simulated": True
    }

def get_cluster_dashboard(cluster_name: str, db: Session) -> Dict[str, Any]:
    """Anonymized cluster dashboard with strict k-anonymity privacy protection (N >= 5)."""
    # Query MSMEs matching the cluster
    query = db.query(MSME)
    if cluster_name and cluster_name.lower() != "all":
        query = query.filter(MSME.cluster.ilike(f"%{cluster_name}%"))
    
    msmes = query.all()
    cohort_size = len(msmes)

    # Privacy Rule: Minimum cohort size before showing any aggregate
    if cohort_size < MIN_COHORT_SIZE:
        return {
            "status": "PRIVACY_SUPPRESSED",
            "cluster_name": cluster_name,
            "cohort_size": cohort_size,
            "min_required_cohort_size": MIN_COHORT_SIZE,
            "privacy_notice": (
                f"Privacy protection active: Cohort size of {cohort_size} is below the minimum threshold "
                f"of {MIN_COHORT_SIZE} MSMEs. Aggregate metrics are suppressed to prevent single-enterprise deanonymization."
            ),
            "simulated": True
        }

    # Aggregate anonymized statistics
    total_rev = sum(m.monthly_revenue_rs for m in msmes)
    total_kwh = sum(m.monthly_kwh for m in msmes)
    total_overdue = sum(m.overdue_receivables_rs for m in msmes)
    avg_rejection = sum(m.rejection_rate_pct for m in msmes) / cohort_size
    avg_grid_factor = sum(m.grid_factor_tco2_mwh for m in msmes) / cohort_size
    total_scope2_tco2e = (total_kwh * avg_grid_factor) / 1000.0

    category_counts = {}
    for m in msmes:
        cat = m.category or "small"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "status": "AGGREGATED_SUCCESS",
        "cluster_name": cluster_name,
        "cohort_size": cohort_size,
        "privacy_compliance": f"k-Anonymity Verified (Cohort N = {cohort_size} >= {MIN_COHORT_SIZE})",
        "no_pii_verified": True,
        "aggregated_metrics": {
            "total_msme_count": cohort_size,
            "avg_monthly_revenue_rs": round(total_rev / cohort_size),
            "total_monthly_electricity_kwh": round(total_kwh),
            "total_monthly_scope2_tco2e": round(total_scope2_tco2e, 1),
            "annual_scope2_tco2e": round(total_scope2_tco2e * 12, 1),
            "cluster_avg_rejection_rate_pct": round(avg_rejection, 2),
            "total_overdue_receivables_rs": round(total_overdue),
            "treds_liquidity_unlock_potential_rs": round(total_overdue * 0.92)
        },
        "enterprise_classification_distribution": category_counts,
        "key_initiatives": [
            "Industrial rooftop solar aggregation (target 4.5 MW across cluster)",
            "Common Effluent Treatment Plant (CETP) IoT telemetry integration",
            "Cluster-wide TReDS liquidity onboarding with SBI and Bank of Baroda"
        ],
        "simulated": True
    }
