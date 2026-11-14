"""Deterministic money analytics. The AI never invents numbers: every figure it
speaks comes from one of these functions (exposed to the model as tools)."""
from __future__ import annotations

import json
import math
import re
from datetime import timedelta

import numpy as np
import pandas as pd

from .benchmarks import FINLAND_MONTHLY_PER_UNIT, FINLAND_SHARES, SOURCE, coicop_group
from .data import DATA_DIR, customer_df, today

# ------------------------------------------------------------------ baskets
REGULAR, IRREGULAR, SLIP = "regular", "irregular", "everyday"
BASKETS = {
    REGULAR: {"label": "Fixed essentials", "emoji": "",
              "teach": "Necessary costs that recur every month at a predictable amount, such as rent, electricity, "
                       "insurance and groceries. They form your baseline cost of living and should be budgeted first."},
    IRREGULAR: {"label": "Irregular essentials", "emoji": "",
                "teach": "Necessary but unpredictable costs, such as dental care, appliance repairs or a passport. "
                         "They occur every year, so setting aside a fixed amount each month (a sinking fund) "
                         "prevents them from becoming emergencies."},
    SLIP: {"label": "Everyday spending", "emoji": "",
           "teach": "Small, frequent and optional purchases, such as coffee, takeaway, taxis and subscriptions. "
                    "Individually minor, together they are often the most effective area to adjust."},
}

CATEGORY_BASKET = {
    "Housing": REGULAR, "Utilities": REGULAR, "Phone & internet": REGULAR, "Insurance": REGULAR,
    "Childcare": REGULAR, "Public transport": REGULAR, "Groceries": REGULAR, "Fuel": REGULAR, "Loan": REGULAR,
    "Health": IRREGULAR, "Home & appliances": IRREGULAR, "Electronics": IRREGULAR, "Fees & taxes": IRREGULAR,
    "Car repair": IRREGULAR,
    "Coffee & snacks": SLIP, "Restaurants": SLIP, "Takeaway & delivery": SLIP, "Taxi": SLIP, "Alcohol": SLIP,
    "Entertainment": SLIP, "Shopping": SLIP, "Travel": SLIP, "Subscriptions": SLIP, "Gym & sports": SLIP,
}
# keyword fallback for unfamiliar category names in the official dataset
KEYWORDS = [
    (REGULAR, r"rent|vuokra|mortgage|laina|loan|electric|sähkö|energy|water|insur|vakuut|phone|internet|"
              r"grocer|ruoka|päivä|daycare|childcare|transport pass|utilit"),
    (IRREGULAR, r"health|terve|dental|hammas|doctor|lääkä|repair|korjaus|appliance|kodinkone|tax|vero|fee|"
                r"electronic|optic"),
    (SLIP, r"coffee|kahvi|cafe|restaurant|ravintola|takeaway|wolt|foodora|taxi|taksi|alcohol|alko|bar|"
           r"entertain|shop|cloth|subscript|stream|game|travel|matka|gym"),
]
SMALL_STORES = re.compile(r"alepa|sale|k-market|r-kioski|kiosk", re.I)
EXCLUDED = {"Income", "Savings transfer"}

OVERRIDES_FILE = DATA_DIR / "overrides.json"


