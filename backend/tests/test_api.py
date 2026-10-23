"""API tests: login, permissions, tenders, compliance, uploads, decisions, reports.

Run from the backend folder:   python -m pytest -v
Uses a temporary database (see conftest.py), so your real data is never touched.
Seeded demo data: 3 tenders (ids 1-3), 5 bidders (ids 1-5), 3 users.
"""
import hashlib
from datetime import timedelta
from types import SimpleNamespace


# ------------------------------------------------------------------ health
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# -------------------------------------------------------------------- auth
def test_login_success_returns_tokens_and_role(officer_login):
    assert officer_login["user"]["role"] == "OFFICER"
    assert officer_login["access_token"] and officer_login["refresh_token"]
    assert officer_login["access_token"] != officer_login["refresh_token"]


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "officer@bidguard.demo", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert r.status_code == 401


def test_protected_route_needs_token(client):
    assert client.get("/api/tenders").status_code == 401


def test_garbage_token_rejected(client):
    assert client.get("/api/tenders", headers={"Authorization": "Bearer not.a.token"}).status_code == 401


def test_me_returns_current_user(client, officer):
    r = client.get("/api/auth/me", headers=officer)
    assert r.status_code == 200 and r.json()["email"] == "officer@bidguard.demo"


def test_refresh_token_cannot_be_used_as_access_token(client, officer_login):
    h = {"Authorization": f"Bearer {officer_login['refresh_token']}"}
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_access_token_cannot_be_used_to_refresh(client, officer_login):
    r = client.post("/api/auth/refresh", json={"refresh_token": officer_login["access_token"]})
    assert r.status_code == 401


def test_refresh_gives_working_access_token(client, officer_login):
    r = client.post("/api/auth/refresh", json={"refresh_token": officer_login["refresh_token"]})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200


def test_expired_token_rejected(client):
    from app.main import _token
    fake_user = SimpleNamespace(id=1, email="officer@bidguard.demo", role="OFFICER")
    expired = _token(fake_user, "access", timedelta(seconds=-10))
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


# --------------------------------------------------------- tenders/bidders
def test_list_tenders(client, officer):
    r = client.get("/api/tenders", headers=officer)
    assert r.status_code == 200 and len(r.json()) == 3


def test_tender_detail_includes_requirements(client, officer):
    r = client.get("/api/tenders/1", headers=officer)
    assert r.status_code == 200
    assert len(r.json()["requirements"]) == 6


def test_tender_not_found(client, officer):
    assert client.get("/api/tenders/999", headers=officer).status_code == 404


def test_list_bidders(client, officer):
    r = client.get("/api/bidders", headers=officer)
    assert r.status_code == 200 and len(r.json()) == 5


def test_bidder_detail_and_not_found(client, officer):
    r = client.get("/api/bidders/1", headers=officer)
    assert r.status_code == 200 and r.json()["name"].startswith("Apex")
    assert "documents" in r.json() and "verifications" in r.json()
    assert client.get("/api/bidders/999", headers=officer).status_code == 404


# ----------------------------------------------------- compliance and risk
def test_fully_compliant_bidder(client, officer):
    r = client.get("/api/compliance/1/1", headers=officer).json()   # Apex vs safety tender
    assert r["score"] == 100.0 and r["risk_level"] == "LOW" and r["failed"] == 0


def test_high_risk_bidder(client, officer):
    r = client.get("/api/compliance/2/3", headers=officer).json()   # Coastal vs electrical tender
    assert r["score"] == 35.0 and r["failed"] == 3
    assert r["risk_score"] == 62 and r["risk_level"] == "HIGH"


def test_blacklisted_bidder_is_disqualified_despite_good_score(client, officer):
    r = client.get("/api/compliance/1/5", headers=officer).json()   # Eastern Projects (blacklisted)
    assert r["score"] == 80.0
    assert r["disqualified"] is True
    assert r["risk_level"] == "MEDIUM"


def test_compliance_unknown_ids(client, officer):
    assert client.get("/api/compliance/999/1", headers=officer).status_code == 404
    assert client.get("/api/compliance/1/999", headers=officer).status_code == 404


