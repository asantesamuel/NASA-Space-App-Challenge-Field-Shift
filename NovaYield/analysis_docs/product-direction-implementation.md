# Product Direction Implementation Audit and Plan

**Baseline:** NovaYield Product Direction, 7 November 2026, with Product Owner clarifications of 9 November 2026.  
**Implementation branch:** `dev`.  
**Status:** Implementation and automated verification completed on this worktree; this is an implementation record, not local agronomist validation.

> The separate “Prompt 1” audit mentioned in the implementation request was not present in this checkout. This audit was reconstructed from the supplied Product Direction PDF, the current repository and the Product Owner clarifications in the active conversation. The PDF's seven November direction supersedes earlier Jira and research contracts where they conflict; the nine November clarifications below resolve the additional crop evidence, priority, privacy, diversity, weather and operational choices.

## 1. Executive summary

The `dev` branch is the requested working source for this implementation. At inspection it was at `5c83d78` and matched `origin/dev`; `master` has a separate history. No merge, reset, branch deletion or history rewrite was performed. Existing uncommitted changes are being preserved. No commit was made.

The new architecture is being implemented around a shared daily climate archive per NASA-returned grid cell, not a separate NASA request per farmer. A separate operator/cron process resolves locations and loads/synchronizes climate data. Farmer API requests read persisted MongoDB climate records, analyze the farm's actual dated crop events, schedule future events from location-specific calendars and run a deterministic, versioned four-criterion scoring engine. The engine returns at most three options and records its inputs and rule versions.

The 9 November decisions authorize research-backed direct and analogue estimates for the starter crop library, with provenance and limitations visible; those estimates are provisional and must not be represented as Ghana-local validation. Farmers choose at most one priority. Climate context status is explicit and unavailable weather remains null; its step-one weighting only changes when an available finding meets the documented adverse-weather condition. Crop-group diversity is a soft preference and the first tie-break after score. The current-practice baseline remains deferred. MVP catalog maintenance uses seed/operator scripts; an agronomist administration page is out of scope.

The guarded loader has now completed a controlled 1981-to-latest archive load for each of the three configured pilot location cells in the authorized disposable development database. Each archive is verified `ready` through 6 November 2026. Weekly refresh remains disabled until a separate scheduled worker is configured; no worker runs inside FastAPI or during farmer requests.

## 2. Current state and implementation matrix

| Area | Status | Repository evidence / remaining work |
|---|---|---|
| Branch and working tree | In progress | Working on `dev`; unrelated work is preserved. `master` remains separate and untouched. |
| FastAPI and Beanie lifecycle | Implemented previously | `backend/app/main.py`, `backend/app/database/`; reused rather than duplicated. |
| NASA POWER client | Adapted | One client in `backend/app/integrations/nasa/power.py`; returned geometry and metadata are used by the resolver/loader. |
| Grid-based climate persistence | Implemented in this change | `ClimateCell`, `ClimateDaily`, repository, indexes, per-cell lease and progress fields. |
| Initial loader and recent refresh | Implemented and exercised | Resumable decade-aligned history and last-120-day refresh in a separate worker; controlled full archive loaded for all three pilot cells. |
| Dated farm history and privacy | Adapted | Owner-scoped Farm model/routes; actual crop-event dates; private location coordinates; legacy history is not inferred. |
| Crop and calendar catalogues | Adapted and seeded by scripts | Shared crop identity/history/candidate collection; rice profiles are separate by production system; calendar rows are location scoped. Trait and calendar entries are evidence-labelled estimates, not local validation. |
| Historical environmental analysis | Implemented in this change | Pure event-window and since-harvest analysis with fixed 1991–2020 comparisons and explicit coverage/missingness. |
| Future scheduler | Implemented in this change | Pure location-calendar scheduler, maturity ranges, 14-day turnover and 24-month horizon. |
| Recommendation engine | Implemented in this change | Pure generate/filter/score/explain pipeline, hard candidate/labour/calendar/rice filters, four criteria, one priority, soft diversity tie-break, top-three cap. |
| Recommendation and result persistence | Adapted | NY-9 workflow persists a versioned result through the existing NY-20 repository; old result records remain readable. |
| Frontend farm and comparison flow | Adapted | `FieldSetup.tsx` uses backend catalog/reference choices and dated history; `Comparison.tsx` shows climate state, findings, future dates and score explanations. |
| API contract / OpenAPI | Implemented and tested | Existing auth/farm/history routes are retained; `/environment` and `/recommendations` use persisted climate. Automated API and Mongo workflow coverage passes. |
| Documentation | In progress | This guide and API/setup documentation are being aligned; older decision/scoring/NASA snapshot documents need explicit historical/legacy notices. |

