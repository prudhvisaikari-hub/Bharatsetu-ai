import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from backend.main import app

client = TestClient(app)

def test_market_agent_endpoints():
    r = client.get("/api/market/buyers")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert len(data["buyers"]) >= 3
    assert any("Pithampur" in b["cluster"] for b in data["buyers"])

    # Draft listing
    r_list = client.post("/api/market/listing", json={
        "product_name": "Forged Flange Pin",
        "price_inr": 290.0,
        "moq": 500,
        "hsn_code": "8483",
        "lead_time_days": 10
    })
    assert r_list.status_code == 200
    listing = r_list.json()["listing"]
    assert listing["product_title"] == "Forged Flange Pin"
    assert listing["base_price_inr"] == 290.0
    assert listing["simulated"] is True

def test_quality_agent_yolo_and_fallback():
    clean = Image.new("RGB", (360, 200), (170, 175, 180))
    bad = clean.copy()
    ImageDraw.Draw(bad).line((210, 60, 290, 150), fill=(40, 40, 40), width=4)

    b_clean, b_bad = io.BytesIO(), io.BytesIO()
    clean.save(b_clean, "PNG")
    bad.save(b_bad, "PNG")

    res_clean = client.post("/api/inspect", files={"file": ("clean.png", b_clean.getvalue(), "image/png")}).json()
    assert res_clean["verdict"] == "PASS"
    assert "model_validated" in res_clean
    assert res_clean["model_validated"] is False
    assert res_clean["model_name"] == "surface_defect_yolov8n.pt"

    res_bad = client.post("/api/inspect", files={"file": ("bad.png", b_bad.getvalue(), "image/png")}).json()
    assert res_bad["verdict"] == "FAIL"
    assert len(res_bad["boxes"]) > 0
    assert "model_validated" in res_bad

def test_predictive_maintenance():
    # Send CSV with high vibration
    sample_csv = "timestamp,machine_id,vibration_rms,current_a,temperature_c\n08:00,Press-1,2.1,14.5,43.0\n09:00,Press-1,4.8,18.5,58.0\n"
    r = client.post("/api/maintenance/telemetry?machine_id=Press-1", files={"file": ("sensor.csv", sample_csv.encode(), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "anomaly_detected"
    assert data["risk_level"] in ("HIGH", "MEDIUM")
    assert "वाइब्रेशन" in data["explanation"]["hi"] or "anomaly" in data["explanation"]["en"]

def test_supply_chain_forecasting():
    r = client.get("/api/supply-chain/forecast?growth=20")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert len(data["forecasts"]) >= 3
    # Look for steel or fasteners
    mats = [f["name"] for f in data["forecasts"]]
    assert any("Steel" in m or "Fasteners" in m for m in mats)
    assert "कच्चे माल" in data["summary"]["hi"]

def test_compliance_circular_summarizer():
    circular_text = (
        "Madhya Pradesh Pollution Control Board Notification 2026: All electroplating and foundry units "
        "in Pithampur and Sanwer Road must install IoT effluent sensors before April 1, 2026. Non-compliance "
        "shall attract revocation of Consent to Operate (CTO)."
    )
    r = client.post("/api/compliance/circular", json={"content": circular_text, "title": "MPPCB 2026/04"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "summarized"
    assert "effluent" in data["what_changed"].lower() or "sensor" in data["what_changed"].lower()
    assert "2026" in data["deadline"]

def test_energy_smart_meter_and_pdf():
    # 1. Smart meter CSV analysis
    meter_csv = "timestamp,kw,pf\n00:00,30,0.96\n08:00,75,0.95\n19:00,98,0.94\n23:00,40,0.97\n"
    r_meter = client.post("/api/energy/smart-meter", files={"file": ("meter.csv", meter_csv.encode(), "text/csv")})
    assert r_meter.status_code == 200
    meter_data = r_meter.json()
    assert meter_data["status"] == "success"
    assert meter_data["peak_demand_kw"] == 98.0
    assert meter_data["load_shifting"]["monthly_savings_rs"] > 0
    assert meter_data["rooftop_solar_assessment"]["recommended_capacity_kwp"] > 0

    # 2. PDF Download
    r_pdf = client.get("/api/energy/carbon-report-pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content.startswith(b"%PDF")

def test_worker_wellness():
    r = client.get("/api/wellness/info?operation=press")
    assert r.status_code == 200
    data = r.json()
    assert len(data["facilities"]["esi_facilities"]) >= 2
    assert "ईएसआई" in data["summary_hi"]

def test_multi_agent_hindi_export_loan_prompt():
    prompt = "Next month's export order needs a carbon report and my loan is pending"
    r = client.post("/api/chat", json={"text": prompt}).json()
    trace = r["trace"]
    # Must trigger Energy, Finance, and Scheme agents
    assert "Energy Agent" in trace
    assert "Finance Agent" in trace
    assert "Scheme Agent" in trace
    assert "approval_id" in r
    assert "Carbon Draft" in r["reply"] or "tCO2e" in r["reply"]
