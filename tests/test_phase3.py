import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.dpi import get_adapter, AccountAggregatorAdapter
from backend.store import get_msme_audit

client = TestClient(app)

def test_account_aggregator_adapter_and_consent():
    r = client.post("/api/dpi/aa/consent", json={
        "customer_vpa": "owner@sbi",
        "purpose": "Working Capital Assessment"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "CONSENT_REQUESTED"
    assert "consent_handle" in data

    r_fin = client.get("/api/dpi/aa/financials?consent_handle=" + data["consent_handle"])
    assert r_fin.status_code == 200
    fin_data = r_fin.json()
    assert fin_data["status"] == "COMPLETED"
    assert len(fin_data["accounts"]) > 0

    # Verify audit trail has explicit consent logged
    audits = get_msme_audit("demo", limit=10)
    assert any("DPI:AccountAggregator" in a["agent"] and "Consent ID:" in a["consent"] for a in audits)

def test_gst_sandbox_and_eway_bill():
    r = client.get("/api/dpi/gst/status")
    assert r.status_code == 200
    gst_data = r.json()
    assert gst_data["status"] == "ACTIVE"
    assert len(gst_data["filings"]) >= 2

    # e-Way bill
    r_ewb = client.post("/api/dpi/gst/eway-bill", json={
        "invoice_number": "INV-2026-991",
        "to_gstin": "23AABCE1289P1Z2",
        "consignee_pincode": "454775",
        "vehicle_number": "MP-09-GH-8219",
        "value_inr": 350000.0
    })
    assert r_ewb.status_code == 200
    assert r_ewb.json()["status"] == "GENERATED"
    assert "eway_bill_no" in r_ewb.json()

def test_digilocker_document_pull():
    r = client.get("/api/dpi/digilocker/document?doc_type=UDYAM")
    assert r.status_code == 200
    doc = r.json()
    assert doc["status"] == "VERIFIED"
    assert "SHA256:" in doc["digital_signature"]
    assert doc["simulated"] is True

def test_udyam_registration_verification():
    r = client.get("/api/dpi/udyam/verify")
    assert r.status_code == 200
    u = r.json()
    assert u["status"] == "VERIFIED_ACTIVE"
    assert u["priority_sector_lending_eligible"] is True
    assert u["classification"] == "Small"

def test_einvoicing_irn_generation():
    r = client.post("/api/dpi/einvoicing/irn", json={
        "invoice_number": "INV-2026-102",
        "buyer_gstin": "23AABCM9910D1Z7",
        "total_amount_inr": 480000.0,
        "tax_amount_inr": 73220.0
    })
    assert r.status_code == 200
    irn_data = r.json()
    assert irn_data["status"] == "ACT"
    assert len(irn_data["irn"]) == 64  # SHA-256 hash length
    assert "signed_invoice_qr" in irn_data

def test_upi_payment_link_generation():
    r = client.post("/api/dpi/upi/payment-link", json={
        "invoice_id": "INV-2026-102",
        "amount_inr": 480000.0,
        "note": "Precision machined pins delivery"
    })
    assert r.status_code == 200
    upi_data = r.json()
    assert upi_data["status"] == "CREATED"
    assert "upi://pay?" in upi_data["upi_deep_link"]
    assert "480000.00" in upi_data["upi_deep_link"]

def test_ulip_logistics_tracking():
    r = client.get("/api/dpi/ulip/track?vehicle_number=MP-09-GH-8219")
    assert r.status_code == 200
    ulip_data = r.json()
    assert ulip_data["status"] == "IN_TRANSIT"
    assert len(ulip_data["fastag_toll_trail"]) >= 2
    assert ulip_data["vahan_status"]["rc_status"] == "ACTIVE"

def test_treds_receivables_discounting():
    r = client.post("/api/dpi/treds/discount", json={
        "invoice_number": "INV-2026-089",
        "buyer_name": "VE Commercial Vehicles Ltd",
        "buyer_gstin": "23AABCV1290K1Z9",
        "amount_rs": 680000.0,
        "due_days": 47
    })
    assert r.status_code == 200
    treds_data = r.json()
    assert treds_data["status"] == "AUCTION_ACTIVE"
    assert "best_bid" in treds_data
    assert treds_data["best_bid"]["annual_discount_rate_pct"] == 8.15
    assert treds_data["best_bid"]["net_cash_disbursement_rs"] > 0

def test_dpi_mode_real_stubs_raise_cleanly():
    # Verify real stub raises cleanly rather than silently failing
    real_adapter = AccountAggregatorAdapter(is_mock=False)
    with pytest.raises(NotImplementedError):
        real_adapter.request_consent(customer_vpa="test@upi")
