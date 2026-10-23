"""Unit tests for the rule engine (app/rules.py). No server or database needed."""
from types import SimpleNamespace

import pytest

from app.rules import check_rule, evaluate, extract_requirements, risk_level


def bidder(**kw):
    base = dict(gstin="33AAECA1234F1Z5", pan="AAECA1234F", turnover=0, experience_years=0,
                local_content=0, iso=False, startup=False, blacklisted=False)
    base.update(kw)
    return SimpleNamespace(**base)


def req(rule, weight=10, rid=1):
    return SimpleNamespace(id=rid, name=rule, category="TEST", rule=rule, weight=weight, evidence_hint="")


# ------------------------------------------------------------- check_rule
@pytest.mark.parametrize("turnover,expected", [(19_999_999, False), (20_000_000, True), (42_000_000, True)])
def test_turnover_boundary(turnover, expected):
    assert check_rule("turnover>=20000000", bidder(turnover=turnover)) is expected


@pytest.mark.parametrize("years,expected", [(2.9, False), (3, True), (8, True)])
def test_experience_boundary(years, expected):
    assert check_rule("experience>=3", bidder(experience_years=years)) is expected


def test_local_content_boundary():
    assert check_rule("local_content>=40", bidder(local_content=39.9)) is False
    assert check_rule("local_content>=40", bidder(local_content=40)) is True


def test_numeric_rules_work_for_any_number():
    # the rule string is parsed, so new thresholds need no code change
    assert check_rule("turnover>=500", bidder(turnover=500)) is True
    assert check_rule("experience>=12", bidder(experience_years=11)) is False


def test_gst_and_pan_validity_use_length():
    assert check_rule("gst_valid", bidder(gstin="33AAECA1234F1Z5")) is True      # 15 chars
    assert check_rule("gst_valid", bidder(gstin="33AAECA1234F1Z")) is False      # 14 chars
    assert check_rule("gst_valid", bidder(gstin="")) is False
    assert check_rule("pan_valid", bidder(pan="AAECA1234F")) is True             # 10 chars
    assert check_rule("pan_valid", bidder(pan="AAECA123")) is False


def test_boolean_rules():
    assert check_rule("iso", bidder(iso=True)) is True
    assert check_rule("iso", bidder(iso=False)) is False
    assert check_rule("startup", bidder(startup=True)) is True
    assert check_rule("not_blacklisted", bidder(blacklisted=True)) is False
    assert check_rule("not_blacklisted", bidder(blacklisted=False)) is True


@pytest.mark.parametrize("rule", ["", None, "banana", "turnover>20000000", "turnover>=abc"])
def test_unknown_rule_returns_none(rule):
    assert check_rule(rule, bidder()) is None


# ------------------------------------------------------------- risk_level
@pytest.mark.parametrize("score,level", [
    (0, "LOW"), (34, "LOW"), (35, "MEDIUM"), (59, "MEDIUM"),
    (60, "HIGH"), (79, "HIGH"), (80, "CRITICAL"), (100, "CRITICAL"),
])
def test_risk_level_boundaries(score, level):
    assert risk_level(score) == level


# --------------------------------------------------------------- evaluate
def test_all_requirements_pass():
    b = bidder(turnover=30_000_000, experience_years=5, iso=True)
    r = evaluate([req("turnover>=20000000", rid=1), req("experience>=3", rid=2), req("iso", rid=3)], b)
    assert r["score"] == 100.0
    assert r["risk_score"] == 0 and r["risk_level"] == "LOW"
    assert r["passed"] == 3 and r["failed"] == 0
    assert r["disqualified"] is False


def test_score_is_weighted_not_a_simple_count():
    # passes the 25-weight rule, fails the 75-weight rule -> 25%, not 50%
    b = bidder(iso=True, startup=False)
    r = evaluate([req("iso", weight=25, rid=1), req("startup", weight=75, rid=2)], b)
    assert r["score"] == 25.0


def test_risk_formula_without_penalties():
    # score 75 -> (100-75)*0.8 = 20
    b = bidder(iso=True)
    r = evaluate([req("iso", weight=75, rid=1), req("startup", weight=25, rid=2)], b)
    assert r["score"] == 75.0 and r["risk_score"] == 20


