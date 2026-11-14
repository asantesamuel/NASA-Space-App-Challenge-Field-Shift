# Nova Yield

Nova Yield is a rule-based crop-rotation decision-support prototype for farmers in the Ghana pilot area. It combines a farmer's dated crop history, a shared crop catalogue, location-specific planting windows, persisted NASA POWER climate history, labour capacity, and one farmer-selected priority to produce up to three explainable future rotation options.

The recommendations are relative comparisons for planning conversations. They are not yield forecasts, field measurements, profitability estimates, or guaranteed planting advice. Crop traits, public town reference points, and planting windows include provisional desk-research estimates and still need local agronomic validation.

## Current product direction

The approved Product Direction dated 7 November 2026, together with the Product Owner clarifications recorded on 9 November 2026, is the current implementation baseline. It supersedes older research handoffs and Jira descriptions wherever they conflict. The complete implementation notes, open evidence limits, file map, and architecture are in [the Product Direction implementation guide](analysis_docs/product-direction-implementation.md). Historical decisions remain in [the research and Product Owner decision record](novayield-research-and-product-decisions.md), which now points to the current baseline.

## Repository layout

```text
NovaYield/
├── frontend/       # React + TypeScript + Vite user interface
├── backend/        # FastAPI, MongoDB/Beanie, NASA loader, and decision logic
├── analysis_docs/  # Research evidence, decisions, and analytical experiments
├── README.md
└── .gitignore
```

Runtime information—users, farms, saved results, crop/calendar catalogues, and daily climate records—belongs in MongoDB. `analysis_docs/` is for research and reproducible analysis artifacts, never for application persistence or NASA cache data.

## Technology

| Area | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| Backend | Python 3.11+, FastAPI, Pydantic, Uvicorn |
| Database | MongoDB, PyMongo Async, Beanie |
| External climate source | NASA POWER Daily API |
| Backend checks | pytest, Ruff |
| Frontend checks | TypeScript typecheck, Oxlint, Vite production build |

Python and Node dependencies are installed separately in `backend/` and `frontend/`.

## Prerequisites

- Git
- Python 3.11 or later
- Node.js 20.19+ or 22.12+ and npm
- MongoDB available locally or through a development connection string
- Network access for the one-day NASA grid-mapping request and climate-loader jobs

## Backend setup (Windows PowerShell)

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Create separate private values for `NOVAYIELD_CSRF_SECRET` and `NOVAYIELD_LOCATION_HASH_SECRET` in `backend/.env`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Run the command twice. Keep both values private. Keep the location-hash value stable while old request-keyed NASA snapshots may still need to be resolved. Set `NOVAYIELD_MONGODB_URI` and `NOVAYIELD_MONGODB_DATABASE_NAME` for the development database. Never put secrets into `.env.example` or source control.

Seed the supported locations, crop records, planting calendars, farmer reference options, and versioned analysis defaults:

```powershell
python -m app.farms.seed_catalogs
```

The seed command inserts missing records and preserves existing catalog changes. It does not claim that provisional crop values or calendars are locally validated.

### Map pilot locations to NASA grid cells

Before climate loading, map the supported town references with one small NASA request per location. The command stores NASA's returned grid geometry internally and queues that cell as pending; it does not perform the historic backfill:

```powershell
python -m app.jobs.resolve_nasa_grid --location-key ejura
python -m app.jobs.resolve_nasa_grid --location-key anyinasu
python -m app.jobs.resolve_nasa_grid --location-key kintampo
```

After mocked ingestion, API, and database checks pass, an operator may explicitly load one mapped cell's history in controlled decade chunks:

```powershell
python -m app.jobs.climate_worker --mode backfill --cell-key <cell-key> --confirm-large-download
```

