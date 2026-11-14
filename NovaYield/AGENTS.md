# NovaYield Project Context

The current product baseline is the **NovaYield Product Direction dated 7 November 2026**, as clarified by the Product Owner on 9 November 2026. Read [the implementation guide](analysis_docs/product-direction-implementation.md) and §9 of [the research and decision record](novayield-research-and-product-decisions.md) before changing product behavior, architecture, or data contracts. The PDF is `C:\Users\BOAKYE\Downloads\NovaYield Product Direction.pdf`.

- The Product Direction supersedes earlier Jira tickets, NY-38/39/40 handoffs, and previous scoring/cache contracts when they conflict.
- The Product Owner's 9 November clarifications are part of the baseline: crop values may use explicitly documented analogues; crop/calendar estimates remain provisional; farmers select one priority; coordinates stay server-side; missing climate values stay null; crop-group diversity is a soft preference and the first tie-break after score; MVP data is managed through seed/operator scripts, with no agronomist admin UI.
- Do not claim that desk research or an analogue is local agronomic validation. Keep the source, evidence kind, confidence and limitations with every seeded crop value. Do not silently promote a provisional planting calendar or crop profile to locally reviewed.
- A crop can be scored only when its required traits and maturity range exist. Rice must remain separated by known production system; never infer its system from irrigation access.
- Store and analyze one NASA POWER Daily series per NASA-returned grid cell. Use only `PRECTOTCORR`, `T2M`, and `T2M_MAX`; store missing values as null. Farmer requests read MongoDB and never call NASA. Keep the 1991–2020 normal distinct from the 1981-to-current stored archive.
- Analyze actual dated crop-history windows plus a separate since-harvest weather note. The artificial 12-month context window is retired. Never infer dates/order from legacy free-text crop history.
- Pure analysis, scheduling, and recommendation functions must not call HTTP, MongoDB, the clock, or the filesystem. The standalone loader/weekly worker owns climate writes; do not run a scheduler in FastAPI workers.
- Resolve a location key to its backend-only reference coordinates. Never serialize coordinates or include them in logs/errors. Keep farm/result reads owner-scoped and preserve the same not-found behavior for missing and non-owned records.
- Do not run a full NASA backfill until fixture, integration, and database checks pass and an operator deliberately starts it. A one-day live metadata check is acceptable; do not add unrelated NASA datasets.
- Preserve existing user work and history. Do not delete old snapshots/results; keep legacy results readable. Do not modify Jira or commit unless explicitly requested.