def test_risk_endpoint_lists_failed_requirements_as_drivers(client, officer):
    r = client.get("/api/risk/2/3", headers=officer).json()
    assert r["risk_level"] == "HIGH"
    assert set(r["drivers"]) == {"Minimum annual turnover ₹3 Cr", "Minimum 5 years experience", "ISO certification"}
    assert "review" in r["recommendation"].lower()


def test_dashboard_totals_match_seed_data(client, officer):
    d = client.get("/api/dashboard", headers=officer).json()
    assert d["tenders"] == 3 and d["bidders"] == 5 and d["total_assessments"] == 15
    assert d["passing_bids"] == 5 and d["failed_bids"] == 10     # blacklisted bids never count as passing
    assert d["high_risk"] == 3
    assert d["compliance_rate"] == 33.3


# ---------------------------------------------------- requirement extraction
def test_extract_from_pasted_clause_text(client, officer):
    text = "Annual turnover of ₹2 Cr, 3 years experience, 40% local content, valid GST, not blacklisted."
    r = client.post("/api/tenders/1/extract", json={"text": text}, headers=officer)
    assert r.status_code == 200
    detected = {d["rule"]: d for d in r.json()["detected"]}
    assert {"turnover>=20000000", "experience>=3", "local_content>=40", "gst_valid", "not_blacklisted"} <= set(detected)
    assert detected["turnover>=20000000"]["already_registered"] is True   # tender 1 already has this rule


def test_extract_without_body_uses_tender_text(client, officer):
    r = client.post("/api/tenders/1/extract", headers=officer)
    assert r.status_code == 200 and r.json()["requirements_found"] == 6


def test_extract_unknown_tender(client, officer):
    assert client.post("/api/tenders/999/extract", headers=officer).status_code == 404


def test_auditor_cannot_run_extraction(client, auditor):
    assert client.post("/api/tenders/1/extract", headers=auditor).status_code == 403


# ------------------------------------------------------------ verification
def verify(client, headers, bidder_id, provider, reference):
    return client.post("/api/government/verify", headers=headers,
                       json={"bidder_id": bidder_id, "provider": provider, "reference": reference})


def test_verify_correct_gst(client, officer):
    r = verify(client, officer, 1, "GST", "33AAECA1234F1Z5")
    assert r.status_code == 200 and r.json()["status"] == "VERIFIED"


def test_verify_is_case_insensitive(client, officer):
    r = verify(client, officer, 1, "gst", "  33aaeca1234f1z5 ")
    assert r.json()["status"] == "VERIFIED" and r.json()["provider"] == "GST"


def test_verify_wrong_reference_is_mismatch(client, officer):
    assert verify(client, officer, 1, "PAN", "ZZZZZ9999Z").json()["status"] == "MISMATCH"


def test_verify_udyam_missing_on_record_is_mismatch(client, officer):
    assert verify(client, officer, 3, "UDYAM", "UDYAM-TN-00-0000000").json()["status"] == "MISMATCH"


def test_blacklisted_bidder_fails_blacklist_check(client, officer):
    assert verify(client, officer, 5, "BLACKLIST", "any").json()["status"] == "MISMATCH"
    assert verify(client, officer, 1, "BLACKLIST", "any").json()["status"] == "VERIFIED"


def test_unknown_provider_is_rejected(client, officer):
    assert verify(client, officer, 1, "ANYTHING", "x").status_code == 400


def test_verify_unknown_bidder(client, officer):
    assert verify(client, officer, 999, "GST", "x").status_code == 404


def test_auditor_cannot_verify(client, auditor):
    assert verify(client, auditor, 1, "GST", "33AAECA1234F1Z5").status_code == 403


def test_verification_is_saved_on_bidder(client, officer):
    verify(client, officer, 2, "PAN", "AABCB5678G")
    saved = client.get("/api/bidders/2", headers=officer).json()["verifications"]
    assert any(v["provider"] == "PAN" and v["status"] == "VERIFIED" for v in saved)


