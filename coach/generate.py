"""Synthetic transaction generator modelled on a typical bank transaction schema.

Used so the app runs end-to-end before (or without) the official Junction dataset.
When the real dataset is available, drop it into data/ and see coach/data.py for
the column mapping - nothing else in the app needs to change.

Schema (one row per booked transaction):
    txn_id, customer_id, date, amount (EUR, negative = money out), merchant,
    category, account, source_bank, description
"""
from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd

START = date(2025, 11, 1)
END = date(2026, 11, 14)

# ---------------------------------------------------------------- personas
PERSONAS = {
    "aino": {
        "name": "Aino", "age": 24, "city": "Helsinki",
        "blurb": "Junior designer, first full-time job, rents a studio.",
        "salary": 2650, "payday": 15, "rent": 890, "rent_merchant": "Kojamo Lumo-kodit",
        "extra_income": [],
        "bills": [("Helen Oy", "Utilities", 38, 12), ("Elisa Oyj", "Phone & internet", 34.9, 20),
                  ("HSL", "Public transport", 64.7, 2), ("Spotify", "Subscriptions", 11.99, 7),
                  ("Netflix", "Subscriptions", 13.99, 11), ("HBO Max", "Subscriptions", 9.99, 23),
                  ("Elixia", "Gym & sports", 49.0, 1), ("If Vahinkovakuutus", "Insurance", 14.5, 5)],
        "groceries_week": 70, "coffee_per_week": 6, "dining_per_month": 5, "takeaway_per_month": 7,
        "taxi_per_month": 3, "alcohol_per_month": 3, "shopping_per_month": 3, "night_out_per_month": 3,
        "savings_transfer": 100, "multi_bank": None,
    },
    "mikko": {
        "name": "Mikko", "age": 38, "city": "Tampere",
        "blurb": "Engineer, two kids, family car and a mortgage.",
        "salary": 4300, "payday": 1, "rent": 1240, "rent_merchant": "Asuntolaina S-Pankki",
        "extra_income": [("Kela lapsilisa", 220, 26)],
        "bills": [("Tampereen Sähkölaitos", "Utilities", 95, 12), ("Telia Finland", "Phone & internet", 59.8, 20),
                  ("Päiväkoti Tampere", "Childcare", 310, 3), ("LähiTapiola", "Insurance", 78, 5),
                  ("Taloyhtiö As Oy Kaleva", "Housing", 280, 4), ("Disney+", "Subscriptions", 10.99, 9),
                  ("Spotify Family", "Subscriptions", 21.99, 7), ("Nysse", "Public transport", 55, 2)],
        "groceries_week": 210, "coffee_per_week": 3, "dining_per_month": 4, "takeaway_per_month": 4,
        "taxi_per_month": 1, "alcohol_per_month": 2, "shopping_per_month": 5, "night_out_per_month": 1,
        "savings_transfer": 300, "fuel_per_month": 4,
        "multi_bank": {"bank": "Nordea (PSD2)", "salary": 2900, "payday": 15},
    },
    "liisa": {
        "name": "Liisa", "age": 67, "city": "Jyväskylä",
        "blurb": "Retired teacher, owns her flat, enjoys travelling.",
        "salary": 2350, "payday": 8, "rent": 340, "rent_merchant": "Taloyhtiö As Oy Harju",
        "extra_income": [],
        "bills": [("Jyväskylän Energia", "Utilities", 62, 12), ("DNA Oyj", "Phone & internet", 29.9, 20),
                  ("Pohjola Vakuutus", "Insurance", 46, 5), ("Helsingin Sanomat", "Subscriptions", 32.9, 3)],
        "groceries_week": 85, "coffee_per_week": 2, "dining_per_month": 3, "takeaway_per_month": 0,
        "taxi_per_month": 2, "alcohol_per_month": 1, "shopping_per_month": 2, "night_out_per_month": 0,
        "savings_transfer": 250, "multi_bank": None,
    },
}

GROCERY_BIG = ["Prisma", "S-market", "K-Citymarket", "Lidl", "K-Supermarket"]
GROCERY_SMALL = ["Alepa", "Sale", "K-Market", "R-kioski"]
COFFEE = ["Robert's Coffee", "Espresso House", "Fazer Café", "Starbucks", "Wayne's Coffee"]
DINING = ["Rax", "Hesburger", "Ravintola Kaisla", "Hanko Sushi", "Fafa's", "Ravintola Sea Horse", "Amarillo"]
TAKEAWAY = ["Wolt", "Foodora"]
TAXI = ["Uber", "Bolt", "Taksi Helsinki", "Menevä"]
ALCOHOL = ["Alko"]
NIGHT_OUT = ["Bar Ihku", "Kaarle XII", "Finnkino", "Tiketti"]
SHOPPING = ["Zalando", "H&M", "Stockmann", "Sokos", "Clas Ohlson", "Tokmanni", "Amazon.de"]
HEALTH = ["Yliopiston Apteekki", "Terveystalo", "Mehiläinen", "Oral Hammaslääkärit"]
FUEL = ["ABC", "Neste", "St1"]

IRREGULAR_EVENTS = [
    # (merchant, category, min, max, probability per month)
    ("Gigantti", "Home & appliances", 280, 720, 0.07),
    ("Verkkokauppa.com", "Electronics", 120, 650, 0.08),
    ("Terveystalo", "Health", 60, 190, 0.15),
    ("Oral Hammaslääkärit", "Health", 85, 340, 0.08),
    ("Instru Optiikka", "Health", 180, 420, 0.03),
    ("Traficom", "Fees & taxes", 60, 240, 0.05),
    ("Poliisi passi", "Fees & taxes", 52, 52, 0.02),
]


def _d(n: int) -> list[date]:
    return [START + timedelta(days=i) for i in range(n)]


