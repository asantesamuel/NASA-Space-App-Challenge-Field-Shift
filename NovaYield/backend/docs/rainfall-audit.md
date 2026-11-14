# Ghana pilot rainfall audit

Run this offline comparison with exported IMERG science data and read access to the existing POWER archive. The command covers Ejura, Anyinasu and Kintampo from 1 January 2023 to 31 December 2024. It writes 12 crop-length benchmark rows and 72 monthly rows to local Markdown and CSV reports.

## Prepare the IMERG extract

1. In [NASA Earthdata Search](https://search.earthdata.nasa.gov/) or [GES DISC](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGDF_07/summary), choose GPM IMERG Final Daily collection `GPM_3IMERGDF`, collection edition `07`, granule edition `V07B`. Verify the latest accessible date and obtain just the study dates and needed subsets using the provider's numeric subsetting or equivalent approved download. Use the [collection DOI](https://doi.org/10.5067/GPM/IMERGDF/DAY/07) and check the [version transition](https://gpm.nasa.gov/data/news/update-imerg-v08-transition-schedule-aug-2026). Use an Earthdata account with access where the provider requires it.
2. Check the daily science variable, fill value, 0.1° grid, units and time bounds in the granule metadata. Keep the standard Final precipitation field and UTC midnight-to-midnight days. Resolve each pilot reference privately from `supported_locations`. Pick the containing IMERG cell in the **native** grid with west/south edges inclusive and east/north edges exclusive. No interpolation or remapping to the POWER cell.
3. Convert a verified daily mean in mm/hr to a daily total by multiplying by the verified 24-hour duration. Keep numeric daily accumulations (including daily values expressed as mm/day for that one-day interval) as supplied. Apply any declared scale and offset to valid values only. Export missing and fill as blank and retain a valid zero. The command also recognizes the exact declared negative fill marker for defensive handling. Other invalid, non-finite or negative values fail validation.
4. Export UTF-8 CSV with exactly `location_key,date,rain_mm` and ISO calendar dates. Each location/date may appear once. Missing days may be omitted. Generate a lowercase SHA-256 digest from the final CSV bytes. Keep data extracts, credentials and spatial metadata outside Git.

## Describe and run the input

Use the following manifest structure. This example is a fixture. Replace the hash and populate all source fields from the actual files, including the source units and the last archive date you checked. Use `"sample_kind": "real"` for a provider extract paired with the actual POWER archive. `coverage_start` and `coverage_end` bound the extract, even if individual days are missing. For either sample type the tool reports the full fixed study.

```json
{
  "collection": "GPM_3IMERGDF",
  "collection_version": "07",
  "edition": "V07B",
  "run": "Final",
  "doi": "10.5067/GPM/IMERGDF/DAY/07",
  "source_variable": "precipitation",
  "source_units": "mm/day",
  "normalized_units": "mm/day",
  "time_basis": "UTC 00:00–24:00",
  "grid_degrees": 0.1,
  "extraction": "containing_cell_west_south_inclusive",
  "source_fill_value": -9999.9,
  "latest_source_day_checked": "2025-09-30",
  "retrieved_on": "2026-11-14",
  "coverage_start": "2023-01-01",
  "coverage_end": "2024-12-31",
  "csv_sha256": "replace with the 64-character lowercase SHA-256 digest",
  "sample_kind": "fixture"
}
```

Set `NOVAYIELD_AUDIT_MONGODB_URI` and `NOVAYIELD_AUDIT_MONGODB_DATABASE` through the operator environment. Use a role with `find` privileges for `supported_locations` and `climate_daily` only. The command does not read the app's environment file or initialize database indexes. From the backend directory run:

```powershell
python -m app.jobs.rainfall_audit --imerg-csv C:/local-audit/imerg.csv --manifest C:/local-audit/manifest.json --output-dir C:/local-audit/report
```

The report uses inclusive UTC dates and includes leap day in the February summary. Both totals include only shared valid days. Check coverage before interpreting totals and compare daily differences with monthly summaries. The longest dry spell is reported only for complete benchmark windows using the MVP threshold below 1 mm/day. A blank metric represents unavailable data. An incompatible source, unit or time basis fails the run with a validation error. The benchmark intervals do not represent a farmer's crop history.

The products estimate rain at different grid scales. Their difference does not identify which estimate is closer to local rainfall. A later gauge study could align accumulation intervals, record quality and data rights, and keep an independent group of sites or dates for evaluation. [Ghana Meteorological Agency data request](https://www.meteo.gov.gh/data-request/)

The first real pilot comparison is pending. The implementation was exercised with
synthetic IMERG input and a disposable POWER archive. To run the real sample,
provide the pinned numeric IMERG subset and a read-only account for the existing
POWER study archive.
