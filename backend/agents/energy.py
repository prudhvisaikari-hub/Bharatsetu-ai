"""Energy Agent: Scope 2 CBAM carbon footprinting, smart-meter interval load analysis,
Time-of-Day (ToD) tariff load shifting, rooftop solar sizing, and downloadable PDF report generation.
"""
import io
import csv
from typing import Dict, Any, List, Optional
from ..store import PROFILE as P, log, gain, get_msme_profile
from ..utils.carbon_pdf import generate_carbon_report_pdf

SOLAR_KWP, YIELD_KWH_PER_KWP_DAY = 40, 4.5

def parse_meter_csv(csv_content: str) -> List[Dict[str, float]]:
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    readings = []
    for row in reader:
        try:
            readings.append({
                "timestamp": row.get("timestamp", ""),
                "kw": float(row.get("kw", row.get("kW", row.get("power_kw", 0.0)))),
                "pf": float(row.get("pf", row.get("power_factor", 0.95)))
            })
        except Exception:
            continue
    return readings

def analyze_smart_meter_csv(csv_content: str, msme_id: str = "demo") -> Dict[str, Any]:
    readings = parse_meter_csv(csv_content)
    profile = get_msme_profile(msme_id)
    if not readings:
        kw_values = profile.get("load_kw", [30, 45, 60, 80, 92, 56])
        readings = [{"timestamp": f"{i:02d}:00", "kw": float(v), "pf": 0.96} for i, v in enumerate(kw_values)]

    kws = [r["kw"] for r in readings]
    peak_kw = max(kws) if kws else 96.0
    avg_kw = sum(kws) / len(kws) if kws else 55.0
    est_monthly_kwh = sum(kws) * 30.0 / (len(kws) / 24.0) if len(kws) > 0 else profile.get("monthly_kwh", 18400.0)

    # ToD calculations for MPPKVVCL (MP Western DISCOM)
    # Peak hours: 18:00 - 22:00
    peak_tariff = profile.get("peak_tariff", 8.5)
    offpeak_tariff = profile.get("offpeak_tariff", 6.2)
    normal_tariff = profile.get("tariff_rs_kwh", 7.2)

    shiftable_kw = round(peak_kw * 0.25, 1)  # ~25% flexible load (e.g. pumps, annealing, air compressor)
    shift_kwh_month = shiftable_kw * 4 * 25  # 4 peak hours, 25 working days
    monthly_shift_savings_rs = round(shift_kwh_month * (peak_tariff - offpeak_tariff))

    # Solar sizing
    optimal_solar_kwp = round(avg_kw * 0.7, 0)  # optimal sizing covering ~70% base daytime load
    annual_solar_kwh = optimal_solar_kwp * YIELD_KWH_PER_KWP_DAY * 330
    monthly_solar_savings_rs = round((annual_solar_kwh / 12) * normal_tariff)
    capex_rs = round(optimal_solar_kwp * 42000)
    payback_years = round(capex_rs / (monthly_solar_savings_rs * 12), 1)

    gain("meter_audit", (monthly_shift_savings_rs + monthly_solar_savings_rs) * 12, (annual_solar_kwh / 12), 4.0, msme_id=msme_id)
    log("Energy Agent", f"Analyzed smart-meter CSV: {len(readings)} intervals, peak {peak_kw} kW", msme_id=msme_id)

    return {
        "status": "success",
        "intervals_analyzed": len(readings),
        "peak_demand_kw": peak_kw,
        "average_load_kw": round(avg_kw, 1),
        "estimated_monthly_kwh": round(est_monthly_kwh, 1),
        "load_shifting": {
            "shiftable_flexible_kw": shiftable_kw,
            "peak_window": "18:00 - 22:00 IST",
            "suggested_offpeak_window": "00:00 - 05:00 IST",
            "monthly_savings_rs": monthly_shift_savings_rs,
            "discom_tariff_structure": "MPPKVVCL High Tension / Industrial Tariff"
        },
        "rooftop_solar_assessment": {
            "recommended_capacity_kwp": optimal_solar_kwp,
            "estimated_annual_generation_kwh": round(annual_solar_kwh),
            "estimated_capex_rs": capex_rs,
            "monthly_power_bill_reduction_rs": monthly_solar_savings_rs,
            "payback_period_years": payback_years
        }
    }

def carbon_report(msme_id: str = "demo"):
    """Scope 2 emissions from grid electricity (illustrative factor; needs third-party verification)."""
    profile = get_msme_profile(msme_id)
    kwh = profile.get("monthly_kwh", 18400.0)
    factor = profile.get("grid_factor_tco2_mwh", 0.71)
    t = kwh * factor / 1000
    log("Energy Agent", "Built monthly carbon report from meter data (mock)", msme_id=msme_id)
    return {
        "monthly_kwh": kwh,
        "grid_factor": factor,
        "scope2_tco2e_month": round(t, 2),
        "standard": "CBAM-style draft",
        "verified": False,
        "disclaimer": "Draft report based on CEA v19 emission factor. Third-party audit required for official CBAM."
    }

def savings_plan(msme_id: str = "demo"):
    profile = get_msme_profile(msme_id)
    solar_kwh = SOLAR_KWP * YIELD_KWH_PER_KWP_DAY * 30
    tariff = profile.get("tariff_rs_kwh", 7.2)
    peak = profile.get("peak_tariff", 8.5)
    offpeak = profile.get("offpeak_tariff", 6.2)
    solar_rs = solar_kwh * tariff
    shift_rs = 3000 * (peak - offpeak)
    gain("energy", (solar_rs + shift_rs) * 12, solar_kwh, 2.5, msme_id=msme_id)
    log("Energy Agent", "Computed solar and load-shifting plan", msme_id=msme_id)
    return {
        "solar_kwp": SOLAR_KWP,
        "solar_kwh_month": solar_kwh,
        "solar_rs_month": round(solar_rs),
        "load_shift_rs_month": round(shift_rs),
        "shift": "Move ~22 kW press load from 18-22h to 0-5h"
    }

def generate_pdf(msme_id: str = "demo") -> bytes:
    profile = get_msme_profile(msme_id)
    c = carbon_report(msme_id)
    s = savings_plan(msme_id)
    return generate_carbon_report_pdf(
        msme_name=profile.get("name", "Sharma Auto Components"),
        city=profile.get("city", "Pithampur, Indore"),
        udyam=profile.get("udyam", "UDYAM-MP-23-0012345"),
        monthly_kwh=c["monthly_kwh"],
        grid_factor=c["grid_factor"],
        scope2_tco2e=c["scope2_tco2e_month"],
        solar_kwp=s["solar_kwp"],
        solar_rs_month=s["solar_rs_month"],
        load_shift_rs_month=s["load_shift_rs_month"]
    )