def _load_overrides() -> dict:
    try:
        return json.loads(OVERRIDES_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def set_override(customer_id: str, key: str, basket: str) -> dict:
    """key is 'category:<name>' or 'merchant:<name>'."""
    if basket not in BASKETS:
        raise ValueError(f"basket must be one of {list(BASKETS)}")
    data = _load_overrides()
    data.setdefault(customer_id, {})[key] = basket
    _CACHE.clear()
    OVERRIDES_FILE.parent.mkdir(exist_ok=True)
    OVERRIDES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    return data[customer_id]


def _basket_for(row, recurring_merchants: set, ov: dict) -> tuple[str, str]:
    m, c, a = row["merchant"], row["category"], -row["amount"]
    if f"merchant:{m}" in ov:
        return ov[f"merchant:{m}"], "You moved this merchant here"
    if f"category:{c}" in ov:
        return ov[f"category:{c}"], "You moved this category here"
    if c == "Groceries" and a < 15 and SMALL_STORES.search(m):
        return SLIP, "Small top-up at a convenience store - adds up quietly"
    if c in ("Subscriptions", "Gym & sports"):
        return SLIP, "Recurring, but optional - a choice you renew every month"
    if c in CATEGORY_BASKET:
        return CATEGORY_BASKET[c], f"{c} is usually {BASKETS[CATEGORY_BASKET[c]]['label'].lower()}"
    low = f"{c} {m}".lower()
    for basket, pat in KEYWORDS:
        if re.search(pat, low):
            return basket, f"Matched '{c}' to {BASKETS[basket]['label'].lower()}"
    if m in recurring_merchants:
        return REGULAR, "Same merchant, similar amount every month"
    if a >= 150:
        return IRREGULAR, "Large one-off payment"
    return SLIP, "Small optional purchase"


_CACHE: dict = {}


def spending(customer_id: str, include_other_banks: bool = True) -> pd.DataFrame:
    """Outgoing spending (positive 'spend' column) with basket labels. Cached;
    the cache is cleared whenever the user re-classifies something."""
    key = ("spending", customer_id, include_other_banks)
    if key not in _CACHE:
        _CACHE[key] = _spending(customer_id, include_other_banks)
    return _CACHE[key].copy()


def _spending(customer_id: str, include_other_banks: bool) -> pd.DataFrame:
    df = customer_df(customer_id, include_other_banks)
    out = df[(df["amount"] < 0) & (~df["category"].isin(EXCLUDED))].copy()
    out["spend"] = -out["amount"]
    rec = {r["merchant"] for r in recurring(customer_id, df=df)}
    ov = _load_overrides().get(customer_id, {})
    labels = out.apply(lambda r: _basket_for(r, rec, ov), axis=1, result_type="expand")
    out["basket"], out["basket_reason"] = (labels[0], labels[1]) if len(out) else ("", "")
    return out


def income(customer_id: str, include_other_banks: bool = True) -> pd.DataFrame:
    df = customer_df(customer_id, include_other_banks)
    return df[(df["amount"] > 0) & (df["category"].isin({"Income"}) | (df["category"] == "Other"))]


# ------------------------------------------------------------------ periods
def resolve_period(period: str | None, start: str | None = None, end: str | None = None):
    t = today()
    if start or end:
        return (pd.Timestamp(start) if start else pd.Timestamp("1900-01-01"),
                pd.Timestamp(end) if end else t, f"{start or 'start'} – {end or 'today'}")
    p = (period or "last_3_months").lower().replace(" ", "_")
    som = t.replace(day=1)
    if p == "this_month":
        return som, t, som.strftime("%B %Y") + " (so far)"
    if p == "last_month":
        s = (som - timedelta(days=1)).replace(day=1)
        return s, som - timedelta(days=1), s.strftime("%B %Y")
    if p == "this_week":
        s = t - timedelta(days=t.weekday())
        return s, t, "this week"
    if p == "last_week":
        s = t - timedelta(days=t.weekday() + 7)
        return s, s + timedelta(days=6), "last week"
    if p in ("last_7_days", "last_30_days", "last_90_days"):
        n = int(p.split("_")[1])
        return t - timedelta(days=n - 1), t, f"last {n} days"
    if p in ("last_3_months", "last_6_months", "last_12_months"):
        n = int(p.split("_")[1])
        s = (som - pd.DateOffset(months=n)).normalize()
        return s, som - timedelta(days=1), f"last {n} full months"
    if p in ("this_year", "ytd"):
        s = t.replace(month=1, day=1)
        return s, t, f"{t.year} so far"
    if p == "all":
        return pd.Timestamp("1900-01-01"), t, "all time"
    if re.fullmatch(r"\d{4}-\d{2}", p):
        s = pd.Timestamp(p + "-01")
        return s, s + pd.offsets.MonthEnd(0), s.strftime("%B %Y")
    raise ValueError(f"unknown period '{period}'")


def _months_in(s, e) -> float:
    return max((e - s).days + 1, 1) / 30.44


def _r(x) -> float:
    return round(float(x), 2)


# ------------------------------------------------------------------ queries
GROUPS = {"category", "merchant", "basket", "month", "week", "weekday", "source_bank", "none"}


def _any(col: pd.Series, terms: str) -> pd.Series:
    """Case-insensitive substring match; comma-separated terms are OR-ed
    ('Restaurants, Takeaway' matches both)."""
    parts = [t.strip() for t in str(terms).split(",") if t.strip()]
    mask = pd.Series(False, index=col.index)
    for t in parts:
        mask |= col.str.contains(t, case=False, regex=False)
    return mask


def query(customer_id: str, period: str | None = None, start: str | None = None, end: str | None = None,
          category: str | None = None, merchant: str | None = None, basket: str | None = None,
          min_amount: float | None = None, max_amount: float | None = None,
          group_by: str = "category", top: int = 12, include_other_banks: bool = True) -> dict:
    """Free-form exploration of the user's own spending (the MyData tool)."""
    s, e, label = resolve_period(period, start, end)
    df = spending(customer_id, include_other_banks)
    df = df[(df["date"] >= s) & (df["date"] <= e)]
    if category:
        df = df[_any(df["category"], category)]
    if merchant:
        df = df[_any(df["merchant"], merchant)]
    if basket:
        df = df[df["basket"] == basket]
    if min_amount is not None:
        df = df[df["spend"] >= min_amount]
    if max_amount is not None:
        df = df[df["spend"] <= max_amount]

    res = {"period": label, "from": str(s.date()), "to": str(e.date()), "total": _r(df["spend"].sum()),
           "count": int(len(df)), "avg_ticket": _r(df["spend"].mean()) if len(df) else 0.0,
           "filters": {k: v for k, v in dict(category=category, merchant=merchant, basket=basket,
                                             min_amount=min_amount, max_amount=max_amount).items() if v is not None}}
    gb = group_by if group_by in GROUPS else "category"
    if gb != "none" and len(df):
        key = {"month": df["date"].dt.strftime("%Y-%m"),
               "week": df["date"].dt.strftime("%G-W%V"),
               "weekday": df["date"].dt.day_name().str[:3]}.get(gb, df.get(gb))
        g = df.groupby(key)["spend"].agg(["sum", "count"])
        if gb == "weekday":
            g = g.reindex(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]).fillna(0)
        elif gb not in ("month", "week"):
            g = g.sort_values("sum", ascending=False).head(top)
        res["groups"] = [{"name": str(k), "total": _r(v["sum"]), "count": int(v["count"])} for k, v in g.iterrows()]
        res["chart"] = {"type": "line" if gb in ("month", "week") else "bar",
                        "title": f"Spending by {gb}, {label}",
                        "labels": [x["name"] for x in res["groups"]],
                        "values": [x["total"] for x in res["groups"]], "unit": "€"}
    if len(df) <= 15:
        res["transactions"] = [{"date": str(r["date"].date()), "merchant": r["merchant"], "amount": _r(r["spend"]),
                                "category": r["category"]} for _, r in df.sort_values("date").iterrows()]
    return res