### Source-of-truth branch

The user explicitly selected `dev`. At inspection, `dev` was at `5c83d78` and aligned with `origin/dev`; `master` was not an ancestor-equivalent copy and was left unchanged. Continue implementation and review on `dev` until the team selects another integration branch. Do not infer that `master` is newer or merge it without an explicit branch reconciliation task.

## 3. Reusable modules and files that changed

### Backend

- `backend/app/integrations/nasa/power.py` remains the sole NASA POWER adapter. It is called by the location grid resolver and climate worker, not by farmer requests.
- `backend/app/models/climate_store.py` defines `climate_cells`, `climate_daily`, and `analysis_config`.
- `backend/app/repositories/climate_store.py` owns Mongo access, cell registration/leases, daily reads and idempotent upserts.
- `backend/app/services/climate_ingestion.py` implements decade chunking, resumable backfill and 120-day synchronization.
- `backend/app/jobs/resolve_nasa_grid.py` resolves a supported place to NASA's returned cell geometry using a one-day request. It stores the geometry privately and prints an opaque cell key only.
- `backend/app/jobs/climate_worker.py` is the separate worker entry point for explicitly targeted backfill, pending-cell processing and weekly refresh. A large-load confirmation flag gates initial downloads; weekly refresh is disabled until configured.
- `backend/app/decisions/environmental_analysis.py` is pure. It receives daily records and dated crop events; it does not call MongoDB, NASA, the clock or the filesystem.
- `backend/app/decisions/product_direction.py` contains pure crop scheduling, hard filtering, deterministic scoring, ranking and explanations.
- `backend/app/farms/catalog_seed_data.py`, `backend/app/farms/seed_catalogs.py`, and `backend/app/repositories/crop_catalog.py` provide the shared crop/calendar/reference catalogues and operator-managed seed path.
- `backend/app/api/workflows.py` assembles owner-scoped farm, climate, catalog, analysis, recommendation and result services. It reads climate only and persists the result through the established result repository.
- Existing auth, Mongo connection, farm ownership and result history modules are reused. No second NASA client or Mongo client was introduced. The new versioned pure engine is the active implementation for the changed Product Direction; the older engine remains inactive for compatibility rather than being called alongside it.

### Legacy modules intentionally retained

The repository still contains the earlier `EnvironmentalSnapshot` model/repository/service, the NY-8 evidence-gated `rotation.py`/`scoring.py` path, NY-38/NY-40 assessment services, and some legacy Farm/result fields. They are not called by the new `/environment` and `/recommendations` workflow. They remain so existing records and prior tests/contracts can still be read while the new direction is adopted. Do not extend both old and new flows. A separate cleanup/migration should decide whether old snapshot and profile collections can be archived after production data and saved-result consumers have been audited.

### Frontend

- `frontend/src/api/farms.ts` describes the dated farm/environment contracts and the redacted location response.
- `frontend/src/api/recommendations.ts` sends at most one selected priority and no farmer-supplied climate date ranges.
- `frontend/src/pages/FieldSetup.tsx` loads crop and reference options from the backend, collects one to three dated events and labour capacity, and limits the farmer to one priority.
- `frontend/src/pages/Comparison.tsx` displays climate readiness/coverage, the historical windows, three future events, scores, weights, evidence and trade-offs. It labels historical regional grid weather and provisional calendar assumptions.

