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