def recurring(customer_id: str, df: pd.DataFrame | None = None) -> list[dict]:
    """Merchants charged in >=3 different months at a stable amount."""
    if df is None:
        key = ("recurring", customer_id)
        if key not in _CACHE:
            _CACHE[key] = _recurring(customer_df(customer_id))
        return [dict(r) for r in _CACHE[key]]
    return _recurring(df)


def _recurring(df: pd.DataFrame) -> list[dict]:
    out = df[(df["amount"] < 0) & (df["category"] != "Savings transfer")].copy()
    out["ym"] = out["date"].dt.to_period("M")
    span = max(out["ym"].nunique(), 1)
    recent = out["date"].max() - pd.Timedelta(days=45)
    res = []
    for m, g in out.groupby("merchant"):
        per_month = g.groupby("ym")["amount"].sum().abs()
        if per_month.size < 3 or g.groupby("ym").size().median() > 1.5:
            continue
        if per_month.size < 0.6 * span or g["date"].max() < recent:
            continue
        cv = per_month.std() / per_month.mean() if per_month.mean() else 9
        if cv > 0.35:
            continue
        res.append({"merchant": m, "category": g["category"].mode().iat[0], "monthly": _r(per_month.median()),
                    "day_of_month": int(g["date"].dt.day.median()), "months_seen": int(per_month.size),
                    "last_paid": str(g["date"].max().date())})
    return sorted(res, key=lambda r: -r["monthly"])


