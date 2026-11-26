# Open items — ts-convert-from-sisense

Unverified assumptions / follow-ups. Status vocabulary: `TO VERIFY | VERIFIED | KNOWN |
DEFERRED | WONT-FIX`. Each must reach VERIFIED (live or via MCP spec) or be explicitly
deferred before this ships live.

## #1 — Live end-to-end conversion on a real cluster — VERIFIED 2026-07-21

Ran the full chain (`parse` → `build-model` → `ts tml lint` → `ts tml import` → `build-liveboard`
→ import) on **ps-internal**, a test Org, against the live **"Sisense Migration - Databricks"**
connection (`workspace.sisense_demo`, the captured `sample_ecommerce` bundle):

- **Model TML validated + imported OK** against the real connection, binding to the live
  Databricks tables (Commerce/Category/Brand/Country); `ts tml lint` CLEAN.
- **Numbers reconcile (no fan-out):** total `SUM(Revenue) = 5315.0`; `Revenue` grouped by
  `Category` (Electronics 2190 + Home 910 + Apparel 835 + Sports 820 + Toys 560) = **5315.0** —
  the `Commerce → Category` MANY_TO_ONE join does not inflate the measure.
- **Liveboard path:** `build-liveboard` emitted 9 Answers (8 Migrated, 1 Approximated =
  bubble→scatter) + 1 tabbed Liveboard; all 10 objects imported OK (0 errors) against the model.

Test objects were deleted after verification (`metadata/delete` → 204); the pre-existing
warehouse tables were left untouched. Merge gate satisfied.

## #2 — Chart-type fidelity via the shared emitter — VERIFIED (design)

The shared emitter (`ts_cli.tableau.liveboard`) is on `main` (merged in #253). `build-liveboard`
emits Answer + tabbed-Liveboard TML directly via the emitter's `build_answer`, passing the
**Sisense-resolved `ts_chart`** (COLUMN/PIE/KPI/…) and status per widget (`answers.build_liveboard_result`).
It deliberately does NOT go through `build_from_spec`'s mark path: main's `build_from_spec`
`_resolve_ct` **re-infers** the chart from a mark and hardcodes `Migrated` (the `ts_chart`-aware
variant is only on the unmerged #255), which would silently mis-type KPIs/pies and hide the
review signal. Driving `build_answer` directly makes the chart mapping correct on today's `main`,
**independent of #255**. The Sisense dashboard filter bar is injected as `liveboard.filters`
chips after emission. Live-render fidelity of the emitted TML is covered by #1 / #5.

## #3 — Live Sisense REST fetch not built — DEFERRED

The converter consumes an **offline bundle JSON** (`{dashboard, widgets, datamodel}`) already on
disk; there is no command that pulls a dashboard, its widgets, and the datamodel directly from a
Sisense server's REST API. A user must assemble the bundle from a Sisense export first. A future
`ts sisense fetch` (following the `.claude/rules/ts-cli.md` "new command" flow: MCP-spec the
Sisense REST endpoints, verify live, then add the command) would close this. Deferred — the
offline path is the intended v1 surface.

## #4 — JAQL formula subset breadth — TO VERIFY on real dashboards

The deterministic `FUNCTION_MAP` in `ts_cli/sisense/functions.py` covers the common
subset observed in the sample bundles. Against a broader set of real customer dashboards, some
functions currently emitted as Migrated may still be rejected by the ThoughtSpot engine (e.g.
`median`, `stddev`/`variance` argument shapes), and some now marked NEEDS REVIEW may turn out to
have a safe deterministic port. Confirm against real JAQL on the first few live migrations; the
runtime prune step (Step 2) is the safety net until then.

## #5 — Numeric-range / date-bucket filter-chip fidelity — TO VERIFY live

The dashboard-filter → Liveboard-chip mapping (member→`IN`, exclude→`NOT_IN`, numeric range→
`GE`/`GT`/`LE`/`LT`/`BW_INC`/`BW`/`EQ`; date `level`→`HOURLY…YEARLY`) is derived from the
standalone converter and the worked examples, not yet round-tripped through a live Liveboard
import. Confirm the chip operators and bucket tokens render and filter correctly on a real
Liveboard. **Specifically verify the two-sided range boundary:** ThoughtSpot exposes `BW_INC`
(both-inclusive) and `BW` (both-exclusive); a **mixed** inclusive/exclusive Sisense range
(e.g. `from:10, toNotEqual:100`) keeps both bounds but is emitted as `BW_INC`, so the exact
open/closed boundary is approximate — confirm whether a mixed-bound operator exists on the
target build and tighten if so.

## #6 — Widget measures, measured values, widget filters, ignore, pivots — VERIFIED 2026-11-26

`build-liveboard` now emits widget measures as Answer formulas, measured values as
`group_aggregate` over a conditional aggregate, widget `metadata.ignore` as `group_aggregate`
filter sets, tile filters shadowed by a Liveboard filter as measure conditions, KPI tiles with
a y axis, and flattened pivots as `TABLE_MODE` grids. Verified on **ps-internal** (a test Org)
over a single-table Databricks dataset shaped like a recruiting pipeline (synthetic rows):
the model and a 14-tile Liveboard generated from a real-shaped bundle (with three synthetic
widgets added for `ignore.ids`, `ignore.all` and a Columns-panel pivot) imported with no
error, and every tile returned data. Numbers reconciled with direct SQL on the same table:

- distinct jobs 120, published 83, unpublished 37; distinct applications 2,500; positions
  755, unpublished positions 246; pivot cells (18, 20) and (25, 14) for two companies;
- under a Liveboard runtime filter on the status column: the `ignore.ids` tile and the
  `ignore.all` tile stay 2,500, the measured value "Unpublished Jobs" stays 37, and a tile
  whose own filter is `Status = Published` reads 0 (the Sisense intersection) rather than the
  37 a search filter would give;
- under a runtime filter on the company column: the `ignore.ids` tile narrows to 376 (= SQL)
  while the `ignore.all` tile stays 2,500.

Found during verification: a `GRID_TABLE` emitted in `CHART_MODE` imports cleanly but its
Liveboard tile returns "No data source found for the query"; the same Answer in `TABLE_MODE`
renders. The Sisense path now sets `TABLE_MODE`. The shared emitter
(`ts_cli/tableau/liveboard.build_answer`) still emits `CHART_MODE` for every chart type, so
the other converters' grids are exposed to the same failure (follow-up, not changed here).

Test objects were deleted after verification.

## #7 — UNION of timestamps in a hand-written SQL view — KNOWN (Snowflake)

When a Sisense cube is rebuilt as a ThoughtSpot SQL view (a custom table, or several Sisense
tables unioned into one event table), Snowflake refuses a `UNION` whose branches mix
`TIMESTAMP_NTZ` with `TIMESTAMP_TZ`/`TIMESTAMP_LTZ` columns; casting every timestamp branch to
`::TIMESTAMP_NTZ` fixed it on a production Snowflake migration (2026-11-26). Not reproduced on
ps-internal (no active Snowflake connection there). Databricks does not fail: a `UNION ALL` of
`TIMESTAMP` and `TIMESTAMP_NTZ` returns `TIMESTAMP` (probed 2026-11-26), but the values are
then read in the session time zone, so cast there too when the sources disagree.
