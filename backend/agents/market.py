"""Market Agent: Lists products on mock ONDC / GeM catalogues, finds buyers in Pithampur-Indore corridor, and drafts listings."""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..store import PROFILE as P, log, gain, get_msme_profile

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MARKET_DATA = json.loads((DATA_DIR / "market_buyers.json").read_text())

def get_catalog_products(msme_id: str = "demo") -> List[Dict[str, Any]]:
    profile = get_msme_profile(msme_id)
    return [
        {
            "id": "prod_01",
            "name": "Precision CNC Machined Flange (EN8D)",
            "hsn": "8483",
            "unit_price_inr": 340,
            "moq": 500,
            "lead_time_days": 10,
            "material": "EN8D Normalized Steel",
            "certifications": ["ISO 9001:2015", "IATF 16949 Ready"],
            "simulated": True
        },
        {
            "id": "prod_02",
            "name": "Heavy Duty Stamping Suspension Bracket",
            "hsn": "8708",
            "unit_price_inr": 185,
            "moq": 1000,
            "lead_time_days": 14,
            "material": "CRCA High Tensile Sheet",
            "certifications": ["ISO 9001:2015"],
            "simulated": True
        },
        {
            "id": "prod_03",
            "name": "Hardened Drive Pin / Bushing Assembly",
            "hsn": "8483",
            "unit_price_inr": 120,
            "moq": 2000,
            "lead_time_days": 7,
            "material": "SAE 8620 Case Hardened",
            "certifications": ["ISO 9001:2015"],
            "simulated": True
        }
    ]

def find_buyers(query: Optional[str] = None, cluster: Optional[str] = None, msme_id: str = "demo") -> Dict[str, Any]:
    log("Market Agent", "Searched ONDC B2B and GeM buyer registry for Pithampur/Indore corridor (simulated)", msme_id=msme_id)
    buyers = MARKET_DATA.get("buyers", [])
    if cluster:
        buyers = [b for b in buyers if cluster.lower() in b.get("cluster", "").lower()]
    gain("market_discovery", rs=60000, hrs=3.0, msme_id=msme_id)
    return {
        "status": "success",
        "matches_count": len(buyers),
        "buyers": buyers,
        "note": "Simulated ONDC / GeM buyer matching based on MPIDC cluster data."
    }

def draft_listing(
    product_name: str,
    price_inr: float,
    moq: int = 500,
    hsn_code: str = "8483",
    lead_time_days: int = 14,
    msme_id: str = "demo"
) -> Dict[str, Any]:
    profile = get_msme_profile(msme_id)
    listing_id = f"ONDC-B2B-{msme_id[:6].upper()}-{abs(hash(product_name)) % 10000:04d}"
    listing = {
        "listing_id": listing_id,
        "seller_name": profile.get("name", "MSME Unit"),
        "seller_city": profile.get("city", "Pithampur, Indore"),
        "udyam_number": profile.get("udyam", "UDYAM-MP-23-0012345"),
        "product_title": product_name,
        "hsn_code": hsn_code,
        "base_price_inr": price_inr,
        "moq_units": moq,
        "standard_lead_time_days": lead_time_days,
        "gst_rate_pct": 18.0,
        "ondc_protocol_version": "B2B-1.2.0 (Beckn protocol)",
        "catalogue_network": "ONDC / GeM B2B (Simulated)",
        "simulated": True
    }
    gain("market_listing", rs=120000, hrs=4.0, msme_id=msme_id)
    log("Market Agent", f"Drafted ONDC/GeM product listing: '{product_name}' at Rs {price_inr:,} (simulated)", msme_id=msme_id)
    return {
        "status": "draft_created",
        "listing": listing,
        "disclaimer": "Simulated listing draft ready for export to live ONDC network gateway."
    }