def test_blacklisted_bidder_gets_penalty_and_is_disqualified():
    b = bidder(blacklisted=True, iso=True)
    r = evaluate([req("not_blacklisted", weight=20, rid=1), req("iso", weight=80, rid=2)], b)
    assert r["score"] == 80.0                      # high score alone...
    assert r["risk_score"] == round(20 * 0.8 + 35)  # ...but +35 blacklist penalty
    assert r["disqualified"] is True


def test_three_or_more_failures_add_ten_points():
    b = bidder()
    two = evaluate([req("iso", rid=1), req("startup", rid=2), req("gst_valid", rid=3)], b)
    three = evaluate([req("iso", rid=1), req("startup", rid=2), req("turnover>=1", rid=3)], b)
    assert two["failed"] == 2 and three["failed"] == 3
    assert three["risk_score"] - round((100 - three["score"]) * 0.8) == 10
    assert two["risk_score"] == round((100 - two["score"]) * 0.8)


def test_risk_is_capped_at_100():
    b = bidder(blacklisted=True, gstin="", pan="")
    reqs = [req("not_blacklisted", rid=1), req("iso", rid=2), req("startup", rid=3), req("gst_valid", rid=4)]
    assert evaluate(reqs, b)["risk_score"] == 100


def test_no_requirements_does_not_crash():
    r = evaluate([], bidder())
    assert r["score"] == 0 and r["results"] == [] and r["passed"] == 0 and r["failed"] == 0


def test_unknown_rule_is_treated_as_fail_with_clear_message():
    r = evaluate([req("mystery_rule", rid=1)], bidder())
    assert r["results"][0]["status"] == "FAIL"
    assert "not recognised" in r["results"][0]["explanation"]


def test_result_rows_carry_requirement_details():
    row = evaluate([req("iso", weight=15, rid=7)], bidder(iso=True))["results"][0]
    assert row["requirement_id"] == 7 and row["status"] == "PASS" and row["weight"] == 15


# ------------------------------------------------------------- extraction
def rules_of(text):
    return {x["rule"] for x in extract_requirements(text)}


def test_extracts_turnover_in_crore():
    assert "turnover>=20000000" in rules_of("Bidder must have annual turnover of ₹2 Cr.")
    assert "turnover>=35000000" in rules_of("Minimum average turnover: Rs. 3.5 crore")


def test_extracts_turnover_in_lakh():
    assert "turnover>=5000000" in rules_of("Annual turnover of at least 50 lakh is required")


def test_turnover_word_without_amount_extracts_nothing():
    assert not any(r.startswith("turnover") for r in rules_of("Turnover will be verified by the officer"))


def test_extracts_experience_both_phrasings():
    assert "experience>=3" in rules_of("Minimum 3 years experience in similar work")
    assert "experience>=5" in rules_of("Experience of at least 5 years is mandatory")
    assert "experience>=7" in rules_of("7+ years of relevant experience")


def test_experience_word_without_number_extracts_nothing():
    assert not any(r.startswith("experience") for r in rules_of("Relevant experience is preferred"))


def test_extracts_local_content_both_phrasings():
    assert "local_content>=40" in rules_of("Minimum 40% local content required")
    assert "local_content>=50" in rules_of("Local content of at least 50% is mandatory")


def test_extracts_keyword_requirements():
    found = rules_of("Valid GST and PAN needed. ISO 9001 certified. Bidders must not be blacklisted. Startups preferred.")
    assert {"gst_valid", "pan_valid", "iso", "not_blacklisted", "startup"} <= found


def test_empty_or_irrelevant_text_gives_nothing():
    assert extract_requirements("") == []
    assert extract_requirements(None) == []
    assert extract_requirements("Supply of stationery items to the head office.") == []


def test_extracted_rules_are_understood_by_the_rule_engine():
    text = "Turnover of ₹2 Cr, 3 years experience, 40% local content, valid GST, not blacklisted"
    for item in extract_requirements(text):
        assert check_rule(item["rule"], bidder()) is not None, item
