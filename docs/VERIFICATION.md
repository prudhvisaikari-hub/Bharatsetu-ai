# BharatSetu AI Verification Report

**Verification Date:** November 25, 2026  
**Target System:** BharatSetu AI (FastAPI + SQLAlchemy Backend, Vanilla JS/CSS Frontend, Docker)  
**Execution Environment:** Windows 11 Enterprise (Python 3.13.17, Pytest 9.2.0, Playwright 0.10.0, Docker 29.7.2, Docker Compose v5.3.1)  
**Author:** Antigravity AI Verification Engineer  

---

## Executive Summary

This report documents the verification across the four previously unrun areas of BharatSetu AI:
1. **Part 1: Docker Deployment, Secret Enforcement & Isolation**
2. **Part 2: Playwright End-to-End Browser Tests & Artifact Generation**
3. **Part 3: Anthropic Claude Natural Language & Multi-Turn Integration**
4. **Part 4: YOLOv8 Surface Defect Detector & Dataset Benchmarking**

All observations are documented with real command invocations, outputs, and status.

| Check | Result | Evidence File or Command |
|---|---|---|
| **Part 1: Docker CLI & Compose Binary Presence** | **PASSED** | `docker --version`, `docker compose version` |
| **Part 1: Clean Checkout `JWT_SECRET` Fail-Fast Guard** | **PASSED** | `docker compose config` / `docker compose up` output |
| **Part 1: Containerized Service Probing & Volume Persistence** | **NOT RUN** | Blocked by host WSL2 virtualization privileges (`Wsl/E_ACCESSDENIED`) |
| **Part 2: Chromium Browser Engine Installation** | **PASSED** | `python -m playwright install chromium` |
| **Part 2: Playwright E2E Multi-Step User Flow Execution** | **PASSED** | `tests/test_browser_e2e.py` (19.12s execution) |
| **Part 2: Full-Page High-Resolution Screenshots Generation** | **PASSED** | `screenshots/01_*.png` to `06_*.png` (6 full-page artifacts) |
| **Part 2: Full Project Test Suite (All 51 Tests)** | **PASSED** | `pytest -v` (51 passed in 39.09s, 100% pass rate) |
| **Part 3: Claude API Smoke Test & 10-Run Latency** | **NOT RUN** | `ANTHROPIC_API_KEY` not configured in environment |
| **Part 4: YOLO NEU-DET Dataset Training & Benchmarking** | **NOT RUN** | `data/neu-det/data.yaml` not present on host |
| **Part 4: Quality Agent Dual-Mode Fallback & Model Status** | **PASSED** | `tests/test_phase2.py::test_quality_agent_yolo_and_fallback` |

---

## Part 1: Docker

### 1.1 CLI & Compose Version Verification
**Status: PASSED**

Commands executed:
```powershell
docker --version
docker compose version
```

Output:
```
Docker version 29.7.2, build a7dcaa6
Docker Compose version v5.3.1
```

---

### 1.2 Missing Secret Fail-Fast Enforcement (Clean Checkout)
**Status: PASSED**

Tested clean checkout behavior with no `.env` file present and no `JWT_SECRET` exported in the shell:

Command executed:
```powershell
docker compose config
```

Observed Output:
```
error while interpolating services.bharatsetu-app.environment.[]: required variable JWT_SECRET is missing a value: JWT_SECRET must be set
```

Command executed:
```powershell
docker compose up
```

Observed Output:
```
error while interpolating services.bharatsetu-app.environment.[]: required variable JWT_SECRET is missing a value: JWT_SECRET must be set
```

**Finding:** Docker Compose correctly rejects startup when `JWT_SECRET` is unset, preventing insecure defaults from being deployed.

---

### 1.3 Container Runtime & Daemon Status
**Status: NOT RUN**

When launching the Docker Desktop background engine to build and run the containers:
```powershell
wsl --status
```

