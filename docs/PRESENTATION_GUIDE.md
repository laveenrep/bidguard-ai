# How to present BidGuard AI

## 1. The 30-second pitch

"Government tender evaluation is slow and hard to audit. BidGuard AI is a web app that checks each bidder against a tender's requirements, scores compliance and risk with rules a person can read, verifies identifiers like GST and PAN, and keeps an audit trail of every action. The human officer still makes the final decision."

Use the word **rule-based** and say it confidently. It is a strength: every score can be explained line by line, which matters in procurement.

## 2. The problem and the idea (1 minute)

- Officers compare bidder documents against tender conditions by hand.
- Mistakes, inconsistent decisions and missing records cause disputes.
- Idea: turn tender conditions into **rules**, run them automatically, show **why** each bidder passed or failed, and record everything.

## 3. Architecture in one picture

```
React (Vite)  --JSON over REST + JWT-->  FastAPI  --SQLAlchemy-->  SQLite
  browser                                   |
                                            +-- rules.py   (scoring, risk, extraction)
                                            +-- ReportLab  (PDF reports)
                                            +-- data/uploads (evidence files + SHA-256)
```

Say it in one breath: "The React frontend calls a FastAPI backend. The backend checks the JWT, runs the rules, reads and writes SQLite through SQLAlchemy, and returns JSON."

## 4. Concepts to explain simply

| Concept | Simple explanation |
|---|---|
| REST API | The frontend asks the backend for data with URLs like `GET /api/tenders`. |
| JWT | After login the server gives a signed token. The frontend sends it with each request, and the server checks the signature instead of asking for the password again. There is a short-lived access token and a longer refresh token. |
| Password hashing | Passwords are stored as bcrypt hashes, never as plain text. |
| Roles | OFFICER and ADMIN can upload, verify and decide. AUDITOR can only view. |
| Compliance score | `sum of weights of passed rules / sum of all weights x 100` |
| Risk score | `(100 - score) x 0.8`, plus 35 if blacklisted, plus 10 if 3 or more rules failed, capped at 100. LOW below 35, MEDIUM 35-59, HIGH 60-79, CRITICAL 80+. |
| SHA-256 hash | A fingerprint of the uploaded file. If the file changes later, the fingerprint changes, so tampering is detectable. |
| Audit trail | Login, uploads, verification, compliance runs, decisions and reports are all logged with who and when. |

## 5. Live demo (7 minutes)

Follow `docs/DEMO_SCRIPT.md`, and add two things:

1. **Show a decision being explained**: run compliance for Coastal Engineering Works on the Electrical tender. It scores 35% and HIGH risk because it fails turnover, experience and ISO. Say: "Every failure is visible, so the officer knows exactly why."
2. **Show the tests**: in a terminal run `python -m pytest -v`. Say: "The scoring rules, login security and permissions are covered by automated tests."

Optional: open `http://localhost:8000/docs` (FastAPI's built-in API page), log in, and try `POST /api/tenders/1/extract` with this text:
`Bidder must have annual turnover of Rs. 2 Cr, 3 years experience, 40% local content, valid GST, and must not be blacklisted.`
It will list the detected rules.

## 6. Be upfront about what is real and what is simulated

| Part | Status |
|---|---|
| Login, JWT, roles, database, uploads, audit trail, PDF reports | Real and working |
| Compliance and risk scoring | Real, rule-based (no machine learning) |
| Requirement extraction from clause text | Real, regex/keyword based. The web UI button only reports registered requirements; pasted-text extraction is available through the API |
| GST / PAN / Udyam / blacklist verification | **Simulated**: compares against the bidder's own stored record, because real government APIs need authorization |
| Reading uploaded documents | Only .txt, .csv and .json are read as text. PDFs and images are stored and hashed, not read |

Saying this yourself earns trust. Evaluators and interviewers respect honesty more than big claims.

## 7. If someone asks "did you use AI to build it?"

A good answer: "Yes, I used AI tools to help write parts of the code. Then I went through it to understand how it works, I can trace a request from the React button to the API route, the rules and the database, and I added automated tests to check the behaviour." Only say this if it is true for you, so do the walkthrough before your presentation:

1. Trace one login: `Login` form -> `POST /api/auth/login` -> bcrypt check -> JWT returned.
2. Trace one compliance run: `GET /api/compliance/{tid}/{bid}` -> requirements from the database -> `rules.evaluate` -> JSON.
3. Read `rules.py` fully. It is about 150 lines and is the heart of the project.

## 8. Questions you may get

**Why FastAPI?** It is fast, uses Python type hints for validation, and generates API documentation automatically.

**Why SQLite?** It needs no setup, so the prototype runs anywhere. SQLAlchemy lets us move to PostgreSQL by changing the connection string, though that would need testing.

**Is it really AI?** The scoring is rule-based, which is intentional: every decision must be explainable. The design allows an ML or LLM component to be added later, for example to extract requirements from scanned tender PDFs.

**Are the government checks real?** No. They use a local demo registry, labelled DEMO ADAPTER in the app. The endpoint is built so a real authorized API could replace it.

**How do you keep it secure?** Hashed passwords, signed expiring tokens, role checks on write actions, file type and size limits, sanitized filenames, and an audit log. Gaps for production: HTTPS, a strong secret from the environment, rate limiting on login, and virus scanning of uploads.

**What if the rule is not recognised?** It is treated as FAIL and the explanation says so, which is the safe default.

**How did you test it?** Unit tests for the rule engine (boundaries such as turnover exactly 2 Cr) and API tests for login, permissions, uploads, decisions and reports.

**What would you improve next?** Add and edit requirements from the UI, read text from PDFs (OCR), move to PostgreSQL, add a Dockerfile, and plug in a real verification API.

## 9. Known limitations (say them before they are asked)

- Rules cover turnover, experience, local content, GST/PAN format, ISO, startup and blacklist only.
- GST and PAN checks only test the length of the number, not the real format.
- Single-user demo database, no pagination, no password change screen.
- Frontend has no automated tests.
