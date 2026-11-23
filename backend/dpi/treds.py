"""TReDS Adapter (Trade Receivables Discounting System - RXIL / M1xchange / Invoicemart Specification).
Facilitates non-recourse factoring and auctioning of accepted B2B invoices for instant liquidity.
"""
import uuid
import datetime as dt
from typing import Dict, Any, Optional
from .base import DPIAdapter
from ..store import get_msme_profile

class TReDSAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("TReDS", is_mock=is_mock)

    def upload_invoice_for_discounting(
        self,
        invoice_number: str,
        buyer_name: str,
        buyer_gstin: str,
        amount_rs: float,
        due_days: int = 45,
        msme_id: str = "demo"
    ) -> Dict[str, Any]:
        self.record_consent(
            msme_id=msme_id,
            purpose="TReDS Factoring and Bid Auctioning for Immediate Liquidity",
            scope="Invoice Details, E-Way Bill and Buyer Acceptance Acknowledgement",
            expiry_days=30,
            extra_details={"invoice_number": invoice_number, "amount_rs": amount_rs}
        )
        profile = get_msme_profile(msme_id)
        if self.is_mock:
            factoring_unit_id = f"FU-MP-{uuid.uuid4().hex[:8].upper()}"
            # Standard competitive bank bids in Indian TReDS platforms (7.8% - 8.5% annual discount)
            best_bid_rate = 8.15
            discount_cost_rs = round(amount_rs * (best_bid_rate / 100.0) * (due_days / 365.0))
            net_disbursement_rs = round(amount_rs - discount_cost_rs)

            return {
                "status": "AUCTION_ACTIVE",
                "factoring_unit_id": factoring_unit_id,
                "invoice_number": invoice_number,
                "seller_name": profile.get("name", "Sharma Auto Components"),
                "buyer_name": buyer_name,
                "buyer_gstin": buyer_gstin,
                "gross_invoice_rs": amount_rs,
                "tenure_days": due_days,
                "best_bid": {
                    "financier": "State Bank of India (TReDS Desk)",
                    "annual_discount_rate_pct": best_bid_rate,
                    "discount_charges_rs": discount_cost_rs,
                    "net_cash_disbursement_rs": net_disbursement_rs,
                    "disbursement_timeline": "T+1 working day (within 24 hours)"
                },
                "disclaimer": "Simulated TReDS auction result based on current RBI-regulated platform clearing rates.",
                "simulated": True
            }
        # Real-implementation stub for M1xchange / RXIL API (POST /api/v1/invoices/upload)
        raise NotImplementedError("Real TReDS integration requires registered MSME entity credentials on RBI TReDS exchange")
