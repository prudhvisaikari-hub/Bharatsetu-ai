from typing import Optional
from ..store import PROFILE as P, SCHEMES, log, gain, get_msme_profile

def find_schemes(needs=None, msme_id: Optional[str] = None):
    needs = needs or ["loan", "capex", "quality", "export", "receivables", "energy"]
    profile = get_msme_profile(msme_id) if msme_id else P
    category = profile.get("category", "small")
    out = [s for s in SCHEMES if category in s["categories"] and set(s["needs"]) & set(needs)]
    gain("scheme", 60000, 0, 4, msme_id=msme_id)
    log("Scheme Agent", f"Matched Udyam profile to {len(out)} schemes", msme_id=msme_id or "demo")
    return {"matches": out, "note": "Illustrative matches. Verify on official portals."}