## 4. MongoDB documents and indexes

MongoDB uses Beanie/PyMongo through the existing shared connection and central document registry. Application references are document IDs/string cell keys and are enforced by owner-scoped repository queries; no relational foreign-key behavior is assumed.

| Collection | Main fields | Important indexes / privacy boundary |
|---|---|---|
| `climate_cells` | Opaque `cell_key`, NASA-returned grid geometry/resolution, first/data-through dates, load/sync state, source/parameter metadata, completed/failed chunks, safe error and expiring lease owner | Unique `cell_key`; queue/sync indexes. Grid geometry is internal operational metadata. |
| `climate_daily` | `cell_key`, day, nullable `rain_mm`, `t2m_c`, `t2m_max_c`, source products, update time | Unique `(cell_key, day)` plus recent-read index. No farm ID, farmer identity or private farm coordinates. Only the loader/worker writes these records. |
| `analysis_config` | Immutable version, active marker, climate thresholds, reference years, scheduler horizon/buffer, weights | Unique version and unique partial active index. Defaults are configurable MVP policy, not validated universal constants. |
| `crops` | Stable key, aliases/group, traits, maturity, production system, per-trait source/evidence kind/confidence/limitations, selectable/candidate flags and catalog version | Unique crop key and active usage index. One collection serves history selection and candidate generation. Rice variants are distinct records; unknown rice ecology remains history-only. |
| `crop_profile_revisions` | Earlier NY-38/NY-40 scoped trait revisions | Retained for compatibility with the inactive legacy recommendation service; the current Product Direction workflow reads the researched traits from `crops`. Do not treat this sidecar as a second current source of truth. Review and migrate before removing it. |
| `crop_calendars` | Location/crop/season/version, optional window, source/status | Unique scope/version and one active row per scope. A missing row means no supported window at that location. |
| `supported_locations` | Public location key/label and private backend reference coordinates/source; resolved cell geometry/key | Unique location key and selectable ordering index. Public APIs return only key/label. |
| `farms` | Owner, location key, labour, one priority, availability date, soil/irrigation context and ordered dated crop events | Existing owner-scoped lookup indexes. Owner comes from session; query filters use authenticated owner. |
| `rotation_results` | Owner/farm IDs, input/history snapshot, climate cell/data-through, analysis/config/catalog/calendar/engine versions, result options | Existing owner/farm history and result indexes. Old result schemas are retained for reading. |

Exact index definitions live beside their Beanie documents. The daily collection key is derived from NASA's returned geometry, not arbitrary rounding of a farm coordinate.

## 5. API and frontend contract changes

The current farmer-facing path is:

1. Authenticate and load supported locations, crops and farm reference options.
2. Create/update a farm using a supported `location_key`, labour capacity, at most one priority, and one to three actual historical crop events (crop IDs, order, start/end dates, and rice production system when known). Do not send owner ID, private coordinates, NASA date ranges or future planting slots.
3. Read `GET /api/v1/farms/{farm_id}/environment`. The response includes the safe location label, climate load state, data-through/coverage and event-window findings. It never returns farm/reference coordinates.
4. Request `POST /api/v1/farms/{farm_id}/recommendations` with an empty body or one allowed priority override. The server reads the farm's persisted dates and local climate, schedules future planting windows and stores the generated result.
5. Retrieve saved history/detail through the existing owner-scoped result endpoints.

`GET /api/v1/crops` and `GET /api/v1/farms/reference-options` serve backend-managed choices. Environmental status is explicit (`location_unmapped`, `pending`, `loading`, `ready`, `partial`, `error`, `unavailable`). Missing metric values are null and their valid/missing day counts remain visible. A missing weather finding never receives an assumed value or weather weight increase.

