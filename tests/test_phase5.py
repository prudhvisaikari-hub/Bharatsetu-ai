import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_owner_dashboard_api():
    r = client.get("/api/dashboard/owner")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert "impact_kpis" in data
    assert "money_saved_per_year_rs" in data["impact_kpis"]
    assert "defect_history" in data
    assert len(data["defect_history"]) == 6
    assert data["defect_history"][0]["defect_rate_pct"] >= 4.0
    # In DEMO_MODE, defect caption must be dynamically computed and labeled as simulated trend
    assert "defect_caption" in data
    assert "simulated trend (demo data)" in data["defect_caption"]
    assert f"{data['defect_history'][0]['defect_rate_pct']}%" in data["defect_caption"]
    assert f"{data['defect_history'][-1]['defect_rate_pct']}%" in data["defect_caption"]
    saving = data["defect_history"][0]["scrap_cost_rs"] - data["defect_history"][-1]["scrap_cost_rs"]
    assert f"₹{saving:,.0f}" in data["defect_caption"]
    assert "load_profile_24h" in data

def test_cluster_dashboard_compliant_aggregation():
    # Pithampur has 6 seeded units (>= 5)
    r = client.get("/api/dashboard/cluster?cluster=Pithampur Auto Cluster")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "AGGREGATED_SUCCESS"
    assert data["cohort_size"] >= 5
    assert data["no_pii_verified"] is True
    assert "aggregated_metrics" in data
    m = data["aggregated_metrics"]
    assert m["total_msme_count"] >= 5
    assert m["avg_monthly_revenue_rs"] > 0
    assert m["total_monthly_electricity_kwh"] > 0
    assert m["cluster_avg_rejection_rate_pct"] > 0

def test_cluster_dashboard_privacy_suppression():
    # Palda cluster has 2 seeded units (< 5 minimum threshold)
    r = client.get("/api/dashboard/cluster?cluster=Palda Food & Engineering Cluster")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "PRIVACY_SUPPRESSED"
    assert data["cohort_size"] < 5
    assert "suppressed" in data["privacy_notice"].lower()
    assert "aggregated_metrics" not in data

def test_dashboard_html_routes():
    r_dash = client.get("/dashboard")
    assert r_dash.status_code == 200
    assert "Owner Operations & ROI Dashboard" in r_dash.text
    assert "defect-chart" in r_dash.text

    r_clust = client.get("/cluster")
    assert r_clust.status_code == 200
    assert "District MSME Cluster Observatory" in r_clust.text
    assert "privacy-warning" in r_clust.text
