"""Setu: the orchestrator. With ANTHROPIC_API_KEY it runs a Claude tool-use loop; otherwise a keyword router.
Coordinates specialist agents: Energy/Carbon, Scheme, Finance, Compliance, Quality, Market, Maintenance, Supply Chain, and Wellness.
Supports English, Hindi, and Hinglish. Adheres strictly to the human-in-the-loop rule for financial submissions.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from . import config
from .agents import (
    energy, scheme, finance, compliance, quality,
    market, maintenance, supply_chain, wellness
)
from .store import PROFILE as P, log, get_msme_profile

logger = logging.getLogger("bharatsetu.orchestrator")

SYSTEM = """You are Setu, an AI operations copilot for small manufacturing enterprises (MSMEs) in Indore and Pithampur, Madhya Pradesh.
You represent the unit: {name} located in {city} (Udyam: {udyam}).
Rules you must strictly follow:
1. Always reply in the user's language (Hindi, English, or Hinglish). Keep Hindi natural and conversational.
2. Provide concrete numbers using specialist tools. Never guess or hallucinate data.
3. Human-in-the-loop: Never claim a loan, payment, subsidy application or statutory filing is submitted. The `draft_loan` tool ONLY creates a pending draft that the owner must explicitly review and approve.
4. Carbon honesty: Always state that Scope 2 carbon figures are drafts that require third-party verification for CBAM/export buyers.
5. Scheme honesty: Scheme matches are illustrative based on criteria; verify with official portal notifications.
6. For visual defect inspection, invite the owner to upload a photo of the machined/stamped part.
"""

TOOLS = [
    {
        "name": "carbon_report",
        "description": "Calculate monthly Scope 2 carbon footprint for export buyers (CBAM-style draft).",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "energy_savings_plan",
        "description": "Calculate solar capacity, generation, and time-of-day peak load shifting savings.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "find_schemes",
        "description": "Match the MSME against state and central government schemes (loan, capex, quality, export, receivables, energy).",
        "input_schema": {
            "type": "object",
            "properties": {
                "needs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of MSME needs: loan, capex, quality, export, receivables, energy"
                }
            }
        }
    },
    {
        "name": "finance_summary",
        "description": "Fetch bank statements, revenue, overdue receivables, and working capital status via Account Aggregator.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "draft_loan",
        "description": "Draft a working-capital loan application for owner approval. NEVER submits directly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount_rs": {"type": "integer", "description": "Loan amount in INR"}
            }
        }
    },
    {
        "name": "compliance_calendar",
        "description": "Check upcoming statutory deadlines for GST, PF/ESI, MPPCB pollution board, and Udyam renewal.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "summarize_circular",
        "description": "Summarize pasted or uploaded government circular text, highlighting key changes, applicability, and deadlines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text of the circular or notification"},
                "title": {"type": "string", "description": "Title or circular number"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "market_discovery",
        "description": "Find OEM and Tier-1 buyers in Pithampur/Indore corridor or draft an ONDC/GeM product listing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["find_buyers", "draft_listing"]},
                "product_name": {"type": "string"},
                "price_inr": {"type": "number"}
            }
        }
    },
    {
        "name": "predictive_maintenance",
        "description": "Analyze vibration, current, and temperature sensor data for machine anomalies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "machine_id": {"type": "string"}
            }
        }
    },
    {
        "name": "supply_chain_forecast",
        "description": "Forecast raw-material stock requirements and calculate reorder points based on lead times.",
        "input_schema": {
            "type": "object",
            "properties": {
                "orders_growth_pct": {"type": "number", "default": 15.0}
            }
        }
    },
    {
        "name": "worker_wellness",
        "description": "Get ergonomic reminders, ESI dispensary locations in Pithampur/Indore, and Ayushman Bharat info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {"type": "string"}
            }
        }
    },
    {
        "name": "business_snapshot",
        "description": "Summarize operational and margin drivers: power cost hike, overdue receivables, scrap cost, and rejection rate.",
        "input_schema": {"type": "object", "properties": {}}
    }
]

AGENT_OF = {
    "carbon_report": "Energy Agent",
    "energy_savings_plan": "Energy Agent",
    "find_schemes": "Scheme Agent",
    "finance_summary": "Finance Agent",
    "draft_loan": "Finance Agent",
    "compliance_calendar": "Compliance Agent",
    "summarize_circular": "Compliance Agent",
    "market_discovery": "Market Agent",
    "predictive_maintenance": "Predictive Maintenance",
    "supply_chain_forecast": "Supply Chain Agent",
    "worker_wellness": "Worker Wellness Agent",
    "business_snapshot": "Setu"
}

def snapshot(msme_id: str = "demo"):
    profile = get_msme_profile(msme_id)
    log("Setu", "Collected margin drivers from energy, finance and quality data", msme_id=msme_id)
    return {
        k: profile.get(k, 0) for k in (
            "power_cost_rise_pct", "overdue_receivables_rs", "overdue_days",
            "rejection_rate_pct", "scrap_cost_rs"
        )
    }

def run_tool(name: str, args: dict, msme_id: str = "demo") -> Any:
    try:
        if name == "carbon_report":
            return energy.carbon_report(msme_id=msme_id)
        elif name == "energy_savings_plan":
            return energy.savings_plan(msme_id=msme_id)
        elif name == "find_schemes":
            return scheme.find_schemes(args.get("needs"))
        elif name == "finance_summary":
            return finance.aa_summary(msme_id=msme_id)
        elif name == "draft_loan":
            amt = args.get("amount_rs", 1500000)
            return finance.draft_loan(amt, msme_id=msme_id)
        elif name == "compliance_calendar":
            return compliance.calendar(msme_id=msme_id)
        elif name == "summarize_circular":
            return compliance.summarize_circular(args.get("content", ""), args.get("title", ""), msme_id=msme_id)
        elif name == "market_discovery":
            act = args.get("action", "find_buyers")
            if act == "draft_listing":
                return market.draft_listing(args.get("product_name", "Machined Component"), args.get("price_inr", 350), msme_id=msme_id)
            return market.find_buyers(msme_id=msme_id)
        elif name == "predictive_maintenance":
            return maintenance.analyze_telemetry([], machine_id=args.get("machine_id", "CNC Machine"), msme_id=msme_id)
        elif name == "supply_chain_forecast":
            return supply_chain.forecast_raw_materials(args.get("orders_growth_pct", 15.0), msme_id=msme_id)
        elif name == "worker_wellness":
            return wellness.get_reminders(args.get("operation", "Shopfloor"), msme_id=msme_id)
        elif name == "business_snapshot":
            return snapshot(msme_id)
        else:
            return {"error": f"Tool '{name}' not found."}
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return {"error": str(e)}

SESSIONS: Dict[str, List[Dict[str, Any]]] = {}

def chat(session_id: str, text: str, msme_id: str = "demo") -> Dict[str, Any]:
    """Coordinates specialist agents. Uses Claude if ANTHROPIC_API_KEY is configured, else offline router."""
    if config.ANTHROPIC_API_KEY:
        try:
            return _claude(session_id, text, msme_id)
        except Exception as e:
            exc_type = type(e).__name__
            logger.warning(f"Claude API failed with exception: {exc_type}; falling back to offline router.")
            log("Setu", f"Claude unavailable ({exc_type}); used offline router", msme_id=msme_id)
    return _offline(text, msme_id)

def _claude(session_id: str, text: str, msme_id: str = "demo") -> Dict[str, Any]:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    profile = get_msme_profile(msme_id)
    system_prompt = SYSTEM.format(
        name=profile.get("name", "MSME Unit"),
        city=profile.get("city", "Pithampur, Indore"),
        udyam=profile.get("udyam", "UDYAM-MP-23-0012345")
    )

    msgs = SESSIONS.setdefault(session_id, [])
    msgs.append({"role": "user", "content": text})
    trace = ["Setu"]
    approval_id = None

    for _ in range(6):
        r = client.messages.create(
            model=config.BHARATSETU_MODEL,
            max_tokens=1500,
            system=system_prompt,
            tools=TOOLS,
            messages=msgs
        )
        msgs.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use":
            reply_text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
            res = {"reply": reply_text, "trace": trace}
            if approval_id:
                res["approval_id"] = approval_id
            return res

        results = []
        for b in r.content:
            if getattr(b, "type", None) == "tool_use":
                agent_name = AGENT_OF.get(b.name, "Setu")
                if agent_name not in trace:
                    trace.append(agent_name)
                tool_out = run_tool(b.name, b.input, msme_id)
                if isinstance(tool_out, dict) and "approval_id" in tool_out:
                    approval_id = tool_out["approval_id"]
                results.append({
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(tool_out)
                })
        msgs.append({"role": "user", "content": results})

    return {"reply": "Request required multiple complex iterations. Please try a more specific request.", "trace": trace}

def _offline(text: str, msme_id: str = "demo") -> Dict[str, Any]:
    s = text.lower()
    has = lambda ks: any(k in s for k in ks)

    is_carbon = has(["carbon", "कार्बन", "cbam", "energy", "बिजली", "solar", "export", "mwh", "kwh"])
    is_finance = has(["scheme", "subsid", "सब्सिडी", "योजना", "loan", "लोन", "credit", "grant", "working-capital"])
    is_profit = has(["profit", "मुनाफ", "loss", "margin", "मार्जिन", "drop", "why was my profit"])
    is_compliance = has(["gst", "complian", "कंप्लायंस", "deadline", "return", "tax"])
    is_circular = has(["circular", "सर्कुलर", "notification", "mppcb", "प्रदूषण", "rule change", "नियम"])
    is_quality = has(["defect", "quality", "दोष", "inspect", "scratch", "rejection", "क्रैक"])
    is_market = has(["market", "buyer", "खरीदार", "ondc", "gem", "listing", "ग्राहक", "बिक्री"])
    is_maintenance = has(["maintenance", "रखरखाव", "vibration", "वाइब्रेशन", "bearing", "बेयरिंग", "motor", "मशीन"])
    is_supply = has(["raw material", "कच्चा माल", "forecast", "पूर्वानुमान", "steel", "stock", "स्टॉक", "order book"])
    is_wellness = has(["wellness", "स्वास्थ्य", "esi", "ईएसआई", "ayushman", "आयुष्मान", "worker", "मजदूर", "ergonomic", "चोट"])

    # Multi-intent check: both carbon/export and loan/scheme triggered
    if is_carbon and is_finance:
        c = energy.carbon_report(msme_id=msme_id)
        e = energy.savings_plan(msme_id=msme_id)
        m = scheme.find_schemes()["matches"]
        f = finance.draft_loan(msme_id=msme_id)
        trace = ["Setu", "Energy Agent", "Finance Agent", "Scheme Agent"]
        reply = (
            f"Scope 2 Carbon Draft: {c['scope2_tco2e_month']} tCO2e/month (illustrative draft, requires third-party verification). "
            f"Solar {e['solar_kwp']} kWp saves Rs {e['solar_rs_month']:,}/month; load shifting saves Rs {e['load_shift_rs_month']:,}/month.\n"
            f"Matching schemes: {', '.join(x['name'] for x in m[:2])}. "
            f"I have drafted a Rs {f['amount_rs']:,} working capital loan application. "
            f"Owner confirmation is required before submission."
        )
        return {"trace": trace, "reply": reply, "approval_id": f["approval_id"]}

    if is_market:
        b = market.find_buyers(msme_id=msme_id)
        buyers_list = ", ".join(x["name"] for x in b["buyers"][:3])
        return {
            "trace": ["Setu", "Market Agent"],
            "reply": f"Found {b['matches_count']} matching B2B buyers on ONDC/GeM in Pithampur/Dewas belt: {buyers_list}. I can draft a standardized B2B listing for your parts."
        }

    if is_maintenance:
        res = maintenance.analyze_telemetry([], machine_id="100-Ton Power Press #3", msme_id=msme_id)
        trace = ["Setu", "Predictive Maintenance"]
        reply = f"{res['explanation']['en']}\n\n{res['explanation']['hi']}"
        return {"trace": trace, "reply": reply}

    if is_supply:
        res = supply_chain.forecast_raw_materials(msme_id=msme_id)
        trace = ["Setu", "Supply Chain Agent"]
        reply = f"{res['summary']['en']}\n\n{res['summary']['hi']}"
        return {"trace": trace, "reply": reply}

    if is_circular:
        res = compliance.summarize_circular(text, msme_id=msme_id)
        trace = ["Setu", "Compliance Agent"]
        reply = f"Regulatory Summary:\n• What Changed: {res['what_changed']}\n• Applicability: {res['applicability']}\n• Action Required: {res['action_required']}\n• Deadline: {res['deadline']}"
        return {"trace": trace, "reply": reply}

    if is_wellness:
        trace = ["Setu", "Worker Wellness Agent"]
        reply = wellness.summary_hi()
        return {"trace": trace, "reply": reply}

    if is_profit:
        d = snapshot(msme_id)
        return {
            "trace": ["Setu", "Energy Agent", "Finance Agent", "Quality Agent"],
            "reply": (
                f"Profit pressure analysis: Power cost is up {d['power_cost_rise_pct']}% (recommend shifting peak load). "
                f"Rs {d['overdue_receivables_rs']:,} is overdue for {d['overdue_days']} days (recommend discounting on TReDS). "
                f"Shopfloor rejections are at {d['rejection_rate_pct']}% (~Rs {d['scrap_cost_rs']:,} scrap cost)."
            )
        }

    if is_carbon:
        c = energy.carbon_report(msme_id=msme_id)
        e = energy.savings_plan(msme_id=msme_id)
        return {
            "trace": ["Setu", "Energy Agent"],
            "reply": (
                f"Carbon draft: {c['scope2_tco2e_month']} tCO2e/month (needs third-party verification). "
                f"Solar {e['solar_kwp']} kWp saves Rs {e['solar_rs_month']:,}/month; "
                f"load shifting saves Rs {e['load_shift_rs_month']:,}/month. Download full CBAM draft PDF from dashboard."
            )
        }

    if is_finance:
        m = scheme.find_schemes()["matches"]
        f = finance.draft_loan(msme_id=msme_id)
        return {
            "trace": ["Setu", "Scheme Agent", "Finance Agent"],
            "approval_id": f["approval_id"],
            "reply": (
                f"Matching schemes: {', '.join(x['name'] for x in m)}. "
                f"I drafted a Rs {f['amount_rs']:,} working-capital application. "
                "Owner approval is required to submit."
            )
        }

    if is_compliance:
        c = compliance.calendar(msme_id=msme_id)
        return {
            "trace": ["Setu", "Compliance Agent"],
            "reply": "Upcoming compliance deadlines: " + "; ".join(f"{x['item']} in {x['days_left']} days" for x in c)
        }

    if is_quality:
        return {
            "trace": ["Setu", "Quality Agent"],
            "reply": "Upload a photo of the machined part with the button below for YOLOv8 surface defect inspection."
        }

    return {
        "trace": ["Setu"],
        "reply": "Namaste! I am Setu. I can help with carbon reports, loans and schemes, compliance & circulars, YOLO defect checks, predictive maintenance, raw material forecasting, ONDC market listings, and worker wellness."
    }