def subscriptions(customer_id: str) -> dict:
    subs = [r for r in recurring(customer_id) if r["category"] in ("Subscriptions", "Gym & sports")]
    total = sum(r["monthly"] for r in subs)
    return {"subscriptions": subs, "monthly_total": _r(total), "yearly_total": _r(total * 12),
            "tip": "Subscriptions are 'set and forget' spending. Ask for each: did I use it in the last 2 weeks?"}


# ------------------------------------------------------------------ baskets
def basket_summary(customer_id: str, period: str | None = "last_3_months", include_other_banks: bool = True) -> dict:
    s, e, label = resolve_period(period)
    df = spending(customer_id, include_other_banks)
    df = df[(df["date"] >= s) & (df["date"] <= e)]
    inc = income(customer_id, include_other_banks)
    inc_total = inc[(inc["date"] >= s) & (inc["date"] <= e)]["amount"].sum()
    months = _months_in(s, e)
    total = df["spend"].sum()
    baskets = []
    for b, meta in BASKETS.items():
        d = df[df["basket"] == b]
        cats = d.groupby("category")["spend"].sum().sort_values(ascending=False)
        baskets.append({"id": b, "label": meta["label"], "emoji": meta["emoji"], "teach": meta["teach"],
                        "total": _r(d["spend"].sum()), "monthly_avg": _r(d["spend"].sum() / months),
                        "share_of_spending": _r(d["spend"].sum() / total * 100) if total else 0,
                        "share_of_income": _r(d["spend"].sum() / inc_total * 100) if inc_total else None,
                        "count": int(len(d)),
                        "top_categories": [{"name": k, "total": _r(v), "monthly_avg": _r(v / months)}
                                           for k, v in cats.head(6).items()],
                        "examples": [{"merchant": r["merchant"], "amount": _r(r["spend"]), "date": str(r["date"].date()),
                                      "why": r["basket_reason"]}
                                     for _, r in d.sort_values("spend", ascending=False)
                                     .drop_duplicates("merchant").head(3).iterrows()]})
    return {"period": label, "months": round(months, 1), "income_total": _r(inc_total),
            "income_monthly_avg": _r(inc_total / months), "spending_total": _r(total),
            "spending_monthly_avg": _r(total / months),
            "left_over_monthly_avg": _r((inc_total - total) / months), "baskets": baskets,
            "chart": {"type": "donut", "title": f"Your three baskets, {label}",
                      "labels": [b["label"] for b in baskets], "values": [b["total"] for b in baskets], "unit": "€"}}


def reclassify(customer_id: str, basket: str, category: str | None = None, merchant: str | None = None) -> dict:
    if not (category or merchant):
        raise ValueError("give a category or merchant")
    key = f"merchant:{merchant}" if merchant else f"category:{category}"
    set_override(customer_id, key, basket)
    return {"ok": True, "moved": merchant or category, "to": BASKETS[basket]["label"]}


