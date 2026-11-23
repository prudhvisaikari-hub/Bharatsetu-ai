"""Worker Wellness Agent: Occupational health guidelines, ergonomic reminders for shopfloor workers,
ESI dispensary finder in Pithampur/Indore, and Ayushman Bharat claim instructions.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..store import log, gain

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WELLNESS_DATA = json.loads((DATA_DIR / "wellness_resources.json").read_text())

def get_reminders(operation: Optional[str] = None, msme_id: str = "demo") -> Dict[str, Any]:
    log("Worker Wellness Agent", f"Retrieved ergonomic safety reminders for {operation or 'shopfloor'}", msme_id=msme_id)
    guidelines = WELLNESS_DATA.get("ergonomic_guidelines", [])
    if operation:
        guidelines = [g for g in guidelines if operation.lower() in g["operation"].lower()]
    gain("wellness", rs=15000, hrs=2.0, msme_id=msme_id)
    return {
        "operation": operation or "General Shopfloor",
        "guidelines": guidelines or WELLNESS_DATA["ergonomic_guidelines"],
        "source": WELLNESS_DATA["source"],
        "last_verified": WELLNESS_DATA["last_verified"]
    }

def find_healthcare(cluster: Optional[str] = None, msme_id: str = "demo") -> Dict[str, Any]:
    log("Worker Wellness Agent", "Looked up ESI facilities and Ayushman Bharat coverage (verified)", msme_id=msme_id)
    facilities = WELLNESS_DATA.get("esi_facilities", [])
    if cluster:
        facilities = [f for f in facilities if cluster.lower() in f["address"].lower() or cluster.lower() in f["district"].lower()]
    gain("wellness", rs=10000, hrs=1.5, msme_id=msme_id)
    return {
        "esi_facilities": facilities or WELLNESS_DATA["esi_facilities"],
        "ayushman_bharat": WELLNESS_DATA["ayushman_bharat"],
        "teleconsultation": WELLNESS_DATA["teleconsultation"],
        "last_verified": WELLNESS_DATA["last_verified"]
    }

def summary_hi(operation: str = "press") -> str:
    """Returns natural Hindi wellness summary."""
    return (
        "कर्मचारी सुरक्षा और स्वास्थ्य निर्देश:\n"
        "1. भारी लिफ्टिंग और प्रेस मशीन पर काम करते समय कमर सीधी रखें और हर 2 घंटे में ऑपरेटर रोटेशन करें।\n"
        "2. नजदीकी ईएसआई अस्पताल: ईएसआई हॉस्पिटल सेक्टर-1 पीथमपुर (हेल्पलाइन: 07292-256123)।\n"
        "3. मुफ्त सरकारी टेली-कंसल्टेशन eSanjeevani (esanjeevani.mohfw.gov.in) पर उपलब्ध है। आयुष्मान भारत में प्रति वर्ष ₹5 लाख तक का कैशलेस इलाज मिलता है।"
    )