This downloads daily history from 1981-01-01 through the latest complete date for that grid cell. The loader saves chunk progress and can resume. Do not use `--mode pending` until you intend to load every pending cell. The weekly worker refreshes only the latest 120 days and remains disabled until an operator verifies the initial history and sets `NOVAYIELD_NASA_CLIMATE_WEEKLY_SYNC_ENABLED=true`. Run workers from a separate scheduled process; never schedule them inside FastAPI.

### Start the backend

From `backend/`:

```powershell
python -m uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Readiness: <http://localhost:8000/health/ready>

The API can start while MongoDB is unavailable, but readiness reports HTTP 503. Farmer requests read persisted climate records; they do not call NASA POWER.

## Frontend setup

From the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

Vite normally serves the app at <http://localhost:5173>. `VITE_API_BASE_URL` can point the browser at another API origin. Browser requests use cookie credentials; keep API and frontend hostnames consistent for local development.

## Farmer API flow

1. Initialize the CSRF cookie, then register or log in with JSON email/password. The browser sends the HttpOnly session cookie and an `X-CSRF-Token` header on state-changing requests.
2. Load supported locations, crops, and reference options from the API. Create a farm with its location key, labour capacity, one to three actual dated crop-history events, and optionally one priority.
3. Read `GET /api/v1/farms/{farm_id}/environment` to see whether its shared NASA grid-cell archive is pending, loading, ready, partial, or unavailable and to inspect analysis of the farmer-reported historical event dates.
4. Call `POST /api/v1/farms/{farm_id}/recommendations` with `{}` or one optional priority, for example `{"priority":"water_security"}`. The backend reads stored climate data, schedules crop events from location calendars, applies the versioned scoring rules, and saves the result.
5. Read saved result history from `GET /api/v1/farms/{farm_id}/rotation-results`.

The farmer does not send coordinates, NASA dates, future planting windows, or an owner ID. The location key resolves to a private backend reference point. The 1991–2020 climate normal is used only for historical comparison; it is not the entire stored climate range, which begins in 1981.

## Run checks

From `backend/`:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The unit suite uses synthetic fixtures and mocked NASA responses. Optional end-to-end Mongo tests require `NOVAYIELD_TEST_MONGODB_URI` pointing directly at a local disposable MongoDB instance; they create and remove only uniquely named test databases. They do not call NASA.

From `frontend/`:

```powershell
npm run typecheck
npm run lint
npm run build
```

The frontend currently has no dedicated unit-test runner.

## Data and decision boundaries

- `climate_cells` and `climate_daily` hold one shared daily archive per NASA-returned grid cell. No farm identifiers or private farm coordinates are stored in daily rows.
- Only the standalone loader and weekly worker write daily climate records. The API reads them for history analysis and recommendations.
- Missing NASA values remain `null`; the backend reports coverage and never fills them with zero. The historical findings describe regional grid weather, not farm sensors, soil moisture, or forecasts.
- The current engine scores water resilience, soil effect, growth speed, and labour. It uses one farmer priority as a weight adjustment. Crop-group diversity is a soft tie-break immediately after score, not a hard exclusion or a numeric bonus.
- The initial crop and calendar records are source-backed desk estimates and clearly labelled analogues where needed. Unsupported information remains absent; no calendar is copied to a location without evidence.
- Old farms with free-text crop history must be explicitly marked for re-entry. The migration does not invent crop identities, order, or dates. Old snapshots and saved results remain readable.
- Use `analysis_docs/` for new source reviews and agronomic validation records. Runtime data stays in MongoDB.

## Git workflow

The current integration branch for this work is `dev`. Check the branch and worktree before starting. Feature work after the foundation should use separate branches from the current team integration branch; this assignment is being carried out directly on `dev` as requested.

```powershell
git status --short --branch
git log --oneline -5
```

See [backend setup and operations](backend/README.md), [the current API workflow](backend/docs/product-direction-api-workflow.md), [the Product Direction implementation audit](analysis_docs/product-direction-implementation.md), and [historical Product Owner decisions](novayield-research-and-product-decisions.md#9-current-product-direction--7-november-2026-clarified-9-november-2026) for further details.