# ----------------------------------------------------------------- uploads
def upload(client, headers, name="evidence.txt", content=b"hello", bidder=1, tender=1, content_type="text/plain"):
    return client.post(f"/api/bidders/{bidder}/documents", headers=headers,
                       data={"tender_id": str(tender), "doc_type": "GST_CERTIFICATE"},
                       files={"file": (name, content, content_type)})


def test_upload_returns_correct_sha256(client, officer):
    content = b"GSTIN: 33AAECA1234F1Z5"
    r = upload(client, officer, content=content)
    assert r.status_code == 200
    assert r.json()["sha256"] == hashlib.sha256(content).hexdigest()
    assert r.json()["size"] == len(content)


def test_uploaded_text_file_is_stored_in_database(client, officer):
    upload(client, officer, name="notes.txt", content=b"turnover 2 crore")
    docs = client.get("/api/bidders/1", headers=officer).json()["documents"]
    assert any(d["filename"] == "notes.txt" for d in docs)


def test_upload_sanitizes_filename_on_disk(client, officer):
    from app.main import UPLOADS
    upload(client, officer, name="my evidence (final).txt")
    assert any(p.name.endswith("_my_evidence__final_.txt") for p in UPLOADS.iterdir())


def test_upload_rejects_disallowed_type(client, officer):
    assert upload(client, officer, name="virus.exe", content=b"MZ").status_code == 400


def test_upload_rejects_files_over_10mb(client, officer):
    big = b"x" * (10 * 1024 * 1024 + 1)
    assert upload(client, officer, name="big.txt", content=big).status_code == 413


def test_upload_unknown_bidder_or_tender(client, officer):
    assert upload(client, officer, bidder=999).status_code == 404
    assert upload(client, officer, tender=999).status_code == 404


def test_upload_requires_login_and_write_role(client, auditor):
    assert upload(client, {}).status_code == 401
    assert upload(client, auditor).status_code == 403


# --------------------------------------------------------------- decisions
def decide(client, headers, **over):
    body = {"tender_id": 1, "bidder_id": 1, "decision": "APPROVE", "reason": "All documents verified"}
    body.update(over)
    return client.post("/api/decisions", headers=headers, json=body)


def test_officer_can_record_decision_and_it_is_listed(client, officer):
    r = decide(client, officer, decision="REVIEW", reason="Needs second look")
    assert r.status_code == 200 and r.json()["officer"] == "officer@bidguard.demo"
    listed = client.get("/api/decisions/1", headers=officer).json()
    assert any(d["decision"] == "REVIEW" and d["reason"] == "Needs second look" for d in listed)


def test_admin_can_record_decision(client, admin):
    assert decide(client, admin).status_code == 200


def test_auditor_cannot_record_decision(client, auditor):
    assert decide(client, auditor).status_code == 403


def test_invalid_decision_value(client, officer):
    assert decide(client, officer, decision="MAYBE").status_code == 400


def test_decision_requires_reason(client, officer):
    assert decide(client, officer, reason="   ").status_code == 400


def test_decision_for_unknown_tender_or_bidder(client, officer):
    assert decide(client, officer, tender_id=999).status_code == 404
    assert decide(client, officer, bidder_id=999).status_code == 404


# ---------------------------------------------------------- report + audit
def test_report_is_a_pdf(client, officer):
    r = client.get("/api/reports/1/1", headers=officer)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_report_unknown_ids(client, officer):
    assert client.get("/api/reports/999/1", headers=officer).status_code == 404


def test_audit_trail_records_key_events(client, officer):
    # perform one of each audited action here so this test does not depend on test order
    client.get("/api/compliance/1/1", headers=officer)
    verify(client, officer, 1, "GST", "33AAECA1234F1Z5")
    upload(client, officer, name="audit-check.txt")
    decide(client, officer, reason="audit check")
    actions = {a["action"] for a in client.get("/api/audit", headers=officer).json()}
    assert {"LOGIN", "COMPLIANCE_RUN", "GOVERNMENT_VERIFICATION", "DOCUMENT_UPLOAD", "FINAL_DECISION"} <= actions