Observed Output:
```
Access is denied.
Error code: Wsl/E_ACCESSDENIED
```
Output from `docker version`:
```
Client:
 Version:           29.7.2
 API version:       1.53
 Go version:        go1.25.7
 Git commit:        a7dcaa6
 Built:             Wed Feb 18 03:02:43 2026
 OS/Arch:           windows/amd64
 Context:           default
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.53/version": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

**Reason:** The Windows host session lacks elevated hypervisor/WSL2 virtualization permissions required to initialize the Linux container engine. In compliance with verification rules, containerized steps (healthcheck polling, multi-tenant container registration, container restart persistence, non-root user ID verification) are marked **NOT RUN**.

---

## Part 2: Playwright Browser Test & Screenshots

### 2.1 Browser Engine Installation & Test Execution
**Status: PASSED**

Playwright Chromium was installed and the end-to-end browser test suite was executed against a live test server with `DEMO_MODE=true`:

Commands executed:
```powershell
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\pytest tests/test_browser_e2e.py -v
```

Observed Output:
```
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\prudh\Downloads\bharatsetu-ai\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\prudh\Downloads\bharatsetu-ai
plugins: anyio-4.16.0, playwright-0.10.0
collecting ... collected 1 item

tests/test_browser_e2e.py::test_playwright_e2e_user_flows PASSED         [100%]

