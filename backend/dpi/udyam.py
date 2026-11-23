"""Udyam Registration Adapter (Ministry of MSME Public Verification API).
Verifies enterprise classification (Micro/Small/Medium), PSL eligibility, and capital investment.
"""
from typing import Dict, Any, Optional
from .base import DPIAdapter
from ..store import get_msme_profile

class UdyamAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("Udyam", is_mock=is_mock)

    def verify_registration(self, udyam_number: Optional[str] = None, msme_id: str = "demo") -> Dict[str, Any]:
        self.record_consent(
            msme_id=msme_id,
            purpose="MSME Status & Priority Sector Lending (PSL) Eligibility Check",
            scope="Udyam Registry Official Record",
            expiry_days=90
        )
        profile = get_msme_profile(msme_id)
        target_udyam = udyam_number or profile.get("udyam", "UDYAM-MP-23-0012345")
        if self.is_mock:
            return {
                "status": "VERIFIED_ACTIVE",
                "udyam_registration_number": target_udyam,
                "enterprise_name": profile.get("name", "Sharma Auto Components"),
                "classification": profile.get("category", "small").capitalize(),
                "major_activity": "Manufacturing",
                "nic_code": "29301 - Manufacture of parts and accessories for motor vehicles",
                "cluster_location": profile.get("city", "Pithampur, Indore"),
                "investment_plant_machinery_cr": 4.25,
                "annual_turnover_cr": profile.get("monthly_revenue_rs", 4200000.0) * 12 / 10000000.0,
                "priority_sector_lending_eligible": True,
                "women_entrepreneur_status": False,
                "sc_st_status": False,
                "simulated": True
            }
        # Real-implementation stub for Udyam Verification API
        raise NotImplementedError("Real Udyam API integration requires MoMSME gateway authorization")
