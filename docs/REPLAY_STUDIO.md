# Replay Studio and Scenario Builder

Replay Studio extends the existing scripted replay pipeline. It uses the same replay controller and hooks as the live console, so a custom scenario goes through detection, attack graph updates, Precog forecasts, incident correlation, and simulated containment. Scenarios are data only; the platform never evaluates user-provided code.

All activity remains a simulation. The scenario builder, run archive, and studio display simulation disclosures and use the existing one-process Flask service and polling model.

## Workflows

### Scenario library and builder

Open `/scenarios` to browse the four shipped scenarios and saved user scenarios. Create a scenario at `/scenarios/new`, or edit a saved `user-` scenario at `/scenarios/:id/edit`. The editor organizes technique, traffic, and attempt events into lanes by demo host. It supports event offsets, pause-for-decision and compromise flags, shipped templates, JSON import/export, server validation, and a dry run that estimates host-state changes and Precog forecasts without changing the live world.

The server checks every draft before saving or running it:

- At most 200 events, with ordered offsets and a maximum duration of two hours.
- Only known demo host IDs and technique IDs; user input cannot supply host IP addresses or file paths.
- Traffic endpoints must be distinct valid hosts and ports must satisfy the scenario schema.
- Scenario identifiers must use the `user-` prefix and a lowercase slug. Shipped scenarios are read-only.
- At most 50 user scenarios are retained. Invalid JSON, unknown fields, oversized content, traversal-like IDs, unknown hosts/techniques, and invalid event order are rejected with a path and reason.

Scenario drafts are persisted under `lead-core/backend/data/scenarios/` using atomic temporary-file replacement. The filename is derived from the validated scenario identifier, never from an arbitrary path. Existing shipped scenarios remain unchanged.

### Replay studio

Open `/replay` to select and start a scenario. The controls support pause/resume, speed from 0.25× through 8×, breakpoints on scenario event sequence numbers, step forward, step back, and seeking to a recorded position. The studio records the initial state and a snapshot after each processed event. Stepping and seeking restore the recorded world, graph, packet store, incidents, and containment state before continuing the same scenario.

Each completed run receives a sequential `RUN-000001` style identifier. A fresh/empty run-data folder starts at `RUN-000001`; saved finished-run history supplies the next number after a normal restart. Completed run records are stored beneath `lead-core/backend/data/runs/`. The service retains the newest 50 finished runs and at most 2,000 snapshots for the active recording. A restarted process loads finished runs and saved user scenarios; the in-memory live world and an unfinished replay start clean.

The archive at `/runs` links to each run detail page and offers side-by-side comparison at `/runs/compare?a=…&b=…`. Comparisons show additions and removals across alerts, incidents, forecasts and actions, plus outcome and metric changes. Wall-clock fields are excluded from the normalized comparison; the displayed run timestamps still reflect when each run actually occurred. Run identifiers and timestamps are not claims of model determinism.

## API

All routes are under `/api/x/`. Write requests use the platform's JSON content-type and cookie-session CSRF checks, input-size limit, server-side validation, role checks, and heavy-request rate limits.

| Method and route | Purpose |
|---|---|
| `GET /scenarios` | Shipped and saved scenario summaries |
| `GET /scenarios/options` | Known demo hosts and ATT&CK techniques |
| `GET /scenarios/{id}` | Scenario detail and whether it is editable |
| `GET /scenarios/{id}/export` | Download scenario JSON |
| `POST /scenarios/validate` | Return all validation errors with JSON paths |
| `POST /scenarios/dry-run` | Estimate host states and forecasts without live mutation |
| `POST /scenarios` | Save or update a validated `user-` scenario |
| `DELETE /scenarios/{id}` | Delete a saved `user-` scenario |
| `GET /replay/studio/status` | Playback status and current run |
| `POST /replay/studio/start` | Start an authorized replay |
| `POST /replay/step` | Advance one event while paused |
| `POST /replay/step-back` | Restore the preceding recorded position |
| `POST /replay/seek` | Restore a recorded position |
| `POST /replay/speed` | Set speed between 0.25× and 8× |
| `POST /replay/breakpoints` | Set event-sequence breakpoints |
| `GET /runs` | List recent finished runs |
| `GET /runs/{id}` | Run summary and final evidence |
| `GET /runs/{id}/snapshots` | Snapshot index for time travel |
| `GET /snapshots?run=…&version=…` | Read a recorded snapshot |
| `GET /runs/compare?a=…&b=…` | Compare two finished runs |
| `GET /feed?since=…` | Shared incident/run/action/note domain versions |

Viewers can read and compare. Analysts and admins can validate, dry-run, save, and run scenarios. Admin-only restrictions continue to apply to administrative actions. No route changes the legacy world-state response contract.

## Contracts

Each C2 response has its own JSON Schema and sample, checked by `contracts/check_contracts.py`:

`breakpoint_set`, `run_comparison`, `run_detail`, `run_snapshot`, `run_summary`, `scenario_builder_options`, `scenario_draft`, `scenario_dry_run`, `scenario_library`, `scenario_summary`, `scenario_validation`, `snapshot_index`, and `studio_status`.

The replay routes are covered by `lead-core/integration/tests/test_replay_studio.py`; the scenario builder logic and rendered routes are covered in `web/src/areas/replay/` tests. Browser workflow evidence is saved beneath `docs/audit/screenshots/phase-c/`.

## Known limits

- This is a scripted six-host demonstration, not real network monitoring or protection.
- Active state remains process memory. The hosted deployment must continue to use one worker; finished run history and user scenarios may disappear if hosted disk is ephemeral.
- The current mobile layout supports the library and run views. Dense timeline editing and comparison tables use horizontally scrollable regions on narrow screens.
- The 3D twin and forecast explanation lab are later Phase C items. Replay Studio offers run snapshots and state summaries, but does not replace those planned workflows.
