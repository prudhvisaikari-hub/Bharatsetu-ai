"""e-Invoicing Adapter (NIC e-Invoice System API Specification v1.03).
Generates official 64-character Invoice Reference Number (IRN) and signed QR code string.
"""
import hashlib
import uuid
import datetime as dt
from typing import Dict, Any, Optional
from .base import DPIAdapter
from ..store import get_msme_profile

class EInvoicingAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("eInvoicing", is_mock=is_mock)

    def generate_irn(
        self,
        invoice_number: str,
        buyer_gstin: str,
        total_amount_inr: float,
        tax_amount_inr: float = 0.0,
        msme_id: str = "demo"
    ) -> Dict[str, Any]:
        self.record_consent(
            msme_id=msme_id,
            purpose="e-Invoice Generation and Registration (IRN)",
            scope="B2B Tax Invoice Data",
            expiry_days=7
        )
        profile = get_msme_profile(msme_id)
        supplier_gstin = "23AABCS1429B1Z4"
        if self.is_mock:
            raw_str = f"{supplier_gstin}:{invoice_number}:{buyer_gstin}:{total_amount_inr}"
            irn_hash = hashlib.sha256(raw_str.encode()).hexdigest()
            ack_no = int(f"1126{abs(hash(invoice_number)) % 1000000000:09d}")
            ack_date = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            signed_qr_payload = (
                f"GSTIN:{supplier_gstin}|BUYER:{buyer_gstin}|DOC:{invoice_number}|"
                f"TOT:{total_amount_inr}|TAX:{tax_amount_inr}|IRN:{irn_hash[:16]}...|ACK:{ack_no}"
            )

            return {
                "status": "ACT",
                "ack_no": ack_no,
                "ack_date": ack_date,
                "irn": irn_hash,
                "signed_invoice_qr": signed_qr_payload,
                "seller_gstin": supplier_gstin,
                "buyer_gstin": buyer_gstin,
                "total_invoice_value": total_amount_inr,
                "portal": "NIC e-Invoice Portal (Sandbox)",
                "simulated": True
            }
        # Real-implementation stub for NIC e-Invoice system (POST /eivital/v1.03/Invoice)
        raise NotImplementedError("Real e-Invoicing requires live GSP credentials and digital signing certificate")
