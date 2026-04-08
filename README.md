# Backend — FastAPI + SQLite

Server Python che fa da intermediario tra il frontend Next.js, la Strava API e i dati HealthKit. Gestisce la cache SQLite, il refresh automatico dei token e il calcolo delle metriche di allenamento.

## Stack

| Tool | Ruolo |
|---|---|
| Python 3.11+ | Linguaggio |
| FastAPI | Web framework |
| Pydantic v2 | Validazione input/output |
| aiosqlite | Accesso async SQLite |
| httpx | Chiamate HTTP verso Strava |
| python-dotenv | Gestione variabili d'ambiente |
| pytest + pytest-asyncio | Test |

## Avvio

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload   # → http://localhost:8000
```

API docs interattive: [http://localhost:8000/docs](http://localhost:8000/docs)

## Struttura

```
backend/
├── main.py                  # Entry point: app FastAPI, CORS, router mount
├── requirements.txt
├── .env                     # Credenziali (non in git)
│
├── routers/                 # Endpoint per dominio
│   ├── activities.py        # GET lista attività, GET dettaglio
│   ├── activities_stats.py  # Statistiche aggregate per sport/periodo
│   ├── analytics.py         # POST compute, GET fitness/metriche giornaliere
│   ├── athlete.py           # GET profilo atleta
│   ├── auth.py              # OAuth2 Strava (token exchange)
│   ├── health.py            # POST dati HealthKit da app iOS
│   ├── predictions.py       # Previsioni gara (modelli corsa)
│   └── sync.py              # POST sync Strava, GET status sync
│
├── services/
│   ├── strava_client.py     # Client HTTP Strava con refresh token automatico
│   ├── sync_service.py      # Logica sync attività (full + recente)
│   ├── analytics_service.py # Calcolo TRIMP, CTL/ATL/TSB, recovery score
│   ├── analytics_activity.py
│   ├── analytics_daily.py
│   └── analytics_queries.py
│
├── models/                  # Modelli Pydantic (response_model degli endpoint)
│
├── db/
│   ├── database.py          # Connessione aiosqlite, init schema
│   └── schema.sql           # DDL completo (tabelle + indici)
│
├── utils/                   # Helper (pace, conversioni, calcoli)
├── scripts/                 # Script di supporto (es. test_auth.py per OAuth)
└── tests/                   # pytest
```

## Endpoint principali

| Metodo | Path | Descrizione |
|---|---|---|
| `GET` | `/activities` | Lista attività con filtri |
| `GET` | `/activities/{id}` | Dettaglio attività |
| `GET` | `/athlete` | Profilo atleta |
| `POST` | `/sync/recent` | Sync ultime attività da Strava |
| `POST` | `/sync/all` | Sync completo storico |
| `GET` | `/sync/status` | Ultimo sync + conteggio |
| `POST` | `/analytics/compute` | Ricalcola TRIMP, CTL/ATL, recovery score |
| `GET` | `/analytics/fitness` | Serie storica CTL/ATL/TSB |
| `GET` | `/analytics/daily` | Metriche giornaliere aggregate |
| `GET` | `/predictions/races` | Previsioni tempi gara |
| `POST` | `/health/*` | Ingestion dati da app iOS HealthKit |

## Cache SQLite

Il database `db/strava_cache.db` contiene:

- `activities` — attività Strava (raw JSON + colonne estratte)
- `athlete` — profilo atleta
- `sync_log` — storico delle sincronizzazioni
- `analytics_activity` — TRIMP, zone HR, efficiency factor per attività
- `analytics_daily` — CTL/ATL/TSB, recovery score, HRV baseline, dati sonno
- `health_*` — tabelle dati HealthKit (steps, sleep, HR, HRV, workouts, …)

**TTL cache:**
- Attività storiche → 24h
- Ultima settimana → 15 min

Schema completo in `db/schema.sql`. Migrazioni manuali documentate in `docs/migrations.md`.

## Variabili d'ambiente

```env
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_REFRESH_TOKEN=
```

Crea un file `.env` nella root di `backend/`. Il client Strava fa il refresh automatico del token prima di ogni chiamata (scade ogni 6h).

## Test

```bash
pytest                                      # tutti i test
pytest tests/test_sync.py                  # file specifico
pytest tests/test_analytics.py::test_ctl  # singolo test
```

## Note

- CORS configurato solo per `http://localhost:3000` (dev)
- Rate limit Strava: 200 req/15 min, 2000/giorno — header `X-RateLimit-Limit` / `X-RateLimit-Usage` loggati su ogni risposta
- Nessun ORM: SQL diretto con query parametrizzate
- Tutti gli endpoint hanno `response_model` esplicito e status code appropriato
