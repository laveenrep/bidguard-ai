# BidGuard AI 3.0 — Real Working SIH Prototype

This version is intentionally **not a static UI prototype**. The frontend calls a live FastAPI backend and SQLite database. Core actions create or read persistent records.

## Working modules

- Authentication with three roles
- Live dashboard metrics from SQLite
- Tender register and tender details
- Requirement extraction workflow
- Bidder registry
- Real file upload with SHA-256 evidence hash
- Database-backed compliance rule engine
- Explainable risk calculation
- Government verification adapter
- Final officer decision with audit record
- PDF report generation
- Audit timeline

## Important government API note

The included GST/PAN/Udyam/blacklist verification is a **working adapter against a local verification registry**. It is deliberately labelled DEMO ADAPTER. Real government portals often require authorized access, API credentials, certificates, whitelisting or other controls. The adapter boundary is designed so an authorized production API can replace the local registry without changing the frontend workflow.

## Windows setup

### 1. Backend

**Python:** Use Python 3.13 or 3.14. This version avoids the old `pydantic-core` source-build problem by using current wheels. If your existing `venv` was created during a failed install, delete it first.

Open Command Prompt or PowerShell:

```powershell
cd backend
py -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Keep this terminal running.

### 2. Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally:

`http://localhost:5173`

## Demo accounts

Officer:
`officer@bidguard.demo`
`Officer@123`

Admin:
`admin@bidguard.demo`
`Admin@123`

Auditor:
`auditor@bidguard.demo`
`Auditor@123`

The database and demo records are automatically created the first time the backend starts. No separate seed command is required.

## Recommended live demo

1. Sign in as Officer.
2. Open Tenders and select a tender.
3. Run requirement extraction.
4. Open Bidders and inspect a bidder.
5. Upload an evidence file.
6. Open Compliance.
7. Select tender + bidder.
8. Run live assessment.
9. Review each PASS/FAIL requirement.
10. Open Government Verification and verify GST/PAN/Udyam.
11. Open Risk Analysis.
12. Return to Compliance.
13. Record APPROVE / REJECT / REVIEW with a reason.
14. Generate the PDF report.
15. Open Audit Trail and show that actions were recorded.

## Architecture

Browser -> React/Vite -> FastAPI REST API -> SQLite

The backend contains separate logical services for:
- authentication
- requirement extraction
- compliance
- risk
- verification adapters
- reporting
- audit

The automated engines are advisory. Final procurement authority remains with the authorized officer.

## If installation was previously interrupted

From `backend`, run:

```powershell
deactivate
Remove-Item -Recurse -Force venv
py -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Using `python -m uvicorn` also avoids PATH issues where PowerShell says `uvicorn` is not recognized.

## Python 3.14.6 support
This package is prepared for CPython 3.14.x. Use `SETUP_PYTHON_3.14_WINDOWS.bat` to create a fresh virtual environment and install the modern dependency set. Do not reuse a virtual environment created by an older package.
