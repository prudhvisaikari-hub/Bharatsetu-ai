"""DigiLocker Adapter (DigiLocker API Specification 2.0).
Pulls verified enterprise documents: Udyam Certificate, Factory License, MPPCB Consent to Operate.
"""
import uuid
import datetime as dt
from typing import Dict, Any, Optional
from .base import DPIAdapter
from ..store import get_msme_profile

class DigiLockerAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("DigiLocker", is_mock=is_mock)

    def pull_document(
        self,
        doc_type: str = "UDYAM",
        doc_id: Optional[str] = None,
        msme_id: str = "demo"
    ) -> Dict[str, Any]:
        doc_type_upper = doc_type.upper()
        self.record_consent(
            msme_id=msme_id,
            purpose=f"Verification of {doc_type_upper} for Priority Sector Compliance",
            scope="DigiLocker XML Document Retrieval & Hash Validation",
            expiry_days=60
        )
        profile = get_msme_profile(msme_id)
        if self.is_mock:
            doc_uri = f"in.gov.msme.udyam/{profile.get('udyam', 'UDYAM-MP-23-0012345')}"
            return {
                "status": "VERIFIED",
                "doc_type": doc_type_upper,
                "doc_name": f"{profile.get('name', 'MSME Unit')} - {doc_type_upper} Certificate",
                "doc_uri": doc_uri,
                "issuer": "Ministry of Micro, Small and Medium Enterprises / MP Govt",
                "issue_date": "2021-08-14",
                "digital_signature": f"SHA256:{uuid.uuid4().hex.upper()}",
                "validity": "PERMANENT" if doc_type_upper == "UDYAM" else "VALID_UNTIL_2028",
                "simulated": True
            }
        # Real-implementation stub for DigiLocker 2.0 (POST /public/oauth2/1/pull-uri)
        raise NotImplementedError("Real DigiLocker integration requires MeitY API gateway credentials and user OAuth2 consent")
