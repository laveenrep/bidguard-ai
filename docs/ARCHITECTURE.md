# BidGuard AI 3.0 Architecture

## Runtime

Frontend: React + Vite
Backend: FastAPI
Database: SQLite
Report engine: ReportLab

## Request flow

User action -> REST API -> database/service -> JSON result -> UI update

## Evidence workflow

1. User selects bidder and tender.
2. Evidence document is uploaded through multipart HTTP.
3. Backend writes it to `backend/data/uploads`.
4. SHA-256 is calculated and returned.
5. Document metadata is stored in SQLite.
6. Audit event is stored.

## Compliance workflow

Tender requirements are stored as normalized rules.

Examples:
- turnover>=20000000
- gst_valid
- pan_valid
- experience>=3
- local_content>=40
- not_blacklisted
- iso
- startup

Each requirement produces PASS/FAIL, weight, evidence hint and explanation.

## Risk workflow

Risk is calculated from:
- compliance score
- failed requirements
- blacklist status

The UI displays the drivers, rather than only showing an unexplained score.

## Verification adapter

`/api/government/verify` is the stable frontend-facing endpoint.

The current implementation uses a local deterministic registry derived from seeded bidder records. In a production deployment, this endpoint can call an authorized government integration service.

## Security baseline

- JWT authentication
- role check for final decision
- upload size limit
- filename sanitization
- CORS restricted to local frontend
- server-side rule evaluation
- audit events for important operations
