"""Shared test setup.

The environment variables below MUST be set before `app.main` is imported,
because importing it creates the database and seeds the demo data. Pointing
BIDGUARD_DATA_DIR at a temporary folder keeps tests away from your real
data/bidguard.db and your real uploads.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["BIDGUARD_DATA_DIR"] = tempfile.mkdtemp(prefix="bidguard_test_")
os.environ["BIDGUARD_SECRET"] = "unit-test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="session")
def officer_login(client):
    return _login(client, "officer@bidguard.demo", "Officer@123")


@pytest.fixture(scope="session")
def officer(officer_login):
    return {"Authorization": f"Bearer {officer_login['access_token']}"}


@pytest.fixture(scope="session")
def auditor(client):
    data = _login(client, "auditor@bidguard.demo", "Auditor@123")
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    data = _login(client, "admin@bidguard.demo", "Admin@123")
    return {"Authorization": f"Bearer {data['access_token']}"}