# ------------------------------------------------------------------ paydays & safe-to-spend
def _paydays(customer_id: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    t = today()
    inc = income(customer_id, include_other_banks=False)
    inc = inc[inc["amount"] >= 300]
    if inc.empty:
        last = t.replace(day=1)
    else:
        biggest = inc.loc[inc.groupby(inc["date"].dt.to_period("M"))["amount"].idxmax()]
        past = biggest[biggest["date"] <= t]
        last = past["date"].max() if len(past) else t.replace(day=1)
    nxt = last + pd.DateOffset(months=1)
    while nxt <= t:
        nxt += pd.DateOffset(months=1)
    return last.normalize(), nxt.normalize()


def safe_to_spend(customer_id: str, savings_rate: float = 0.10, include_other_banks: bool = False) -> dict:
    """How much can be spent on optional things until next payday without touching
    bills, essentials, the irregular buffer or the savings goal."""
    t = today()
    last, nxt = _paydays(customer_id)
    days_left = max((nxt - t).days, 1)
    cycle_days = max((nxt - last).days, 1)
    raw = customer_df(customer_id, include_other_banks)
    cyc = raw[(raw["date"] >= last) & (raw["date"] <= t)]
    cycle_income = cyc[cyc["amount"] > 0]["amount"].sum()
    sp = spending(customer_id, include_other_banks)
    spent = sp[(sp["date"] >= last) & (sp["date"] <= t)]["spend"].sum()
    saved = -cyc[cyc["category"] == "Savings transfer"]["amount"].sum()

    # bills not yet paid this cycle
    recs = recurring(customer_id, df=raw)
    paid = set(cyc["merchant"])
    upcoming = [r for r in recs
                if r["merchant"] not in paid and r["category"] not in ("Income", "Savings transfer")]
    bills = sum(r["monthly"] for r in upcoming)

    hist = sp[(sp["date"] < last) & (sp["date"] >= last - pd.DateOffset(months=6))]
    hmonths = max(_months_in(last - pd.DateOffset(months=6), last - timedelta(days=1)), 1)
    rec_merchants = {r["merchant"] for r in recs}
    variable_essentials = hist[(hist["basket"] == REGULAR) & (~hist["merchant"].isin(rec_merchants))]["spend"].sum() / hmonths
    essentials_left = variable_essentials / 30.44 * days_left
    irregular_monthly = hist[hist["basket"] == IRREGULAR]["spend"].sum() / hmonths
    irregular_buffer = irregular_monthly / 30.44 * days_left
    savings_goal = savings_rate * cycle_income
    savings_left = max(savings_goal - saved, 0)

    safe = cycle_income - spent - bills - essentials_left - irregular_buffer - savings_left
    per_day = safe / days_left
    week = per_day * min(7, days_left)
    # payday falls inside the coming week: add the typical daily allowance of the next cycle
    days_after = max(7 - days_left, 0)
    inc_hist = raw[(raw["amount"] > 0) & (raw["date"] < last + timedelta(days=1))
                   & (raw["date"] >= last - pd.DateOffset(months=3))]["amount"].sum() / 3
    rec_total = sum(r["monthly"] for r in recs)
    next_daily = max((inc_hist * (1 - savings_rate) - rec_total - variable_essentials - irregular_monthly) / 30.44, 0)
    if days_after:
        week = max(safe, 0) + next_daily * days_after
    slip_hist = hist[hist["basket"] == SLIP]["spend"].sum() / hmonths / 4.35
    status = "comfortable" if per_day > 0 and week >= slip_hist else ("tight" if per_day > 0 else "over")
    return {
        "today": str(t.date()), "last_payday": str(last.date()), "next_payday": str(nxt.date()), "days_left": days_left,
        "cycle_income": _r(cycle_income), "spent_so_far": _r(spent), "saved_so_far": _r(saved),
        "upcoming_bills": _r(bills), "upcoming_bill_list": [{"merchant": r["merchant"], "amount": r["monthly"],
                                                             "usual_day": r["day_of_month"]} for r in upcoming],
        "essentials_reserve": _r(essentials_left), "irregular_buffer": _r(irregular_buffer),
        "savings_goal_left": _r(savings_left), "savings_rate": savings_rate,
        "safe_until_payday": _r(safe), "safe_per_day": _r(per_day), "safe_this_week": _r(max(week, 0)),
        "week_includes_days_after_payday": days_after, "next_cycle_daily_estimate": _r(next_daily),
        "typical_weekly_everyday_spend": _r(slip_hist), "status": status,
        "method": "Income since payday minus what's spent, minus bills still due, a reserve for food & fuel, "
                  "a buffer for irregular costs and your savings goal, spread over the days to payday.",
        "chart": {"type": "waterfall", "title": "How your safe-to-spend is calculated",
                  "labels": ["Income this cycle", "Already spent", "Bills still due", "Food & essentials",
                             "Surprise buffer", "Savings goal", "Safe to spend"],
                  "values": [_r(cycle_income), -_r(spent), -_r(bills), -_r(essentials_left),
                             -_r(irregular_buffer), -_r(savings_left), _r(safe)], "unit": "€"},
    }


# ------------------------------------------------------------------ what-if
EQUIVALENTS = [(35, "a cinema night for two"), (120, "a month of HSL travel + Spotify"),
               (300, "a weekend cruise to Tallinn"), (800, "a new phone"), (1500, "a week in Southern Europe"),
               (3000, "a solid emergency fund for most young adults")]


def _future_value(monthly: float, years: float, annual_return: float) -> float:
    n, r = int(years * 12), annual_return / 12
    return monthly * n if r == 0 else monthly * ((1 + r) ** n - 1) / r


def what_if(customer_id: str, reduce_pct: float = 20, category: str | None = None, merchant: str | None = None,
            basket: str | None = None, extra_monthly: float | None = None, annual_return: float = 0.03,
            lookback_months: int = 3) -> dict:
    """Simulate cutting spending in a category/merchant/basket by a percentage
    (or redirecting a fixed monthly amount) and project the savings."""
    df = spending(customer_id)
    s, e, label = resolve_period(f"last_{lookback_months}_months" if lookback_months in (3, 6, 12) else "last_3_months")
    d = df[(df["date"] >= s) & (df["date"] <= e)]
    target = "your spending"
    if category:
        d = d[_any(d["category"], category)]
        target = category
    if merchant:
        d = d[_any(d["merchant"], merchant)]
        target = merchant
    if basket:
        d = d[d["basket"] == basket]
        target = BASKETS.get(basket, {}).get("label", basket)
    months = _months_in(s, e)
    monthly_now = d["spend"].sum() / months
    visits = len(d) / months
    ticket = d["spend"].mean() if len(d) else 0
    saving = extra_monthly if extra_monthly is not None else monthly_now * reduce_pct / 100
    proj = [{"years": y, "saved": _r(saving * 12 * y), "with_interest": _r(_future_value(saving, y, annual_return))}
            for y in (1, 3, 5, 10)]
    eq = [txt for amt, txt in EQUIVALENTS if saving * 12 >= amt][-1:] or ["a nice dinner out"]
    return {"target": target, "based_on": label, "monthly_now": _r(monthly_now), "times_per_month": round(visits, 1),
            "avg_ticket": _r(ticket), "reduce_pct": reduce_pct, "monthly_saving": _r(saving),
            "yearly_saving": _r(saving * 12), "fewer_purchases_per_month": round(saving / ticket, 1) if ticket else None,
            "annual_return_assumed": annual_return, "projection": proj,
            "that_buys_per_year": eq[0],
            "chart": {"type": "line", "title": f"If you save €{saving:.0f}/month ({annual_return * 100:.0f}% yearly return)",
                      "labels": ["Now"] + [f"{p['years']}y" for p in proj],
                      "values": [0] + [p["with_interest"] for p in proj], "unit": "€"}}


# ------------------------------------------------------------------ persona
ARCHETYPES = {
    "steady_planner": ("The Steady Planner", "🧭", "Bills covered, savings automatic, few surprises."),
    "small_ticket": ("The Small-Ticket Leaker", "☕", "Lots of little purchases that quietly add up."),
    "weekend": ("The Weekend Warrior", "🎉", "Weekdays are calm; Friday-to-Sunday is where the money goes."),
    "payday": ("The Payday Splurger", "💸", "Spending spikes in the days right after salary lands."),
    "subscriber": ("The Subscription Collector", "📺", "Many small monthly services on autopilot."),
    "experience": ("The Experience Seeker", "✈️", "Money goes to eating out, events and travel - memories over things."),
    "provider": ("The Family Provider", "", "Most money goes to the essentials that keep a household running."),
}


def spender_profile(customer_id: str) -> dict:
    s, e, _ = resolve_period("last_6_months")
    df = spending(customer_id)
    df = df[(df["date"] >= s) & (df["date"] <= e)]
    inc = income(customer_id)
    inc_m = inc[(inc["date"] >= s) & (inc["date"] <= e)]["amount"].sum() / 6
    total = df["spend"].sum()
    slip = df[df["basket"] == SLIP]
    small = slip[slip["spend"] < 15]
    last, _ = _paydays(customer_id)
    pday = last.day
    after_pay = slip[((slip["date"].dt.day - pday) % 31) < 5]["spend"].sum()
    wkend = slip[slip["date"].dt.weekday >= 4]["spend"].sum()
    subs = subscriptions(customer_id)
    exp = slip[slip["category"].isin(["Restaurants", "Travel", "Entertainment", "Takeaway & delivery"])]["spend"].sum()
    monthly = df.groupby(df["date"].dt.to_period("M"))["spend"].sum()
    f = {
        "everyday_share": slip["spend"].sum() / total if total else 0,
        "regular_share": df[df["basket"] == REGULAR]["spend"].sum() / total if total else 0,
        "small_purchases_per_week": len(small) / 26,
        "small_purchases_monthly": small["spend"].sum() / 6,
        "payday_share": after_pay / slip["spend"].sum() if len(slip) else 0,
        "weekend_share": wkend / slip["spend"].sum() if len(slip) else 0,
        "subscriptions": len(subs["subscriptions"]),
        "experience_share": exp / slip["spend"].sum() if len(slip) else 0,
        "savings_rate": (inc_m - total / 6) / inc_m if inc_m else 0,
        "volatility": float(monthly.std() / monthly.mean()) if len(monthly) > 1 else 0,
    }
    scores = {
        "steady_planner": (f["savings_rate"] - 0.10) * 4 + (0.30 - f["everyday_share"]) * 2,
        "small_ticket": (f["small_purchases_per_week"] - 4) / 4,
        "weekend": (f["weekend_share"] - 3 / 7) * 5,
        "payday": (f["payday_share"] - 5 / 30) * 5,
        "subscriber": (f["subscriptions"] - 3) / 2,
        "experience": (f["experience_share"] - 0.35) * 3,
        "provider": (f["regular_share"] - 0.62) * 6,
    }
    ranked = sorted(scores, key=scores.get, reverse=True)
    main, second = ranked[0], ranked[1]
    traits = [
        f"{f['everyday_share'] * 100:.0f}% of your spending is everyday/optional",
        f"{f['small_purchases_per_week']:.1f} purchases under €15 a week (≈ €{f['small_purchases_monthly']:.0f}/month)",
        f"{f['weekend_share'] * 100:.0f}% of optional spending happens Fri–Sun",
        f"{f['payday_share'] * 100:.0f}% of optional spending lands in the 5 days after payday",
        f"{f['subscriptions']} subscriptions (€{subs['monthly_total']:.0f}/month)",
        f"You keep about {f['savings_rate'] * 100:.0f}% of your income",
    ]
    return {"archetype": ARCHETYPES[main][0], "emoji": ARCHETYPES[main][1], "description": ARCHETYPES[main][2],
            "secondary": ARCHETYPES[second][0], "traits": traits,
            "features": {k: round(v, 3) for k, v in f.items()},
            "scores": {ARCHETYPES[k][0]: round(v, 2) for k, v in scores.items()}}


# ------------------------------------------------------------------ benchmarks
def benchmark(customer_id: str, household_units: float = 1.0) -> dict:
    """Compare monthly spending by consumption group with Finnish averages."""
    s, e, label = resolve_period("last_12_months")
    df = spending(customer_id)
    df = df[(df["date"] >= s) & (df["date"] <= e)]
    months = _months_in(s, e)
    df["group"] = df["category"].map(coicop_group)
    mine = df.groupby("group")["spend"].sum() / months
    total = mine.sum()
    rows = []
    for g, share in FINLAND_SHARES.items():
        you = float(mine.get(g, 0))
        fin = FINLAND_MONTHLY_PER_UNIT * share * household_units
        rows.append({"group": g, "you_monthly": _r(you), "you_share": _r(you / total * 100) if total else 0,
                     "finland_share": _r(share * 100), "finland_monthly": _r(fin),
                     "difference_pct_points": _r((you / total - share) * 100) if total else 0})
    rows.sort(key=lambda r: -abs(r["difference_pct_points"]))
    return {"period": label, "your_monthly_total": _r(total),
            "finland_monthly_per_consumption_unit": _r(FINLAND_MONTHLY_PER_UNIT * household_units),
            "groups": rows, "source": SOURCE,
            "note": "Shares compare where your money goes, which is fairer than raw euros across household sizes.",
            "chart": {"type": "compare", "title": "Your spending mix vs the Finnish average (% of spending)",
                      "labels": [r["group"] for r in rows[:7]],
                      "values": [r["you_share"] for r in rows[:7]],
                      "values2": [r["finland_share"] for r in rows[:7]], "unit": "%",
                      "series": ["You", "Finland avg"]}}


# ------------------------------------------------------------------ overview & insights
def overview(customer_id: str) -> dict:
    sts = safe_to_spend(customer_id)
    bs = basket_summary(customer_id, "last_3_months")
    prof = spender_profile(customer_id)
    t = today()
    som = t.replace(day=1)
    sp = spending(customer_id)
    this_m = sp[sp["date"] >= som]
    prev = sp[(sp["date"] >= som - pd.DateOffset(months=1)) & (sp["date"] < som - pd.DateOffset(months=1) + (t - som) + timedelta(days=1))]
    cat_now = this_m.groupby("category")["spend"].sum()
    cat_prev = prev.groupby("category")["spend"].sum()
    deltas = (cat_now - cat_prev.reindex(cat_now.index).fillna(0)).sort_values(ascending=False)
    nudges = []
    for c, dv in deltas.head(2).items():
        if dv > 25:
            nudges.append(f"{c}: €{cat_now[c]:.0f} so far this month, €{dv:.0f} more than at this point last month.")
    subs = subscriptions(customer_id)
    if subs["monthly_total"] > 30:
        nudges.append(f"You pay €{subs['monthly_total']:.0f}/month (€{subs['yearly_total']:.0f}/year) for "
                      f"{len(subs['subscriptions'])} subscriptions.")
    slip = next(b for b in bs["baskets"] if b["id"] == SLIP)
    return {"safe_to_spend": sts, "baskets": bs, "profile": prof, "nudges": nudges,
            "month_to_date": _r(this_m["spend"].sum()), "everyday_monthly": slip["monthly_avg"]}


def monthly_trend(customer_id: str) -> dict:
    sp = spending(customer_id)
    g = sp.groupby([sp["date"].dt.strftime("%Y-%m"), "basket"])["spend"].sum().unstack(fill_value=0)
    return {"months": g.index.tolist(), "series": {b: [_r(x) for x in g.get(b, pd.Series(0, index=g.index))]
                                                   for b in BASKETS}}


def transactions(customer_id: str, limit: int = 60, basket: str | None = None, q: str | None = None) -> list[dict]:
    sp = spending(customer_id)
    if basket:
        sp = sp[sp["basket"] == basket]
    if q:
        sp = sp[sp["merchant"].str.contains(q, case=False, regex=False) | sp["category"].str.contains(q, case=False, regex=False)]
    sp = sp.sort_values("date", ascending=False).head(limit)
    return [{"date": str(r["date"].date()), "merchant": r["merchant"], "category": r["category"],
             "amount": _r(r["spend"]), "basket": r["basket"], "why": r["basket_reason"], "bank": r["source_bank"]}
            for _, r in sp.iterrows()]


def clean(o):
    """Make results JSON-safe (numpy / NaN)."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else float(o)
    return o
