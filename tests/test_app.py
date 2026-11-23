import io
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from backend.main import app
c = TestClient(app)

def test_carbon_report_math():
    r = c.post("/api/chat", json={"text": "carbon report for export"}).json()
    assert "13.06" in r["reply"] and "Energy Agent" in r["trace"]

def test_loan_requires_approval_and_executes_once():
    r = c.post("/api/chat", json={"text": "which subsidies and loan?"}).json()
    pid = r["approval_id"]
    assert c.post(f"/api/approve/{pid}").json()["status"] == "submitted"
    assert c.post(f"/api/approve/{pid}").status_code == 404

def test_quality_flags_scratch_and_passes_clean():
    clean = Image.new("RGB", (360, 200), (170, 175, 180))
    bad = clean.copy(); ImageDraw.Draw(bad).line((210, 60, 290, 150), fill=(40, 40, 40), width=4)
    def post(im):
        b = io.BytesIO(); im.save(b, "PNG"); return c.post("/api/inspect", files={"file": ("p.png", b.getvalue(), "image/png")}).json()
    assert post(clean)["verdict"] == "PASS" and post(bad)["verdict"] == "FAIL"

def test_bad_upload_rejected():
    assert c.post("/api/inspect", files={"file": ("x.png", b"nope", "image/png")}).status_code == 400
