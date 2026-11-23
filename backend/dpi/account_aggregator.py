"""Account Aggregator (AA) Adapter (ReBIT 1.1.3 Specification).
Handles consent artifact generation, account linking, and bank statement analytics.
"""
import uuid
import datetime as dt
from typing import Dict, Any, Optional
from .base import DPIAdapter
from ..store import get_msme_profile

class AccountAggregatorAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("AccountAggregator", is_mock=is_mock)

    def request_consent(
        self,
        customer_vpa: str,
        purpose: str = "Working Capital Credit Assessment",
        date_range_months: int = 12,
        msme_id: str = "demo"
    ) -> Dict[str, Any]:
        consent_record = self.record_consent(
            msme_id=msme_id,
            purpose=purpose,
            scope=f"Bank statements last {date_range_months} months",
            expiry_days=90,
            extra_details={"customer_vpa": customer_vpa}
        )
        if self.is_mock:
            return {
                "status": "CONSENT_REQUESTED",
                "consent_handle": f"AA-HANDLE-{uuid.uuid4().hex[:12]}",
                "consent_artifact": consent_record,
                "fip_list": ["State Bank of India (Indore Industrial Branch)", "Bank of Baroda (Pithampur)"],
                "redirect_url": f"https://sandbox.rebit-aa.org/consent?handle={consent_record['consent_id']}",
                "simulated": True
            }
        # Real-implementation stub following ReBIT API spec
        # POST /Consent (headers: client_id, client_secret, x-jws-signature)
        raise NotImplementedError("Real Account Aggregator gateway requires production FIP/FIU certificates")

    def fetch_financial_data(self, consent_handle: str, msme_id: str = "demo") -> Dict[str, Any]:
        self.record_consent(
            msme_id=msme_id,
            purpose="Financial Information Fetch",
            scope="TRANSACTION_DATA",
            expiry_days=1
        )
        profile = get_msme_profile(msme_id)
        if self.is_mock:
            return {
                "status": "COMPLETED",
                "msme_id": msme_id,
                "accounts": [
                    {
                        "account_type": "CURRENT",
                        "bank": "State Bank of India",
                        "account_masked": "XXXXXX4892",
                        "current_balance_rs": 485000.0,
                        "average_monthly_balance_rs": 720000.0,
                        "monthly_turnover_rs": profile.get("monthly_revenue_rs", 4200000.0),
                        "overdue_inward_clearing_days": profile.get("overdue_days", 47)
                    }
                ],
                "inward_credit_turnover_12m_cr": 4.82,
                "bounce_count_12m": 0,
                "simulated": True
            }
        # Real-implementation stub following ReBIT API spec (/FI/fetch)
        raise NotImplementedError("Real Account Aggregator gateway requires production FIP/FIU certificates")
