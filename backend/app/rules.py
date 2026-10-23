"""BidGuard AI - rule engine.

Pure Python: no FastAPI, no database. Everything here takes plain objects
(anything with the right attributes) and returns plain dicts, which makes it
easy to unit test and easy to explain.

A requirement "rule" is a short string such as:
    turnover>=20000000   experience>=3   local_content>=40
    gst_valid   pan_valid   not_blacklisted   iso   startup
"""
import re

# rule name -> function(bidder) -> bool
BOOLEAN_RULES = {
    "gst_valid": lambda b: bool(b.gstin and len(b.gstin) >= 15),
    "pan_valid": lambda b: bool(b.pan and len(b.pan) >= 10),
    "not_blacklisted": lambda b: not b.blacklisted,
    "iso": lambda b: bool(b.iso),
    "startup": lambda b: bool(b.startup),
}

# "<field>>=<number>" rules, e.g. turnover>=20000000
NUMERIC_RULE = re.compile(r"^(turnover|experience|local_content)>=(\d+(?:\.\d+)?)$")
NUMERIC_FIELDS = {
    "turnover": "turnover",
    "experience": "experience_years",
    "local_content": "local_content",
}


def check_rule(rule, bidder):
    """Return True/False for a known rule, or None if the rule is not recognised."""
    if rule in BOOLEAN_RULES:
        return BOOLEAN_RULES[rule](bidder)
    m = NUMERIC_RULE.match(rule or "")
    if m:
        field, limit = m.group(1), float(m.group(2))
        return getattr(bidder, NUMERIC_FIELDS[field]) >= limit
    return None


def risk_level(risk_score):
    if risk_score >= 80:
        return "CRITICAL"
    if risk_score >= 60:
        return "HIGH"
    if risk_score >= 35:
        return "MEDIUM"
    return "LOW"


def evaluate(requirements, bidder):
    """Score one bidder against a list of requirements.

    compliance score = (sum of weights of passed rules / sum of all weights) * 100
    risk score       = (100 - score) * 0.8
                       + 35 if the bidder is blacklisted
                       + 10 if 3 or more requirements failed
                       (capped at 100)
    An unrecognised rule counts as FAIL (safe default).
    A failed "not_blacklisted" rule sets disqualified=True: a high weighted
    score must never let a blacklisted bidder count as a passing bid.
    """
    rows, earned, total, disqualified = [], 0, 0, False
    for r in requirements:
        ok = check_rule(r.rule, bidder)
        if r.rule == "not_blacklisted" and not ok:
            disqualified = True
        status = "PASS" if ok else "FAIL"
        if ok:
            earned += r.weight
        total += r.weight
        rows.append({
            "requirement_id": r.id,
            "name": r.name,
            "category": r.category,
            "status": status,
            "weight": r.weight,
            "evidence": r.evidence_hint,
            "explanation": f"Rule {r.rule} evaluated against bidder master data."
            if ok is not None else f"Rule {r.rule} is not recognised and was treated as FAIL.",
        })
    score = round(earned / total * 100 if total else 0, 1)
    fails = sum(1 for x in rows if x["status"] == "FAIL")
    risk = min(100, round((100 - score) * 0.8 + (35 if bidder.blacklisted else 0) + (10 if fails >= 3 else 0)))
    return {
        "score": score,
        "risk_score": risk,
        "risk_level": risk_level(risk),
        "results": rows,
        "failed": fails,
        "passed": len(rows) - fails,
        "disqualified": disqualified,
    }


# ---------------------------------------------------------------- extraction
_CRORE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:cr|crore|crores)\b", re.I)
_LAKH = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lakhs|lac|lacs)\b", re.I)
_EXPERIENCE = re.compile(
    r"(\d+)\s*\+?\s*(?:years?|yrs?)\b[^.\n]{0,40}experience|experience[^.\n]{0,40}?(\d+)\s*\+?\s*(?:years?|yrs?)\b",
    re.I,
)
_LOCAL = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*local\s+content|local\s+content[^0-9]{0,30}(\d+(?:\.\d+)?)\s*%", re.I)


def _number(x):
    return int(x) if float(x).is_integer() else float(x)


def extract_requirements(text):
    """Detect compliance requirements from free tender text using regex/keywords.

    This is deterministic, rule-based extraction (not machine learning).
    Returns a list of {name, category, rule} dicts using the same rule
    strings that evaluate() understands.
    """
    text = text or ""
    low = text.lower()
    found = []

    if "turnover" in low:
        amount = None
        m = _CRORE.search(text)
        if m:
            amount = float(m.group(1)) * 10_000_000
        else:
            m = _LAKH.search(text)
            if m:
                amount = float(m.group(1)) * 100_000
        if amount:
            found.append({"name": f"Minimum annual turnover {_number(amount)}", "category": "FINANCIAL",
                          "rule": f"turnover>={_number(amount)}"})

    m = _EXPERIENCE.search(text)
    if m:
        years = m.group(1) or m.group(2)
        found.append({"name": f"Minimum {years} years experience", "category": "EXPERIENCE",
                      "rule": f"experience>={years}"})

    m = _LOCAL.search(text)
    if m:
        pct = _number(m.group(1) or m.group(2))
        found.append({"name": f"Minimum {pct}% local content", "category": "MAKE_IN_INDIA",
                      "rule": f"local_content>={pct}"})

    if re.search(r"\bgst", low):
        found.append({"name": "Valid GST registration", "category": "STATUTORY", "rule": "gst_valid"})
    if re.search(r"\bpan\b", low):
        found.append({"name": "Valid PAN", "category": "STATUTORY", "rule": "pan_valid"})
    if re.search(r"blacklist|debar", low):
        found.append({"name": "Not blacklisted", "category": "INTEGRITY", "rule": "not_blacklisted"})
    if re.search(r"\biso\b", low):
        found.append({"name": "ISO certification", "category": "QUALITY", "rule": "iso"})
    if re.search(r"start-?up", low):
        found.append({"name": "Startup preference", "category": "STARTUP", "rule": "startup"})
    return found
