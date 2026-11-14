import math

import pytest

from coach import analytics as A
from coach.data import customers

CIDS = [c["id"] for c in customers()]


def test_dataset_has_customers():
    assert {"aino", "mikko", "liisa"} <= set(CIDS)


@pytest.mark.parametrize("cid", CIDS)
def test_baskets_add_up(cid):
    b = A.basket_summary(cid, "last_3_months")
    assert [x["id"] for x in b["baskets"]] == ["regular", "irregular", "everyday"]
    assert math.isclose(sum(x["total"] for x in b["baskets"]), b["spending_total"], abs_tol=0.05)
    assert math.isclose(sum(x["share_of_spending"] for x in b["baskets"]), 100, abs_tol=0.2)


@pytest.mark.parametrize("cid", CIDS)
def test_every_spend_has_a_basket(cid):
    sp = A.spending(cid)
    assert len(sp) > 0
    assert set(sp["basket"]) <= {"regular", "irregular", "everyday"}
    assert (sp["spend"] > 0).all()


def test_taxi_last_month_matches_transactions():
    r = A.query("aino", period="last_month", category="Taxi", group_by="none")
    assert r["period"] == "October 2026"
    assert math.isclose(r["total"], sum(t["amount"] for t in r["transactions"]), abs_tol=0.01)


def test_comma_separated_categories_combine():
    a = A.query("aino", period="last_3_months", category="Restaurants", group_by="none")["total"]
    b = A.query("aino", period="last_3_months", category="Takeaway", group_by="none")["total"]
    both = A.query("aino", period="last_3_months", category="Restaurants, Takeaway", group_by="none")["total"]
    assert math.isclose(both, a + b, abs_tol=0.05)


@pytest.mark.parametrize("cid", CIDS)
def test_safe_to_spend_is_consistent(cid):
    s = A.safe_to_spend(cid)
    expected = (s["cycle_income"] - s["spent_so_far"] - s["upcoming_bills"] - s["essentials_reserve"]
                - s["irregular_buffer"] - s["savings_goal_left"])
    assert math.isclose(s["safe_until_payday"], expected, abs_tol=0.05)
    assert s["safe_this_week"] >= 0
    assert s["status"] in {"comfortable", "tight", "over"}
    assert s["next_payday"] > s["today"] >= s["last_payday"]


def test_what_if_math():
    r = A.what_if("aino", 20, category="Restaurants", annual_return=0.0)
    assert math.isclose(r["monthly_saving"], r["monthly_now"] * 0.2, abs_tol=0.01)
    assert math.isclose(r["yearly_saving"], r["monthly_saving"] * 12, abs_tol=0.05)
    ten = next(p for p in r["projection"] if p["years"] == 10)
    assert math.isclose(ten["with_interest"], ten["saved"], abs_tol=0.5)  # 0 % return = no growth


def test_compound_interest_grows():
    r = A.what_if("aino", 20, category="Restaurants", annual_return=0.03)
    ten = next(p for p in r["projection"] if p["years"] == 10)
    assert ten["with_interest"] > ten["saved"]


@pytest.mark.parametrize("cid", CIDS)
def test_profile_and_benchmark(cid):
    p = A.spender_profile(cid)
    assert p["archetype"] and len(p["traits"]) >= 4
    b = A.benchmark(cid)
    assert math.isclose(sum(g["you_share"] for g in b["groups"]), 100, abs_tol=0.5)
    assert "stat.fi" in b["source"]["url"]


def test_recurring_finds_rent_not_restaurants():
    names = {r["merchant"] for r in A.recurring("aino")}
    assert "Kojamo Lumo-kodit" in names
    assert not names & {"Rax", "Hesburger", "Wolt"}


def test_reclassify_moves_category():
    before = {r["category"]: r["basket"] for _, r in A.spending("aino").iterrows()}
    assert before["Gym & sports"] == "everyday"
    A.reclassify("aino", "regular", category="Gym & sports")
    after = A.spending("aino")
    assert set(after[after["category"] == "Gym & sports"]["basket"]) == {"regular"}


def test_bad_inputs_raise_value_error():
    with pytest.raises(ValueError):
        A.resolve_period("next_century")
    with pytest.raises(ValueError):
        A.set_override("aino", "category:Taxi", "luxury")


def test_clean_handles_nan():
    assert A.clean({"a": float("nan"), "b": [1.5]}) == {"a": None, "b": [1.5]}