============================= 1 passed in 19.12s ==============================
```

---

### 2.2 Generated Screenshots Review
**Status: PASSED**

The test generated six full-page screenshots into `screenshots/`:

| File Name | Size (Bytes) | Visual Inspection Notes |
|---|---|---|
| `01_homepage_english.png` | 78,346 | English homepage; prominent yellow `⚠️ DEMO MODE: simulated data & test environment` banner visible; clean navigation and typography. |
| `02_bilingual_hindi.png` | 81,844 | Hindi language mode; banner rendered in Hindi (`⚠️ डेमो मोड: सिम्युलेटेड डेटा और परीक्षण वातावरण`); bilingual button toggled. |
| `03_chat_and_loan_card.png` | 123,526 | Chat interface displaying multi-agent loan application card with approval action buttons. |
| `04_loan_approved.png` | 124,954 | Approved state confirmation with single-use token consumption and updated transaction log. |
| `05_owner_dashboard.png` | 81,458 | Owner executive dashboard displaying GST metrics, energy monitoring, carbon footprint math, and demo mode banner. |
| `06_cluster_privacy_guard.png` | 48,473 | Cluster dashboard showing k-anonymity privacy protection alert when cohort size is below threshold ($k < 5$). |

---

### 2.3 Comprehensive Regression Test Suite (51 Tests)
**Status: PASSED**

Executed the full test suite across unit, security, integration, and browser tests:

Command executed:
```powershell
.venv\Scripts\pytest -v
```

Observed Output:
```
====================== 51 passed, 16 warnings in 39.09s =======================
```

Every test module passed, including:
- Phase 1 Authentication & RBAC (`test_phase1.py` - 7 tests)
- Multi-Agent Orchestration & Physics (`test_phase2.py` - 8 tests)
- India DPI Stubs & Integrations (`test_phase3.py` - 9 tests)
- WhatsApp Meta Webhook, Voice & Bilingual UI (`test_phase4.py` - 6 tests)
- Owner & Cluster Dashboards with Privacy Guard (`test_phase5.py` - 4 tests)
- Strict Security Mode with DEMO_MODE=false (`test_demo_mode_false.py` - 8 tests)
- WhatsApp Cryptographic Signatures & Link Throttling (`test_whatsapp_auth.py` - 2 tests)
- Secret Leak Scanner (`test_secret_leak_scanner.py` - 1 test)
- Playwright Browser E2E (`test_browser_e2e.py` - 1 test)

---

## Part 3: Real Claude API Integration

**Status: NOT RUN**

Command executed:
```powershell
.venv\Scripts\python -c "import os; print('ANTHROPIC_API_KEY_PRESENT:', bool(os.getenv('ANTHROPIC_API_KEY')))"
```

Observed Output:
```
ANTHROPIC_API_KEY_PRESENT: False
```

**Reason:** `ANTHROPIC_API_KEY` is not present in the host environment. Under our verification rules, zero latency numbers, mock token counts, or fabricated completions are reported.

When an API key is provided, the live Claude pipeline can be executed via:
```powershell
python scripts/smoke_claude.py
```
Unit testing of the Claude tool execution loop, multi-turn state machine, and fallback handler is verified by `tests/test_claude_loop.py` (which passed).

---

## Part 4: Defect Detector (YOLO) Training and Evaluation

**Status: NOT RUN (Dataset Benchmark) / PASSED (Dual-Mode Fallback)**

### 4.1 Dataset & Benchmark Status
Command executed:
```powershell
.venv\Scripts\python -c "import os; print('NEU_DET_EXISTS:', os.path.exists('data/neu-det'))"
.venv\Scripts\python training/evaluate.py
```

Observed Output:
```
NEU_DET_EXISTS: False
❌ Error: Dataset config not found at C:\Users\prudh\Downloads\bharatsetu-ai\data\neu-det\data.yaml.
To evaluate, download NEU-DET to data/neu-det/ with data.yaml as described in docs/QUALITY_MODEL.md.
```

**Reason:** The NEU-DET benchmark dataset (Northeastern University Surface Defect Database) is not stored locally in `data/neu-det`. In accordance with `docs/QUALITY_MODEL.md`, synthetic benchmark metrics are never committed.

To benchmark once downloaded:
```bash
# 1. Place NEU-DET in data/neu-det/
# 2. Run evaluation
python training/evaluate.py --weights models/surface_defect_yolov8n.pt --data data/neu-det/data.yaml
```

### 4.2 Local Defect Detection & Statistical Fallback
**Status: PASSED**

The Quality Agent's dual-mode architecture was verified via `tests/test_phase2.py::test_quality_agent_yolo_and_fallback`:
- Evaluates synthetic surface blanks with known defects (scratch/pitting).
- Accurately detects anomalies and flags defects.
- Passes clean blanks without false positives.
- `model_validated` flag accurately reports `false` until verified against held-out validation data.

---

## Identified Fixes & Code Improvements During Verification

1. **Owner & Cluster Dashboards Missing Demo Banner:**
   - **File:** `backend/dashboard.py`, `frontend/dashboard.html`, `frontend/cluster.html`
   - **Fix:** Added `demo_mode: config.DEMO_MODE` to `/api/dashboard` and `/api/dashboard/cluster` API responses. Added `#demo-banner` element to `dashboard.html` and `cluster.html` matching `index.html`.
2. **Playwright Screenshot Completeness:**
   - **File:** `tests/test_browser_e2e.py`
   - **Fix:** Added `full_page=True` to screenshot calls to capture full responsive page heights and footer elements.
3. **Module Imports in Test Fixtures & Security Handlers:**
   - **File:** `backend/store.py`, `backend/auth.py`, `tests/test_phase1.py`
   - **Fix:** Resolved missing `os` and `hmac` imports identified during unit test execution.

---

## Remaining Risks & Recommendations

1. **Docker Execution in Production:**
   - Container configuration and fail-fast secret checks passed static analysis and compose validation. Running full containers requires virtualization permissions enabled in the deployment target (e.g. AWS ECS, GCP Cloud Run, or a Linux host with Docker daemon active).
2. **Anthropic API Rate & Quota Monitoring:**
   - When deploying with a production `ANTHROPIC_API_KEY`, ensure rate limiting and timeout safeguards in `backend/orchestrator.py` are coupled with monitoring for 529/429 responses.
3. **NEU-DET Benchmark Formalization:**
   - When preparing for formal model release, run `training/evaluate.py` on the complete validation split so `docs/quality_results.json` is generated with real held-out metrics.
