# CarbonTread

A carbon footprint tracker built for urban Indian users — estimates daily emissions, tracks them over time with honest confidence labeling, and suggests simple, non-repetitive ways to cut them.

No login required. Tap-based onboarding. Real numbers from the first screen, not an empty dashboard.

---

## Features

- **Live dashboard** — today's CO2 estimate, % of the 6.0kg daily carbon budget (aligned with the 1.5°C climate goal by 2030), category breakdown (Transport / Food / Energy)
- **Confidence-tagged tracking** — every number is marked HIGH (logged today), MEDIUM (recalled), or LOW (assumed baseline), so nothing is shown with false precision
- **Counterfactual comparisons** — "your Uber trip cost 2.2kg, metro would've cost 0.17kg"
- **Daily AI suggestions** — three ranked, weather-aware, non-repeating actions with estimated CO2 saved
- **Weekly AI narrative** — a short written summary of the week's emissions pattern
- **No auth, still isolated** — per-browser UUID session means concurrent users never collide

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Flask 3 (Python) |
| Database | SQLite |
| Frontend | Vanilla JS / HTML / CSS — no build step |
| AI | Gemini API (`gemini-3.1-flash-lite`) |
| Weather | OpenWeatherMap |
| Rate limiting | Flask-Limiter |

---

## Project Structure

```
carbontread/
├── app.py                          # App factory, blueprint registration
├── config.py                       # Env-driven config
│
├── services/
│   ├── db.py                       # SQLite connection + schema
│   ├── carbon_calculator.py        # All emission factors + math (single source of truth)
│   ├── baseline_engine.py          # Weekly adaptive baseline recalculation
│   ├── suggestion_engine.py        # Suggestion generation + daily caching
│   ├── gemini_service.py           # Gemini client + calls
│   └── gemini_models.py            # Response schemas
│
├── routes/
│   ├── onboarding_routes.py        # Session init + base profile
│   ├── onboarding_recap_routes.py  # 7-day retroactive recap
│   ├── dashboard_routes.py
│   ├── event_routes.py             # Manual structured event logging
│   ├── event_extraction_routes.py  # Free-text → structured event (Gemini)
│   ├── suggestion_routes.py
│   ├── insight_routes.py           # Confidence report
│   └── insight_narrative_routes.py # Weekly AI narrative
│
├── static/                         # index.html, css/, js/
└── tests/
```

---

## Getting Started

```bash
# Clone and enter the project
cd carbontread

# Set up a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# fill in GEMINI_API_KEY / OPENWEATHERMAP_API_KEY / SECRET_KEY

# Run
python app.py
```

Runs at `http://127.0.0.1:5000`. SQLite schema is created automatically on first launch.

### Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session signing |
| `GEMINI_API_KEY` | Yes, for AI features | Powers extraction, suggestions, narrative |
| `OPENWEATHERMAP_API_KEY` | No | Adds weather context to suggestions |
| `GEMINI_MODEL` | No | Defaults to `gemini-3.1-flash-lite` |

App still runs and degrades gracefully without API keys — AI features fall back to static suggestions/templated narratives instead of crashing.

---

## API

All routes except `/api/session/init` require an `X-User-ID` header (issued by session init, stored client-side).

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/session/init` | Create a per-browser user session |
| `POST` | `/api/onboarding/profile` | Save base profile |
| `POST` | `/api/onboarding/recap` | Save 7-day retroactive recap |
| `GET`  | `/api/dashboard` | Today's totals + category breakdown |
| `POST` | `/api/event/log` | Log a structured event |
| `POST` | `/api/event/confirm_baseline` | One-tap "usual day" confirmation |
| `POST` | `/api/event/extract` | Free-text → structured event |
| `GET`  | `/api/suggestions` | Today's ranked suggestions |
| `POST` | `/api/suggestions/respond` | Accept/reject a suggestion |
| `GET`  | `/api/insights/confidence` | Per-category confidence report |
| `GET`  | `/api/insights/narrative` | Weekly AI narrative |

---

## Testing

```bash
pytest tests/ -v
```

## Deployment

Refer to [PYTHONANYWHERE_DEPLOY.md](PYTHONANYWHERE_DEPLOY.md) for detailed step-by-step instructions on deploying the Flask backend and SQLite database to a production environment (PythonAnywhere).

---

## Limitations

- No authentication — one session per browser, no multi-device sync
- Emission factors are working estimates for an awareness tool, not audit-grade accounting (full sourcing in `services/carbon_calculator.py`)
- Retroactive recap data is self-reported, so it's capped at MEDIUM confidence

---

## License

MIT
