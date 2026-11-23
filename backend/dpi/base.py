"""Abstract Base Interface for Digital Public Infrastructure (DPI) Adapters.
Enforces immutable consent recording in the audit trail for every data fetch.
"""
import uuid
import datetime as dt
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..store import log

class DPIAdapter(ABC):
    def __init__(self, name: str, is_mock: bool = True):
        self.name = name
        self.is_mock = is_mock

    def record_consent(
        self,
        msme_id: str,
        purpose: str,
        scope: str,
        expiry_days: int = 30,
        extra_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Records an explicit consent entry into the audit log before executing DPI transactions."""
        consent_id = f"CONSENT-{self.name[:3].upper()}-{uuid.uuid4().hex[:8]}"
        expiry_date = (dt.date.today() + dt.timedelta(days=expiry_days)).isoformat()
        consent_record = {
            "consent_id": consent_id,
            "dpi_rail": self.name,
            "purpose": purpose,
            "scope": scope,
            "expiry": expiry_date,
            "simulated": self.is_mock
        }
        details = {"consent_artifact": consent_record}
        if extra_details:
            details.update(extra_details)
        
        log(
            agent=f"DPI:{self.name}",
            action=f"Acquired user consent for {purpose} ({scope})",
            consent=f"Consent ID: {consent_id} [Exp: {expiry_date}]",
            details=details,
            msme_id=msme_id
        )
        return consent_record
