# Moneywise – Personal Finance Coach

*Junction × S-Pankki challenge: "chat with your own money".*

Moneywise is a mobile-first AI personal finance coach styled for S-Pankki's S-mobiili. It lets people ask questions about their own transactions in plain language and teaches them where their money really goes, using the **three baskets**.

| Spending type (basket) | What's in it | What the coach teaches |
|---|---|---|
| Fixed essentials (must-pay, regular) | rent, electricity, insurance, groceries | Your baseline cost of living: budget it first |
| Irregular essentials (must-pay, irregular) | dentist, broken washing machine, passport | Not really surprises: save for them monthly (a *sinking fund*) |
| Everyday spending | coffee, takeaway, taxis, subscriptions | Small one at a time, but together often the most effective area to adjust |

The UI uses S-Pankki's brand colours, taken from its public website stylesheet. Developers should read `DEVELOPER_GUIDE.md`.

## Demo video
A narrated pitch video (under 3 minutes) is produced separately. Videos are kept out of the repository (`*.mp4` is git-ignored).

## Run it

```bash
pip install -r requirements.txt
python main.py                      # http://localhost:8931
```

- **With Gemini (Google AI Studio):** get a key at https://aistudio.google.com/apikey and set `GEMINI_API_KEY` before starting. The default model is `gemini-3.8-flash` (override with `GEMINI_MODEL`). If your key can't use that model, the newest available Flash model is picked automatically.
- **With Claude:** set `ANTHROPIC_API_KEY`. Uses `claude-opus-5-5` (override with `COACH_MODEL`; set reasoning effort with `COACH_EFFORT`, default `low` for fast chat).
- **Both keys set:** Claude is used. Force one with `COACH_PROVIDER=gemini` or `COACH_PROVIDER=claude`. Both engines share the same tools, prompt and guardrails (`coach/agent.py`, `coach/gemini.py`).
- **Without a key:** the app still works. A rule-based offline coach answers the core questions, so a live demo can never break.
- **On a phone:** run `HOST=0.0.0.0 python main.py` and open `http://<laptop-ip>:8931` on the same Wi-Fi.
- **Deep links** (for embedding in S-mobiili): `/#coach?ask=How%20much%20did%20I%20spend%20on%20taxis%3F`, `/#whatif`, `/#baskets`.

### Using the official dataset
The app ships with a synthetic generator (`coach/generate.py`): three personas over about 12 months, including a PSD2-linked second bank. To use the Junction dataset:

1. Put the file in `data/`.
2. Run with `COACH_DATA=data/<file>.csv` (Parquet also works).
3. If its column names differ, extend `COLUMN_MAP` in `coach/data.py`.

Required columns are `customer_id`, `date` and `amount`. Unknown category names are mapped to baskets by keyword rules (Finnish and English).

## What's inside

| Screen | What it does |
|---|---|
| **Overview** | Safe-to-spend this week (with a "how is this calculated" breakdown), the three baskets, your spender type and personal nudges |
| **Coach** | Chat in Finnish, Swedish or English. Claude calls analytics tools, explains in plain language, draws charts and suggests follow-up questions. Every reply shows which data it checked |
| **Structure** | One lesson per basket with your own numbers, a month-by-month trend, and **re-classification** ("my gym is a must for me"). The coach and safe-to-spend update immediately |
| **Analyse** | MyData: slice your own data any way you like (period, category, merchant, weekday, bank, basket) instead of fixed charts |
| **Simulate** | Cut any category by X%, choose where the savings go (0% / savings account / fund) and see compound growth over 1–10 years |

### How the AI is used, and why you can trust it
- **Claude never does arithmetic.** Every figure comes from deterministic pandas functions (`coach/analytics.py`) that the model calls as tools: `query_spending`, `basket_summary`, `safe_to_spend`, `what_if`, `spender_profile`, `benchmark`, `subscriptions`, `recurring_bills`, `reclassify` and `show_chart`. The model decides *what* to look at and *how* to explain it.
- **`query_spending` is a general query tool** (filter and group anything), so Claude can answer questions nobody pre-built a screen for.
- **Transparency:** each answer is tagged with the data it checked.
- **Guardrails:** no specific investment products; distress signals point to the free public debt-counselling service (talous- ja velkaneuvonta) and Takuusäätiö; merchant text is treated as data, not instructions.

