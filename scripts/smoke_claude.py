"""Smoke test for live Claude API tool-use loop with Setu orchestrator.
Only runs if ANTHROPIC_API_KEY is configured in the environment.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config, orchestrator
from backend.store import get_approval

def smoke_claude() -> int:
    key = (config.ANTHROPIC_API_KEY or "").strip()
    if not key:
        print("ℹ️ ANTHROPIC_API_KEY is not set. Claude smoke test was NOT run (offline mode remains active).")
        return 0

    print(f"🚀 Running Claude live smoke test with model: {config.BHARATSETU_MODEL}...")
    prompt = "Next month's export order needs a carbon report and my loan is pending"
    session_id = "smoke_test_session"

    res = orchestrator.chat(session_id=session_id, text=prompt, msme_id="demo")
    print(f"Tools called / Trace: {res.get('trace')}")
    print(f"Final Reply: {res.get('reply')}")
    approval_id = res.get("approval_id")
    print(f"Approval ID: {approval_id}")

    if not approval_id:
        print("❌ Error: Expected draft_loan to produce an approval_id, but none was returned.")
        return 1

    appr = get_approval(approval_id, msme_id="demo")
    if not appr:
        print(f"❌ Error: Approval {approval_id} not found in database.")
        return 1

    if appr.get("status") != "pending":
        print(f"❌ Error: Expected approval status to be 'pending', got '{appr.get('status')}'. Human-in-the-loop violated!")
        return 1

    print("✅ Verified: draft_loan produced a PENDING approval; nothing was submitted autonomously.")
    print("✅ Claude smoke test passed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(smoke_claude())
