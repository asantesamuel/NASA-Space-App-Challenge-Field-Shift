# Nova Yield Backend

This directory contains the FastAPI service, MongoDB/Beanie persistence, canonical crop and calendar catalogs, NASA POWER grid-cell ingestion, historical weather analysis, and deterministic rotation engine.

For the full product flow, farmer-facing API examples, and current rules, see the [Product Direction API workflow](docs/product-direction-api-workflow.md). The older [NY-39/NY-40 API workflow](docs/api-workflows.md) is retained as historical ticket documentation. For the architecture, evidence assumptions, and file map, see the [Product Direction implementation audit](../analysis_docs/product-direction-implementation.md).

## Main modules

- `app/main.py` builds the API and owns the shared MongoDB connection/Beanie lifecycle. It does not construct a NASA client.
- `app/integrations/nasa/power.py` is the single NASA POWER adapter. The location resolver and separate climate worker own its HTTP client lifetime.
- `app/models/climate_store.py` defines `climate_cells`, `climate_daily`, and versioned analysis configuration.
- `app/services/climate_ingestion.py` owns resumable backfill and 120-day refresh behavior. It runs only from a separate job process.
- `app/decisions/environmental_analysis.py` and `app/decisions/product_direction.py` are pure functions. They do not call MongoDB, NASA, the system clock, or the filesystem.
- `app/farms/` owns farm profiles, crop and calendar seeding, supported locations, and reference options.
- `app/repositories/` owns MongoDB access. Authenticated user/farm/result queries include owner constraints.
- `tests/` contains unit/API tests and opt-in isolated MongoDB integration tests.

## Local setup (Windows PowerShell)

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Set a development MongoDB URI/name and generate private values for `NOVAYIELD_CSRF_SECRET` and `NOVAYIELD_LOCATION_HASH_SECRET` in `.env`. Generate separate values with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The API uses the database named `nova_yield` at `mongodb://localhost:27017` by default. A missing database can be created by MongoDB on the first write. Keep `.env` private. The location hash secret must remain stable while legacy request-keyed snapshots may be read.

Seed location records, crops, calendars, farmer reference options, and the active versioned analysis configuration:

```powershell
python -m app.farms.seed_catalogs
```

For an existing database with older free-text farm records, explicitly mark legacy records so the owners can re-enter actual history:

```powershell
python -m app.farms.migrate_legacy
```

No crop dates, order, or canonical crop IDs are inferred by this command.

## Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs>. Liveness is `/health/live`; readiness is `/health/ready`. Mongo connection failures are reported without returning the URI or driver credentials. The API may start while MongoDB is down, but readiness is false and data operations cannot proceed.

## NASA grid mapping and climate jobs

Map each supported town before any full history load. Each mapping command makes one small one-day request using the town's private reference point, records the NASA-returned geometry, and registers the shared grid cell as pending:

```powershell
python -m app.jobs.resolve_nasa_grid --location-key ejura
python -m app.jobs.resolve_nasa_grid --location-key anyinasu
python -m app.jobs.resolve_nasa_grid --location-key kintampo
```

After the fixture-based tests and integration checks pass, an operator can target one grid cell for the 1981-to-current initial history load:

```powershell
python -m app.jobs.climate_worker --mode backfill --cell-key <cell-key> --confirm-large-download
```

The worker requests `PRECTOTCORR`, `T2M`, and `T2M_MAX` in decade chunks, stores missing/fill values as `null`, and saves chunk progress so the load can resume. It reuses one NASA client per worker process. Never start the full multi-cell backlog without an explicit rollout plan.

Weekly refresh is a separate scheduled command and only re-requests the last 120 days:

```powershell
python -m app.jobs.climate_worker --mode weekly
```

Weekly sync is disabled by default. Set `NOVAYIELD_NASA_CLIMATE_WEEKLY_SYNC_ENABLED=true` only after the historic load and its stored coverage have been verified. Schedule one worker/cron process outside FastAPI. Per-cell leases prevent concurrent loaders from writing the same grid cell at once.

## Test and lint

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Unit and API tests use mocks and synthetic weather. The authenticated real-Mongo test is opt-in and touches only a randomly named disposable database on a direct local MongoDB listener:

```powershell
$env:NOVAYIELD_TEST_MONGODB_URI = "mongodb://localhost:27017"
python -m pytest tests\integration -q
Remove-Item Env:\NOVAYIELD_TEST_MONGODB_URI
```

It does not read the application's normal `.env` database or call NASA. Do not set the test variable to a remote or valuable database.

## Privacy and data notes

- The public location endpoint returns only location keys and labels. Private point coordinates and NASA grid geometry are backend data and do not appear in frontend responses or application diagnostics.
- `climate_daily` has a unique `(cell_key, day)` index and stores no farm identifier, farmer identity, or private farm coordinates.
- Browser authentication uses a database-backed, expiring HttpOnly cookie. Initialize CSRF first and send `X-CSRF-Token` for state-changing requests. Credentialed CORS requires explicitly configured frontend origins.
- Soil texture and irrigation are display/context inputs. Irrigation does not infer a rice production system. Unknown rice ecology remains in history but cannot be selected as a future candidate.
- Crop traits/calendars are research-backed but provisional; `parameter_evidence` records sources, assumptions, confidence, and limitations. Seed scripts do not make local validation claims.
- Historical results and old NY-6 request snapshots are retained for compatibility. New weather requests use the grid-cell archive and do not run the old per-farm snapshot workflow.
