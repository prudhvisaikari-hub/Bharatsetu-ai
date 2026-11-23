from ..store import PROFILE as P, SCHEMES, log, gain

def find_schemes(needs=None):
    needs = needs or ["loan", "capex", "quality", "export", "receivables", "energy"]
    out = [s for s in SCHEMES if P["category"] in s["categories"] and set(s["needs"]) & set(needs)]
    gain("scheme", 60000, 0, 4)
    log("Scheme Agent", f"Matched Udyam profile to {len(out)} schemes")
    return {"matches": out, "note": "Illustrative matches. Verify on official portals."}