def _jitter(x: float, pct: float, rng: random.Random) -> float:
    return round(x * (1 + rng.uniform(-pct, pct)), 2)


def generate(seed: int = 7) -> pd.DataFrame:
    rows: list[dict] = []
    days = _d((END - START).days + 1)

    for cid, p in PERSONAS.items():
        rng = random.Random(f"{seed}-{cid}")
        acct = "S-Pankki käyttötili"

        def add(d, amount, merchant, category, account=acct, src="S-Pankki", desc=""):
            rows.append({"customer_id": cid, "date": d, "amount": round(amount, 2), "merchant": merchant,
                         "category": category, "account": account, "source_bank": src,
                         "description": desc or merchant})

        # month-level events
        months = sorted({(d.year, d.month) for d in days})
        for (y, m) in months:
            def on(day):
                try:
                    dd = date(y, m, min(day, 28))
                except ValueError:
                    return None
                return dd if START <= dd <= END else None

            if (d := on(p["payday"])):
                bonus = 1.0 + (0.5 if m == 6 else 0)  # Finnish holiday bonus (lomaraha) in June
                add(d, _jitter(p["salary"] * bonus, 0.01, rng), "Palkka / Salary", "Income", desc="SALARY")
            for (merch, amt, day) in p["extra_income"]:
                if (d := on(day)):
                    add(d, amt, merch, "Income")
            if (d := on(1)):
                add(d, -p["rent"], p["rent_merchant"], "Housing", desc="Rent / housing payment")
            for (merch, cat, amt, day) in p["bills"]:
                if (d := on(day)):
                    a = _jitter(amt, 0.25, rng) if cat == "Utilities" else amt
                    if cat == "Utilities" and m in (12, 1, 2):
                        a *= 1.6  # winter electricity
                    add(d, -a, merch, cat)
            if (d := on(p["payday"] + 1)) and p["savings_transfer"]:
                add(d, -p["savings_transfer"], "Oma säästötili", "Savings transfer", desc="To own savings account")
            for (merch, cat, lo, hi, prob) in IRREGULAR_EVENTS:
                if rng.random() < prob and (d := on(rng.randint(1, 28))):
                    add(d, -round(rng.uniform(lo, hi), 2), merch, cat)
            # travel once or twice a year
            if m in (2, 7) and rng.random() < (0.9 if cid == "liisa" else 0.6) and (d := on(rng.randint(3, 20))):
                add(d, -round(rng.uniform(250, 900), 2), rng.choice(["Finnair", "Tallink Silja", "Viking Line", "Booking.com"]), "Travel")
            # discretionary month counts
            plans = [("dining_per_month", DINING, "Restaurants", 14, 48),
                     ("takeaway_per_month", TAKEAWAY, "Takeaway & delivery", 16, 38),
                     ("taxi_per_month", TAXI, "Taxi", 11, 36),
                     ("alcohol_per_month", ALCOHOL, "Alcohol", 12, 45),
                     ("night_out_per_month", NIGHT_OUT, "Entertainment", 14, 60),
                     ("shopping_per_month", SHOPPING, "Shopping", 15, 120),
                     ("fuel_per_month", FUEL, "Fuel", 55, 85)]
            for key, pool, cat, lo, hi in plans:
                n = max(0, int(round(rng.gauss(p.get(key, 0), 1))))
                if p.get(key, 0) == 0:
                    n = 0
                for _ in range(n):
                    # spending clusters right after payday and on weekends
                    day = rng.choice([p["payday"] + rng.randint(0, 5), rng.randint(1, 28), rng.randint(1, 28)])
                    if (d := on(((day - 1) % 28) + 1)):
                        if cat in ("Restaurants", "Entertainment", "Taxi", "Alcohol") and d.weekday() < 4 and rng.random() < 0.5:
                            d = d + timedelta(days=4 - d.weekday())  # push to Friday
                            if d > END:
                                continue
                        add(d, -round(rng.uniform(lo, hi), 2), rng.choice(pool), cat)
            # multi-bank (PSD2) income + spending on other bank's card
            mb = p.get("multi_bank")
            if mb:
                if (d := on(mb["payday"])):
                    add(d, _jitter(mb["salary"], 0.01, rng), "Palkka / Salary (spouse)", "Income",
                        account="Nordea käyttötili", src=mb["bank"])
                for _ in range(rng.randint(3, 6)):
                    if (d := on(rng.randint(1, 28))):
                        add(d, -round(rng.uniform(20, 140), 2), rng.choice(GROCERY_BIG), "Groceries",
                            account="Nordea käyttötili", src=mb["bank"])

        # day-level habits
        for d in days:
            wk = d.weekday()
            # groceries: one big shop weekly + small top-ups
            if wk == 5:
                add(d, -_jitter(p["groceries_week"] * 0.75, 0.3, rng), rng.choice(GROCERY_BIG), "Groceries")
            if rng.random() < 0.35:
                add(d, -round(rng.uniform(2.5, 14), 2), rng.choice(GROCERY_SMALL), "Groceries")
            if rng.random() < p["coffee_per_week"] / 7:
                add(d, -round(rng.uniform(3.2, 8.9), 2), rng.choice(COFFEE), "Coffee & snacks")
            if rng.random() < 0.03:
                add(d, -round(rng.uniform(6, 45), 2), rng.choice(HEALTH[:1]), "Health")

    df = pd.DataFrame(rows).sort_values(["customer_id", "date"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df.insert(0, "txn_id", [f"T{i:07d}" for i in range(len(df))])
    return df


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path(__file__).resolve().parent.parent / "data" / "transactions.csv"
    out.parent.mkdir(exist_ok=True)
    df = generate()
    df.to_csv(out, index=False)
    print(f"wrote {len(df)} rows to {out}")