The engine's score is a transparent relative weighted average, not a forecast or probability. The response explains per-step ratings and weights, crop/period provenance, assumptions, trade-offs, exclusions and versions. Up to three options are returned; fewer or none are valid outcomes. Current-practice baseline is not in the new farmer-facing flow.

## 6. NASA data and background jobs

The adapter requests only `PRECTOTCORR`, `T2M`, and `T2M_MAX`, community `AG`, UTC, JSON. The requested history starts `1981-01-01` and ends at the latest complete date allowed by the configured publication lag. NASA's response supplies returned grid geometry, units, source products and spatial metadata. The live response can provide a 3D GeoJSON point; the original geometry is retained, while the opaque cell key hashes the exact returned horizontal point and excludes optional Z. Confirmed fill values and unavailable days stay null.

On first farm use, its supported location must already be mapped to a returned NASA grid key. Farm creation registers a missing climate cell as pending; it does not hold the farmer request open for a long data download. An operator runs the separate worker:

- Backfill: one selected cell at a time (or explicitly selected pending cells), in resumable decade-sized requests.
- Refresh: weekly, last 120 days only, after initial history is reviewed and the setting is enabled.
- Safety: per-cell database lease, safe provider errors, retryable failed chunks, idempotent cell/day upserts, no bulk overwrite on malformed/all-null responses, and no user-session NASA requests.

Do not launch the full three-location 1981-to-current history load until mocked loader tests, isolated Mongo tests, API checks and one small live response verification have passed. The scheduled worker must run as one external cron/worker process, never independently in every FastAPI worker. NASA's response may contain corrected or replaced recent values; the 120-day upsert window captures that behavior without repeatedly downloading the full archive.

## 7. Crop evidence, calendars and validation gaps

Starter crop options are maize, cowpea, groundnut, cassava, yam, and rice with separate upland, rain-fed lowland and irrigated rice records. Plantain and sorghum are history-selectable only. Trait values carry evidence type (`direct_source`, `analogue_estimate`, `desk_synthesis`), confidence, applicability and limitations. These are research estimates authorized for MVP comparison, not local agronomic approval. Research values include:

