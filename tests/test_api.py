import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health_and_status():
    assert client.get("/api/health").json()["status"] == "ok"
    s = client.get("/api/status").json()
    assert s["provider"] == "offline" and s["ai"] is False


@pytest.mark.parametrize("path", [
    "/api/customers", "/api/aino/overview", "/api/aino/baskets", "/api/aino/trend",
    "/api/aino/explore?group_by=weekday", "/api/mikko/explore?group_by=source_bank&other_banks=false",
    "/api/aino/transactions?limit=5", "/api/aino/whatif?category=Restaurants&reduce_pct=30",
    "/api/aino/categories", "/", "/app.js", "/style.css", "/charts.js",
])
def test_endpoints_ok(path):
    assert client.get(path).status_code == 200


def test_unknown_customer_is_404():
    assert client.get("/api/nobody/overview").status_code == 404


def test_bad_period_is_400_not_500():
    r = client.get("/api/aino/baskets?period=next_century")
    assert r.status_code == 400 and "period" in r.json()["detail"]


@pytest.mark.parametrize("body", [
    {"customer_id": "aino", "message": ""},
    {"customer_id": "aino", "message": "x" * 1001},
    {"customer_id": "aino"},
])
def test_chat_validates_input(body):
    assert client.post("/api/chat", json=body).status_code == 422


def test_reclassify_rejects_unknown_basket():
    r = client.post("/api/aino/reclassify", json={"basket": "luxury", "category": "Taxi"})
    assert r.status_code == 422


@pytest.mark.parametrize("q,expect", [
    ("How much did I spend on taxis last month?", "41.31"),
    ("What kind of spender am I?", "Small-Ticket"),
    ("What is safe for me to spend this week?", "this week"),
    ("How much could I save if I reduced dining out by 20%?", "/month"),
])
def test_offline_coach_answers_challenge_questions(q, expect):
    r = client.post("/api/chat", json={"customer_id": "aino", "message": q}).json()
    assert r["engine"] == "offline"
    assert expect in r["text"]
    assert r["session_id"]


def test_chat_response_escapes_nothing_dangerous_from_merchants():
    # merchant text is data; the API returns plain strings and the UI escapes them
    r = client.get("/api/aino/transactions?limit=3").json()
    assert all(isinstance(t["merchant"], str) for t in r)