### Safe-to-spend method
Income since payday, minus:
- what's already spent;
- bills still due before payday (auto-detected recurring payments);
- a reserve for food and essentials (from your history);
- a buffer for irregular costs (your irregular basket's monthly average);
- the savings goal (default 10%).

What's left is spread over the days to payday. If payday falls inside the week, the days after it use your usual daily allowance.

### Spender types
Scored from real behaviour: share of small purchases under €15, weekend share, spending in the 5 days after payday, number of subscriptions, experience spending, savings rate and share of regular costs. The result is one of seven types (Steady Planner, Small-Ticket Leaker, Weekend Warrior, Payday Splurger, Subscription Collector, Experience Seeker, Family Provider), each backed by evidence lines.

### Open-data benchmark
Your spending mix is compared with the Finnish average from Statistics Finland's Household Budget Survey 2022 (€39,000 per household, €27,800 per consumption unit per year; housing, transport and food ≈ 59%). The per-group shares in `coach/benchmarks.py` are approximate. Replace them with the exact values from [StatFin table 14pg](https://pxdata.stat.fi/PXWeb/pxweb/en/StatFin/StatFin__ktutk/14pg.px) before production.

### PSD2 multi-bank (bonus angle)
Mikko's household has a spouse salary and grocery spending at another bank. Explore can include or exclude other banks. Safe-to-spend deliberately uses only the S-Bank account the user controls day to day.

## Demo script (3 minutes)
1. **Aino, 24 (Home):** "€447 safe this week, payday is tomorrow." Tap *How is this calculated?* to show the receipt-style breakdown.
2. **Three baskets:** 46% of Aino's spending is everyday spending. She's a **Small-Ticket Leaker**: 9.5 purchases under €15 a week, about €305/month.
3. **Coach:** ask the four challenge questions (taxis last month, spender type, safe this week, dining out −20%). Then ask in Finnish: *"Paljonko käytin Woltiin tänä vuonna?"*
4. **Baskets → "my gym is a must":** move it and watch the coach adapt. Users own their classification.
5. **What if:** slide the cut for restaurants, switch to the fund option and show the compound-interest line.
6. **Switch to Mikko:** a different life (family, mortgage, a second bank via PSD2) gives a different persona, the same coach.

## How this maps to the judging criteria
- **Financial literacy:** the three-basket model throughout, plain-language concept explanations (sinking fund, compound interest, safe-to-spend), and visible calculations.
- **Original AI integration:** tool-using agent over the user's own data, with model-chosen charts and user-editable classifications the AI respects.
- **Mobile UX:** 390px-first, bottom tab bar, tap-to-ask chips, dark mode, no dependencies, about 60 KB of front-end code.
- **Feasibility:** plain FastAPI + pandas, deterministic numbers, an offline fallback, and works with the official dataset by mapping columns.
- **S-mobiili fit:** an embeddable web view, deep links (`#coach?ask=`), and stateless JSON APIs per customer.

## Quality
- **46 automated tests** (`python -m pytest -q`) cover the calculations (baskets add up, safe-to-spend arithmetic, what-if maths, recurring detection, reclassification) and every API endpoint, including input validation and the offline coach.
- Friendly errors everywhere: bad input returns `400`/`422` with a clear message, unexpected errors are logged and return a safe `500`, and the UI shows a retry card instead of breaking.
- Limits: chat messages are capped at 1,000 characters, AI calls time out after 45 s, conversation memory is bounded, and the send button is locked while an answer is pending.
- Health check: `GET /api/health`.

## Project layout
```
main.py               FastAPI server and API
coach/generate.py     synthetic S-Bank-like transactions (3 personas, PSD2 account)
coach/data.py         loader and column mapping for the official dataset
coach/analytics.py    baskets, safe-to-spend, what-if, persona, benchmarks, queries
coach/benchmarks.py   Statistics Finland reference data
coach/agent.py        Claude tool-use agent and offline fallback
web/                  mobile UI (index.html, app.js, charts.js, style.css)
tests/                pytest suite (analytics + API)
demo/                 demo video
```