- Maturity examples from the [CSIR Ghana variety catalogue](https://technologies.csirgh.com/maincropvarieties) and [Ghana MoFA Rice Production Guide](https://mofa.gov.gh/site/images/pdf/production_guides/RICE_Production_Guide.pdf), with crop/variety/ecology scope preserved.
- Generic crop water ranges and sensitivity categories from [FAO's crop water requirements table](https://www.fao.org/4/S2022E/s2022e07.htm); the source itself calls these rough indications, not local recommendations.
- Soil-effect and labour estimates from Ghana/West African sources, including [Ghana maize/legume field research](https://pmc.ncbi.nlm.nih.gov/articles/PMC5614088/) and [cassava-maize soil research](https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2023.1095207/full). Transferability is limited; labour categories are relative estimates, not measured household capacity.

Current seed examples are provisional, and any analogue must be labelled as such. Crop maturity-range midpoint determines the configured `Fast`/`Medium`/`Slow` class. Rice is never inferred from irrigation access; unknown rice-system history does not become a recommendation candidate. Seed values need agronomist/farmer review, especially soil effects, labour categories, water resilience, cultivar/ecology scope and the chosen analogues.

Seeded calendars are deliberately scoped:

- Ejura and Anyinasu maize major/minor examples use the Ghana MoFA transition-zone guide and are marked provisional.
- Ejura and Anyinasu cowpea minor window uses a Ghana-wide source; local adaptation is unvalidated.
- Anyinasu yam window is based on a local study's key-informant report and remains provisional.
- The Field Shift follow-up adds provisional Kintampo North maize major/minor and yam major windows under `product-direction-kintampo-v1`. Apply them with the existing catalog seed command. See the [FAO suitability evidence](research/field-shift-gaez-suitability.md) for regional context and the crop mapping limits.
- Groundnut, cassava and rice remain without inferred planting windows.

Public source locations are inhabited-place references, not farm-specific survey coordinates. Their mappings to NASA-returned grid cells were checked with one-day live requests and used for the controlled loads above; local confirmation is still needed before describing them as representative of individual farms. The NASA API's official [Daily API documentation](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) and [meteorological data-source notes](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/) explain the daily service and source products. Live response metadata remains authoritative for units, fill values and resolution.

## 8. Recommendation method and edge cases

The pure engine follows **generate → filter → score → explain**:

1. Generate every ordered three-crop sequence from enabled profiles.
2. Remove crop profiles that exceed farmer labour capacity, are disabled, or have unsupported rice ecology. Schedule each remaining step from the location/crop calendar, starting at `max(today, available_from)`, and require a window within 24 months. Expected harvest is a maturity range; the next step begins after the latest expected harvest plus 14 days.
3. Score water resilience, soil effect, growth speed and labour with ordinal 3/2/1 values and versioned weights. Step one may receive water weight 2 when the latest historical event has an available Drier, Hotter or Longer-than-usual dry-spell finding. A pending/missing/partial parameter contributes no synthetic value. Steps two/three do not inherit that weather adjustment. Soil weight may rise based on the preceding crop. One farmer priority increases its criterion weight by one.
4. Sort by weighted score descending, then crop-group diversity transitions descending, then the selected-priority trait total, shorter scheduled horizon and crop-key order. Diversity has no numeric score bonus and never hard-excludes a sequence.
5. Return the top three (or fewer). If none survive, return no options with a stable reason instead of weakening hard constraints or fabricating a result.

This is the selected edge-case policy for missing/partial climate and candidate shortages: keep the farmer's farm/environment view available; generate only when catalog/calendar/labour constraints permit; use no weather adjustment when needed evidence is absent; preserve nulls/status; and return fewer/no options instead of relaxing rules. It protects the product direction's data integrity and does not imply that a historical weather observation is a forecast.

## 9. Farm migration, security and privacy

One Farm document represents one decision plot. The new model stores ordered, dated events. Invalid chronology, future dates and overlapping sole-crop events are rejected; gaps are allowed. Existing free-text crop lists are not converted into invented events. The legacy-migration operator marks those farms for re-entry while retaining original records for reference. It does not delete or rewrite old results/snapshots.

Authentication remains the existing email/password HttpOnly cookie session with CSRF protection on mutations. Farm and result access stays owner-scoped. The owner identity comes from the authenticated principal, not request payload. Public responses/logs omit exact coordinates and credentials. NASA grid geometry is stored only in backend data needed for reuse; diagnostic text and stored safe error fields omit raw upstream responses and coordinates.

## 10. Tests and verification status

### Existing / added checks

- Unit coverage exists for NASA normalization, supported-location/farm contracts, Mongo model/index behavior, historic analysis, scheduler/scoring, catalog seed behavior and the workflow API.
- New tests cover decade chunking, resumable/repeated loader behavior, null/fill handling, weekly refresh preservation, generated top-three output, criterion weights, diversity tie ordering, weather status and matched comparison missingness.
- `backend/tests/integration/test_authenticated_workflow.py` exercises actual local MongoDB with a dedicated temporary database and synthetic climate rows; it mocks NASA and must not use production data.
- Frontend provides `typecheck`, `lint`, and `build`; no dedicated UI unit-test runner is configured.

**Completed verification on 9 November 2026:**

- Backend suite with the MongoDB integration switches enabled against `mongodb://localhost:27017`: **250 passed**. Each integration test creates a uniquely named disposable database and drops it afterward. The climate integration test verifies Beanie creates the unique `(cell_key, day)` index and MongoDB rejects a duplicate. Test climate data is synthetic; NASA is mocked in automated tests.
- Ruff lint: **passed**. Ruff format check: **129 Python files already formatted**.
- Frontend `npm run typecheck`, `npm run lint`, and `npm run build`: **all passed**.
- `git diff --check`: **passed**; Git emitted only line-ending normalization notices for Windows worktree files.
- A synthetic 15 March–30 April 2025 analysis window run against the persisted Ejura NASA archive returned `ready`, 47/47 valid rainfall days, and explicit rainfall/temperature/dry-spell categories. This is a data-path check, not a farmer-reported crop event or an agronomic recommendation.
- A separate one-day live NASA POWER request for the provisional Ejura reference point on **2025-01-01**: **normalized successfully**. NASA returned API v2.10.3, source products `MERRA2`/`POWER`, a source-native resolution note, and three-dimensional GeoJSON point geometry. All three requested parameters were present with one valid day and no missing days; precipitation units were `mm/day`, temperature units were `C`, and the confirmed fill marker was `-999`. NASA did not provide per-parameter `source` fields in this response. Exact coordinates and daily values were not printed or persisted.

The live one-day request validated the adapter. Each supported location was mapped with one-day NASA requests, and the returned NASA cell geometries/keys were persisted in the configured MongoDB without exposing coordinates. The controlled historical loads then completed for all three distinct cells, in five resumable chunks per cell, from 1981-01-01 through 2026-11-06. Each cell has **16,746 daily records and 16,746 distinct dates**, with **zero null/missing values** across `rain_mm`, `t2m_c`, and `t2m_max_c`; all five chunks completed, with no failed chunks or stored safe errors. The required unique `(cell_key, day)` database index is present and verified. This verifies provider coverage for these periods in the current database; it does not make the town reference points farm-specific or imply on-farm observations. NASA may revise recent values, which is why weekly refresh remains a separate operation.

The 9 November development catalog verification found 8 history crops, 8 enabled recommendation profiles (including 3 rice systems), 3 Ejura calendar rows, 4 Anyinasu calendar rows, 0 Kintampo calendar rows, and active `product-direction-config-v1`. All three places resolved to a `ready` climate cell with `data_through=2026-11-06`. That database check predates the Field Shift Kintampo seed revision.

### Still required before rollout

1. The automated backend, local MongoDB and frontend checks above pass.
2. The idempotent catalog seed has been run and verified in the configured NovaYield database. For another environment, confirm the target database before running the documented seed and any legacy-history marker.
3. The configured development database has complete archives for Ejura, Anyinasu and Kintampo through 6 November 2026. For another environment, map and load its intended cells deliberately; do not assume this local database is shared.
4. Weekly sync remains off. Configure a separate scheduled worker and enable the weekly 120-day refresh only after that deployment target, retry/alerting, and database have been reviewed. Do not run the worker inside an API process.
5. Obtain local agronomist/farmer review for provisional crop traits and location-specific calendars before describing generated rankings as locally validated planting advice. Apply the Kintampo seed revision in the intended environment to make its provisional windows schedulable.

## 11. Implementation order / file-level plan

| Order | Work | Main files | Integration gate |
|---|---|---|---|
| 1 | Confirm current direction, branch, privacy rules, configs | `AGENTS.md`, decision record, `backend/app/core/config.py` | Product direction and 9 Nov clarifications are recorded. |
| 2 | Shared climate collection and location-to-cell mapping | `models/climate_store.py`, `repositories/climate_store.py`, `jobs/resolve_nasa_grid.py`, `integrations/nasa/power.py` | One returned geometry maps to one stable opaque key; indexes/init work. |
| 3 | Resumable history loader and weekly worker | `services/climate_ingestion.py`, `jobs/climate_worker.py` | Fixture/error/retry/lease tests pass before any large NASA pull. |
| 4 | Crop/catalog/farm contract and operator seeds | `models/crop_catalog.py`, `models/farms.py`, `schemas/farms.py`, `farms/catalog_seed_data.py`, `repositories/crop_catalog.py`, farm routes | One priority, dated events, no coordinate exposure; missing location/crop/calendar evidence explicit. |
| 5 | Pure historical analysis | `decisions/environmental_analysis.py` | Tests cover reference dates, missingness, leap dates, dry spell and since-harvest. |
| 6 | Pure future scheduler and scoring | `decisions/product_direction.py` | Calendar/labour/rice filters, rules, deterministic ordering and explanations pass. |
| 7 | Owner-scoped orchestration and immutable result snapshot | `api/workflows.py`, `repositories/rotation_results.py`, result schemas/routes | Cross-user protection, no NASA on request, result provenance and OpenAPI contract. |
| 8 | Frontend contract and documentation | `frontend/src/api/*`, `FieldSetup.tsx`, `Comparison.tsx`, README/docs | API-backed lists, one priority, status and three-option explanation render consistently. |
| 9 | Verification / controlled rollout | `backend/tests`, frontend scripts, operator instructions | Full automated checks pass; live one-day response reviewed; only then manual backfill approval. |

Parallelism: after the climate model/DTO and crop/event contracts are agreed, worker ingestion, farm catalog/farm history, pure analysis and frontend contract work have mostly separate module boundaries. Shared models, router registry, config, seed version and result schema require coordination. No ticket-level isolation can eliminate integration conflicts, so changes to those shared files should be sequenced or reviewed together.

## 12. Open contradictions and decisions to preserve

| Conflict | Resolution used | Remaining implication |
|---|---|---|
| Earlier PRD/Jira describes per-request snapshots and a 12-month context; Product Direction replaces them with local cell history and event windows. | Use `climate_cells`/`climate_daily`, actual crop windows and separate since-harvest period. Keep old snapshot/result documents readable. | Old legacy modules/routes may remain for prior records/tests; do not use them in the new farmer flow. |
| The PDF asks for crop values only when evidence is supported, while the 9 Nov clarification explicitly authorizes researched close-crop analogues and activating starter examples. | Seed estimates only where sources/analogue are documented; store evidence kind, confidence and transfer limits; clearly mark provisional. | Agronomist/farmer review is still needed; do not call these locally validated. |
| The PDF calls crop diversity a soft tie preference but its tie-break ordering is not the latest PO preference. | User clarification places diversity immediately after score. No numeric bonus or hard exclusion. | Engine version must be incremented if ordering behavior changes after result creation. |
| Previous research decisions describe evidence-gated scoring and a water/soil fallback. | New Product Direction replaces this with four configured criteria and an absent-weather no-adjustment behavior. | Do not silently restore older fallback logic. |
| A public point is not a farm point, and NASA returns grid geometry not an arbitrary rounded farm coordinate. | Resolve one supported location server-side, keep coordinates/geometry internal, derive cell identity from returned NASA geometry. | Verify actual response metadata and public point-to-grid mapping before bulk load. |
| Seed crop/calendars are provisional but the algorithm can rank them. | Present rankings as relative and provisional, preserve each source/assumption, expose environment and calendar status. | Do not describe a top-three list as validated planting advice. |

## References

- Supplied source: *NovaYield Product Direction.pdf*, dated 7 November 2026. Product Owner clarifications recorded in the active implementation request, 9 November 2026.
- [CSIR Ghana crop variety catalogue](https://technologies.csirgh.com/maincropvarieties).
- [Ghana MoFA Rice Production Guide](https://mofa.gov.gh/site/images/pdf/production_guides/RICE_Production_Guide.pdf).
- [FAO crop water needs table](https://www.fao.org/4/S2022E/s2022e07.htm).
- [Ghana maize/legume field study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5614088/).
- [Ghana cassava/maize long-term soil study](https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2023.1095207/full).
- [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/).
- [NASA POWER meteorological source notes](https://power.larc.nasa.gov/docs/methodology/data/sources_meteorology/).
