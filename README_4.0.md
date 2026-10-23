# BidGuard AI 4.0 — Stable Local Working Build

This build is an improved version of the supplied BidGuard AI 3.0 Python 3.14 project. It keeps the working tender, bidder, compliance, risk, verification, audit, decision and PDF-report workflows while fixing the session/token behavior and reducing repeated dashboard computation.

## Main improvements
- Access JWT + refresh JWT authentication.
- Automatic access-token refresh after a 401.
- Automatic session cleanup when the refresh token is expired/invalid.
- `/api/auth/me` validation when the app starts.
- SQLite WAL + normal synchronous mode for better concurrent local access.
- Dashboard calculation cache (5 seconds) to avoid repeated expensive recalculation.
- Stable client-side search filters that do not mutate the source dataset.
- Better loading/error states instead of repeated browser alerts.
- Abort-safe React effects; no `useEffect(async () => ...)` pattern.
- Compliance, risk, government verification, audit, evidence upload, decisions and PDF report remain accessible from the sidebar.
- Government verification is explicitly labeled as a local deterministic adapter, not a claim of direct government database access.

## Python 3.14
Use the bundled setup script or create the environment manually. The requirements use modern dependency ranges intended for CPython 3.14 wheels.

## Run
### Backend
```powershell
cd backend
py -3.14 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### Frontend
Open a second terminal:
```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, normally `http://localhost:5173`.

## Demo accounts
- officer@bidguard.demo / Officer@123
- admin@bidguard.demo / Admin@123
- auditor@bidguard.demo / Auditor@123

## Important
This is a local demonstration/development system. Government verification uses seeded/local data. It should not be represented as direct live access to government systems unless an authorized API integration is added.

## What changed in this update

- **`backend/app/rules.py`** (new): all scoring, risk and requirement-extraction logic now lives in one plain-Python file with no web or database code, so it is easy to read and to test.
- **Requirement extraction is real now**: `POST /api/tenders/{id}/extract` can take pasted clause text (`{"text": "..."}`) and detects turnover (crore/lakh), years of experience, local-content %, GST, PAN, ISO, startup and blacklist clauses using regular expressions. It is rule-based, not machine learning.
- **Bug fixes**: an unknown verification provider used to return VERIFIED (now 400); decisions for non-existent tenders/bidders returned a server error (now 404); empty decision reasons are rejected; a blacklisted bidder can no longer be counted as a "passing bid" on the dashboard; version labels now say 4.0.
- **Permissions**: uploading evidence, running verification and extraction, and recording decisions need the OFFICER or ADMIN role. AUDITOR is read-only.
- **Uploads**: only .txt, .csv, .json, .pdf, .png, .jpg, .jpeg and .docx are accepted.

## Running the tests

```powershell
cd backend
venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -v
```

Tests use a temporary database (set through `BIDGUARD_DATA_DIR`), so your real `data/bidguard.db` and uploads are never touched.

- `tests/test_rules.py`: scoring, risk levels, boundaries, extraction (no server needed)
- `tests/test_api.py`: login/JWT, permissions, compliance, verification, uploads, decisions, PDF report, audit trail

## Note on configuration

`.env.example` is only a template; the app does not load a `.env` file automatically. To change the secret, set it in the terminal before starting the server, for example `set BIDGUARD_SECRET=your-long-random-secret` (Windows Command Prompt).
