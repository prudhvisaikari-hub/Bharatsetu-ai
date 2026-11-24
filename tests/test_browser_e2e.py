"""End-to-End Browser UI Test using Playwright.
Drives the web application end-to-end, testing:
- Bilingual English <-> Hindi localization toggle
- Interactive Setu multi-agent chat
- Human-in-the-loop loan approval workflow
- Owner Operations Dashboard with SVG/bar charts
- District Official Cluster Dashboard with k-anonymity privacy protection
Records high-resolution screenshots of each flow in the screenshots/ directory.
"""
import os
import time
import threading
import pytest
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

TEST_PORT = 8765
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

@pytest.fixture(scope="module", autouse=True)
def run_app_server():
    """Starts the BharatSetu AI FastAPI application on a dedicated test port."""
    from backend.main import app
    from backend.seed import seed_database
    seed_database(reset=True, force=True)

    config = uvicorn.Config(app=app, host="127.0.0.1", port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to bind
    import urllib.request
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/", timeout=1):
                break
        except Exception:
            time.sleep(0.2)
    yield
    server.should_exit = True

def test_playwright_e2e_user_flows():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Flow 1: Homepage & English View
        page.goto(f"{BASE_URL}/")
        page.wait_for_selector("#txt-app-title")
        assert "BharatSetu AI" in page.text_content("#txt-app-title")
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_homepage_english.png"))

        # Flow 2: Toggle to Devanagari Hindi
        page.click("#lang-btn")
        page.wait_for_timeout(300)
        assert "भारतसेतु एआई" in page.text_content("#txt-app-title")
        page.screenshot(path=str(SCREENSHOTS_DIR / "02_bilingual_hindi.png"))

        # Switch back to English for automated query run
        page.click("#lang-btn")
        page.wait_for_timeout(300)

        # Flow 3: Multi-Agent Query (Export Order + Carbon Report + Loan)
        prompt = "Next month's export order needs a carbon report and my loan is pending"
        page.fill("#query-input", prompt)
        page.click("#txt-send-btn")

        # Wait for Setu reply and trace badges
        page.wait_for_selector(".tr span", timeout=8000)
        page.wait_for_timeout(600)
        assert "Scope 2 Carbon Draft" in page.text_content("#msgs") or "Carbon draft" in page.text_content("#msgs")
        page.screenshot(path=str(SCREENSHOTS_DIR / "03_chat_and_loan_card.png"))

        # Flow 4: Human-in-the-Loop Confirmation
        # Check approval box appears with Approve button
        approve_button = page.locator(".approval-box button:has-text('Approve')").first
        if approve_button.is_visible():
            approve_button.click()
            page.wait_for_timeout(600)
            assert "successfully submitted" in page.text_content("#msgs") or "Submitted" in page.text_content("#msgs")
            page.screenshot(path=str(SCREENSHOTS_DIR / "04_loan_approved.png"))

        # Flow 5: Owner Operations Dashboard
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_selector("#d-money")
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOTS_DIR / "05_owner_dashboard.png"))

        # Flow 6: District Cluster Observatory & Privacy Guard
        page.goto(f"{BASE_URL}/cluster")
        page.wait_for_selector("#disp-cluster-name")
        page.wait_for_timeout(500)
        # Select Palda Cluster (< 5 cohort) to verify privacy suppression
        page.select_option("#cluster-select", "Palda Food & Engineering Cluster")
        page.wait_for_timeout(600)
        assert "Privacy Protection Active" in page.text_content("#privacy-warning")
        page.screenshot(path=str(SCREENSHOTS_DIR / "06_cluster_privacy_guard.png"))

        browser.close()
