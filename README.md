# Moneywise – Personal Finance Coach

<img width="961" height="1067" alt="image" src="https://github.com/user-attachments/assets/974c07f5-cde1-45cc-bb96-dcaa1b8fc3b7" />


*Junction × S-Pankki challenge: “chat with your own money”.*

Moneywise is a mobile-first AI personal finance coach styled for S-Pankki’s S-mobiili. It lets people ask questions about their own transactions in plain language and teaches them where their money goes, using the **three baskets**.

| Spending type (basket) | What’s in it | What the coach teaches |
|---|---|---|
| Fixed essentials (must-pay, regular) | Rent, electricity, insurance, groceries | Your baseline cost of living: budget it first |
| Irregular essentials (must-pay, irregular) | Dentist, broken washing machine, passport | Save for these monthly with a *sinking fund* |
| Everyday spending | Coffee, takeaway, taxis, subscriptions | Small purchases add up and can be an effective area to adjust |

The UI uses S-Pankki’s brand colours, taken from its public website stylesheet. Developers should read `DEVELOPER_GUIDE.md`.

## Demo video

[Watch the Moneywise project video on YouTube](https://youtu.be/KpjejMlj3NM?is=yqXxYq_BXntGYMGU).

A narrated pitch video (under 3 minutes) is produced separately. Videos are kept out of the repository (`*.mp4` is git-ignored).

## Run it

```bash
pip install -r requirements.txt
python main.py                      # http://localhost:8931
```

- **With Gemini (Google AI Studio):** get a key at https://aistudio.google.com/apikey and set `GEMINI_API_KEY` before starting. The default model is `gemini-3.8-flash` (override with `GEMINI_MODEL`).
- **With Claude:** set `ANTHROPIC_API_KEY`. Uses `claude-opus-5-5` (override with `COACH_MODEL`; set reasoning effort with `COACH_EFFORT`, default `low` for fast chat).
- **Both keys set:** Claude is used. Force one with `COACH_PROVIDER=gemini` or `COACH_PROVIDER=claude`. Both engines share the same tools, prompt and guardrails (`coach/agent.py`, `coach/gemini.py`).
- **Without a key:** the app still works. A rule-based offline coach answers core questions, so a live demo can never break.
- **On a phone:** run `HOST=0.0.0.0 python main.py` and open `http://<laptop-ip>:8931` on the same Wi-Fi.
- **Deep links** (for embedding in S-mobiili): `/#coach?ask=How%20much%20did%20I%20spend%20on%20taxis%3F`, `/#whatif`, `/#baskets`.

### Using the official dataset

The app ships with a synthetic generator (`coach/generate.py`): three personas over about 12 months, including a PSD2-linked second bank. To use the Junction dataset:

1. Put the file in `data/`.
2. Run with `COACH_DATA=data/<file>.csv` (Parquet also works).
3. If its column names differ, extend `COLUMN_MAP` in `coach/data.py`.

Required columns are `customer_id`, `date` and `amount`. Unknown category names are mapped to baskets by keyword rules (Finnish and English).

## What’s inside

| Screen | What it does |
|---|---|
| **Overview** | Safe-to-spend this week with a calculation breakdown, the three baskets, spender type and personal nudges |
| **Coach** | Chat in Finnish, Swedish or English. The AI calls analytics tools, explains results, draws charts and suggests follow-up questions. Replies show which data was checked. |
| **Structure** | Lessons for each basket, monthly trends and user-controlled reclassification (for example, “my gym is a must for me”) |
| **Analyse** | Explore your data by period, category, merchant, weekday, bank or basket |
| **Simulate** | Model category cuts and savings destinations, and see compound growth over 1–10 years |

### How the AI is used, and why you can trust it

- The AI does not do arithmetic. Figures come from deterministic pandas functions in `coach/analytics.py`, called as tools.
- `query_spending` is a general query tool, so the coach can answer questions beyond predefined screens.
- **Transparency:** each answer is tagged with the data it checked.
- **Guardrails:** no specific investment products; distress signals point to public debt counselling resources; merchant text is treated as data, not instructions.

### Safe-to-spend method

Income since payday, minus spending to date, bills due before payday, a reserve for food and essentials, a buffer for irregular costs, and the savings goal (default 10%). What's left is spread over the days to payday. If payday falls inside the week, the days after it use the usual daily allowance.

### Open-data benchmark and PSD2 multi-bank

Spending is compared with the Finnish average from Statistics Finland’s Household Budget Survey 2022. The demo household also includes a second bank; Explore can include or exclude other banks, while safe-to-spend uses only the S-Bank account the user controls day to day.

## Demo script (3 minutes)

1. **Aino, 24 (Home):** show her safe-to-spend figure and the receipt-style calculation breakdown.
2. **Three baskets:** explore her everyday spending and spender type.
3. **Coach:** ask about taxis, spender type, safe-to-spend and a dining-out reduction; then ask in Finnish: *“Paljonko käytin Woltiin tänä vuonna?”*
4. **Baskets:** reclassify the gym as a must and watch the coach adapt.
5. **What if:** adjust restaurant spending and show compound growth.
6. **Switch to Mikko:** compare a family household with a second bank.

## How this maps to the judging criteria

- **Financial literacy:** the three-basket model, plain-language concepts (sinking fund, compound interest, safe-to-spend) and visible calculations.
- **Original AI integration:** a tool-using agent over the user’s own data, model-chosen charts and user-editable classifications.
- **Mobile UX:** 390px-first, bottom tab bar, tap-to-ask chips, dark mode and a lightweight frontend.
- **Feasibility:** FastAPI + pandas, deterministic numbers, offline fallback and support for the official dataset through column mapping.
- **S-mobiili fit:** embeddable web view, deep links and stateless JSON APIs per customer.

## Quality

- Automated tests (`python -m pytest -q`) cover calculations and API endpoints, including input validation and the offline coach.
- Friendly errors: invalid input returns `400`/`422`; unexpected errors are logged and return a safe `500`.
- Limits: chat messages are capped at 1,000 characters, AI calls time out after 45 seconds, conversation memory is bounded, and the send button is locked while an answer is pending.
- Health check: `GET /api/health`.

## Project layout

```
main.py               FastAPI server and API
coach/generate.py     synthetic S-Bank-like transactions (3 personas, PSD2 account)
coach/data.py         loader and column mapping for the official dataset
coach/analytics.py    baskets, safe-to-spend, what-if, persona, benchmarks, queries
coach/benchmarks.py   Statistics Finland reference data
coach/agent.py        AI tool-use agent and offline fallback
web/                  mobile UI (index.html, app.js, charts.js, style.css)
tests/                pytest suite (analytics + API)
demo/                 demo video
```
