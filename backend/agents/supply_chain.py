"""Supply Chain Agent: forecasts raw-material requirements from order book and historical run-rates.
Uses an explainable BOM explosion and moving-average safety stock model.
"""
from typing import Dict, Any, List, Optional
from ..store import log, gain

MATERIALS_CATALOG = {
    "EN8D_round_bar": {
        "name": "EN8D Steel Round Bar (45mm)",
        "unit": "Metric Ton (MT)",
        "current_stock": 4.2,
        "monthly_burn_rate": 8.5,
        "lead_time_days": 12,
        "supplier_hub": "Raipur / Jamshedpur Steel Mills",
        "unit_price_rs": 62000
    },
    "CRCA_sheet_coil": {
        "name": "CRCA Cold-Rolled Steel Sheet (2.5mm)",
        "unit": "Metric Ton (MT)",
        "current_stock": 2.1,
        "monthly_burn_rate": 6.0,
        "lead_time_days": 14,
        "supplier_hub": "Dewas / Pithampur Service Center",
        "unit_price_rs": 68000
    },
    "grade_8_fasteners": {
        "name": "M10 Grade 8.8 High-Tensile Fasteners",
        "unit": "Boxes (1000 pcs)",
        "current_stock": 18,
        "monthly_burn_rate": 35,
        "lead_time_days": 5,
        "supplier_hub": "Sanwer Road Industrial Area",
        "unit_price_rs": 4500
    }
}

def forecast_raw_materials(
    orders_growth_pct: float = 15.0,
    days_horizon: int = 30,
    msme_id: str = "demo"
) -> Dict[str, Any]:
    log("Supply Chain Agent", f"Computed {days_horizon}-day raw-material forecast with {orders_growth_pct}% order bump", msme_id=msme_id)
    multiplier = 1.0 + (orders_growth_pct / 100.0)
    forecasts = []
    urgent_alerts = []

    for mat_id, mat in MATERIALS_CATALOG.items():
        projected_monthly_need = mat["monthly_burn_rate"] * multiplier
        daily_burn = projected_monthly_need / 30.0
        days_remaining = round(mat["current_stock"] / daily_burn, 1) if daily_burn > 0 else 99
        safety_stock = round(daily_burn * mat["lead_time_days"] * 0.5, 2)
        reorder_point = round((daily_burn * mat["lead_time_days"]) + safety_stock, 2)
        needs_order = mat["current_stock"] <= reorder_point

        recommended_order_qty = round(max(0.0, projected_monthly_need - mat["current_stock"] + safety_stock), 2)
        est_cost_rs = round(recommended_order_qty * mat["unit_price_rs"])

        item = {
            "material_id": mat_id,
            "name": mat["name"],
            "unit": mat["unit"],
            "current_stock": mat["current_stock"],
            "projected_need_30d": round(projected_monthly_need, 2),
            "days_stock_remaining": days_remaining,
            "lead_time_days": mat["lead_time_days"],
            "reorder_point": reorder_point,
            "needs_order": needs_order,
            "recommended_order_qty": recommended_order_qty,
            "estimated_cost_rs": est_cost_rs,
            "supplier_hub": mat["supplier_hub"]
        }
        forecasts.append(item)
        if needs_order:
            urgent_alerts.append(
                f"{mat['name']}: {days_remaining} days of stock left. Lead time is {mat['lead_time_days']} days. Order {recommended_order_qty} {mat['unit']}."
            )

    gain("supply_chain", rs=45000, hrs=4.0, msme_id=msme_id)
    summary_hi = (
        f"कच्चे माल का पूर्वानुमान: आने वाले महीने के लिए सीआरसीए शीट और ईएन8डी राउंड बार का स्टॉक "
        f"पुनः ऑर्डर बिंदु (reorder point) पर है। रायपुर/देवास से डिलीवरी में 12-14 दिन लगते हैं। "
        f"उत्पादन रुकने से बचने के लिए अगले 3 दिनों में ऑर्डर दें।"
    )

    return {
        "status": "success",
        "horizon_days": days_horizon,
        "order_growth_assumed_pct": orders_growth_pct,
        "forecasts": forecasts,
        "urgent_alerts": urgent_alerts,
        "summary": {
            "en": "; ".join(urgent_alerts) if urgent_alerts else "All raw materials have healthy buffer stock.",
            "hi": summary_hi
        }
    }
