"""Open-data benchmarks: Statistics Finland, Household Budget Survey 2022.

Headline figures (Statistics Finland, preliminary 2022 results):
  * average consumption expenditure EUR 39,000 per household / EUR 27,800 per consumption unit per year
  * housing & energy + transport + food = ~59% of consumption expenditure
  * food share: 18% in the lowest income quintile vs 12% in the highest

The per-group shares below are APPROXIMATE COICOP shares consistent with those
headline figures. Before production, replace them with the exact values from
StatFin table 'ktutk / 14pg' (expenditure per month by consumption item):
https://pxdata.stat.fi/PXWeb/pxweb/en/StatFin/StatFin__ktutk/14pg.px
"""

SOURCE = {
    "name": "Statistics Finland – Households' consumption (Household Budget Survey 2022)",
    "url": "https://stat.fi/en/statistics/ktutk",
    "table": "https://pxdata.stat.fi/PXWeb/pxweb/en/StatFin/StatFin__ktutk/14pg.px",
    "caveat": "Group shares are approximate; verify against the StatFin table before production use.",
}

FINLAND_MONTHLY_PER_UNIT = 27_800 / 12  # EUR per consumption unit per month

FINLAND_SHARES = {
    "Housing & energy": 0.30,
    "Transport": 0.16,
    "Food": 0.13,
    "Recreation & culture": 0.11,
    "Restaurants & cafés": 0.06,
    "Furnishings & household": 0.05,
    "Health": 0.05,
    "Clothing & shopping": 0.04,
    "Alcohol & tobacco": 0.03,
    "Communication": 0.03,
    "Other": 0.04,
}

_MAP = {
    "Housing": "Housing & energy", "Utilities": "Housing & energy", "Loan": "Housing & energy",
    "Groceries": "Food",
    "Public transport": "Transport", "Taxi": "Transport", "Fuel": "Transport", "Car repair": "Transport",
    "Restaurants": "Restaurants & cafés", "Coffee & snacks": "Restaurants & cafés",
    "Takeaway & delivery": "Restaurants & cafés",
    "Entertainment": "Recreation & culture", "Subscriptions": "Recreation & culture", "Travel": "Recreation & culture",
    "Gym & sports": "Recreation & culture", "Electronics": "Recreation & culture",
    "Home & appliances": "Furnishings & household",
    "Health": "Health",
    "Shopping": "Clothing & shopping",
    "Alcohol": "Alcohol & tobacco",
    "Phone & internet": "Communication",
}


def coicop_group(category: str) -> str:
    return _MAP.get(category, "Other")
