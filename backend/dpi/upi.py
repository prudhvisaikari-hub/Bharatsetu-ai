"""UPI Payment Links Adapter (NPCI Unified Payments Interface Specification).
Creates dynamic instant payment links and QR strings for B2B invoice collection.
"""
import urllib.parse
import uuid
from typing import Dict, Any, Optional
from .base import DPIAdapter
from ..store import get_msme_profile

class UPIPaymentAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("UPI", is_mock=is_mock)

    def create_invoice_payment_link(
        self,
        invoice_id: str,
        amount_inr: float,
        note: str = "B2B Component Payment",
        msme_id: str = "demo"
    ) -> Dict[str, Any]:
        self.record_consent(
            msme_id=msme_id,
            purpose="UPI Dynamic Payment Link Generation",
            scope="Payment Collection & Settlement",
            expiry_days=7
        )
        profile = get_msme_profile(msme_id)
        payee_vpa = "sharmaauto@sbi"
        payee_name = profile.get("name", "Sharma Auto Components")

        # Standard NPCI UPI URI Scheme
        params = {
            "pa": payee_vpa,
            "pn": payee_name,
            "mc": "5511",  # MSME Auto parts Merchant Category Code
            "tid": f"BS{uuid.uuid4().hex[:10].upper()}",
            "tr": invoice_id,
            "tn": f"Payment for {invoice_id} - {payee_name}",
            "am": f"{amount_inr:.2f}",
            "cu": "INR"
        }
        upi_uri = f"upi://pay?{urllib.parse.urlencode(params)}"

        if self.is_mock:
            return {
                "status": "CREATED",
                "invoice_id": invoice_id,
                "amount_rs": amount_inr,
                "payee_vpa": payee_vpa,
                "payee_name": payee_name,
                "upi_deep_link": upi_uri,
                "qr_content": upi_uri,
                "expiry_hours": 72,
                "simulated": True
            }
        # Real-implementation stub for NPCI UPI API
        raise NotImplementedError("Real UPI payment link integration requires approved bank PSP merchant ID")
