# Phase C Map and Verified Starting Baseline

**Started:** 2026-11-05

**Starting point:** `phase-b1.5-precog-landing` at `6d12a82`

**Work branch:** `phase-c1-incidents`

**Scope now:** establish the map and baseline, then implement C1 only. Later C items remain gated on review of the preceding item.

## Phase B inventory

The repository contains `docs/phase-b1/README.md`, `docs/DEMO_SCRIPT_V2.md`, Phase B1 addenda, and the Phase A audit. I found no Phase B3–B7 delivery reports in this checkout. The attached Phase C prompt describes basic B3–B7 features; the table below records what is actually present in the current code and docs so C can extend those pieces without assuming missing workflows were delivered.

| Phase C item | What the current Phase B code delivers | Missing from the full C specification | Likely files or folders to change |
|---|---|---|---|
| **C1 Incident investigation** | Distinct security alerts, ATT&CK technique labels, alert timeline, live graph, forecast summaries, audit log, and single-host simulated containment. Phase B1 adds the workspace shell and mobile SOC routes. | Incident correlation and lifecycle; typed incident timeline; notes and status controls; incident filters, detail, exports, notifications and deep links; incident contracts; analyst/viewer authorization. | `lead-core/backend/addons/` (incident service, routes, role checks and world-state integration), `contracts/schemas/`, `contracts/samples/`, `lead-core/integration/tests/`, `web/src/areas/incidents/`, `web/src/App.jsx`, `web/src/shared/`, `docs/INCIDENTS.md`, `docs/audit/screenshots/phase-c/`. |
| **C2 Replay studio and builder** | Four shipped deterministic replay scenarios and start/pause/resume/restart controls. | Visual scenario authoring, validation and dry run; user scenario library; stepping, breakpoints, seeking, snapshots, run history and comparison. | `graph/graph_replay/`, `lead-core/backend/addons/`, replay contracts and tests, `web/src/areas/replay/`, `web/src/App.jsx`, `docs/`. |
| **C3 Network digital twin** | A live 3D console graph and a separate interactive 3D landing scene, plus graph topology and a phone-friendly SOC view. | Asset/service/weakness inspection, path explanations and alternatives, risk/exposure overlays, camera presets, time travel, segmentation preview and equivalent accessible list. | `graph/graph_net/`, `lead-core/backend/addons/`, `web/src/areas/console/`, new `web/src/areas/twin/` and host views, topology contracts and tests. |
| **C4 Precog decision and what-if lab** | Markov top-three forecasts, baseline/session metrics, calibration chart and a reproducible offline evaluation command. | Per-forecast candidate exclusions and formula explanation; read-only what-if; server evaluation runs, cache and experiment log; model card and per-profile analysis. | `lead-core/precog/precog_engine/`, `lead-core/backend/addons/`, forecast/what-if/evaluation contracts and tests, new forecast/lab/analytics web areas. |
| **C5 Response governance** | Propose/confirm/cancel for a single-host simulated containment, expiry, and audit events. | Role and playbook policy; impact previews; zone/path/top-three actions; approval records; release proposal/confirmation; governance history and UI. | `viz/viz_containment/` or a new add-on module, `lead-core/backend/addons/`, containment/approval contracts and tests, `web/src/areas/containment/`, role-aware navigation. |
| **C6 Connected story and final verification** | Phase B1 command palette, workspace navigation, theme persistence, and a 4–6 minute Golden Path demo script. | Entity-wide links/search, case report exports, notification centre, onboarding/help updates, ten-minute script, full Phase C route audits and final report. | `web/src/shared/`, workflow areas delivered by C1–C5, `docs/DEMO_SCRIPT_V3.md`, `docs/PHASE_C_REPORT.md`, audit scripts and screenshots. |
| **C7 Optional maintenance** | Audit documents eight npm advisories and an unverified Node 22 runtime. | Separate, incremental dependency-family upgrades with full regression after each. | `web/package.json`, lockfile, CI/runtime docs; only after C1–C6 are green and approved. |

## Verified baseline

Environment: Windows 11 desktop, PowerShell, Python 3.11.9, repository `.venv`, offline-model `.venv`, Node/npm from the installed environment, Playwright Chromium with SwiftShader.

| Check | Command or procedure | Current result |
|---|---|---|
| Full Python suite | `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | **374 collected; 373 passed, 1 skipped**, 2 warnings, 37.88 s. The skip is the optional Precog repository test. |
| Offline detector suite | `detect/offline_model/.venv/Scripts/python.exe -m pytest -o testpaths=. -o "addopts=" -p no:cacheprovider --tb=short` | **51 collected; 50 passed, 1 skipped**, 27.50 s. |
| Web suite | `npm test` in `web/` | **106 passed, 0 failed, 0 skipped**. React server-renderer `useLayoutEffect` warnings are present. |
| Contracts | `.venv/Scripts/python.exe contracts/check_contracts.py` | **12 contracts OK**. |
| Browser audit | `npm run audit:browser` in `web/` | **42 checks** across sample/live and 390×844, 820×1180, 1440×900; **0 failures and 0 browser errors**. Confirmed containment flow passes. |
| Golden Path | `.venv/Scripts/python.exe lead-core/integration/golden_path.py --runs 2 --speed 1` | **2 of 2 PASS**. Decision reached in 4.56 s and 4.61 s; replay completed 2.30 s and 2.31 s after confirmation. |
| Hosted-style readiness | `.venv/Scripts/python.exe docs/audit/run_hosted_check.py` | All 13 application checks pass and print `READY for the demo`, but the wrapper exits 1 because Windows reports `PermissionError [WinError 32]` while deleting its redirected `backend.log`. The application readiness passes; wrapper cleanup is a known baseline defect to repair before claiming a clean hosted-check command. |
| Precog evaluation | `.venv/Scripts/python.exe lead-core/precog/tools/evaluate_precog.py` | **149 held-out forecasts**, 60 test / 240 train, α=.01; P@1 **0.6510**, rule baseline **0.6376**, uniform **0.5503**, P@3 **1.0000** (trivial for at most three candidates), ECE **0.0572**, P@1 standard error **0.0390**. Values reproduce the shipped evaluation. |
| Production web build | `npm run build` in `web/`; copied with `deploy/build_web_bundle.py::copy_dist` | Build succeeds; existing Vite large-chunk warning remains. The Flask-served bundle was refreshed to **20 files** on the starting branch. |

Browser audit artifacts were restored after measurement so baseline verification does not replace the checked-in Phase B evidence. The repository's pre-existing untracked landing audit screenshots were left untouched.

## C1 delivered

C1 extends the existing alerts, graph, forecasts, replay, containment, and Phase B1 shell with an incident workbench; it does not implement C2–C7. Incidents correlate scripted alerts deterministically with explainable grouping reasons, severity roll-up, typed timelines, status transitions, notes, JSON/Markdown export, and an atomic bounded audit ledger. Viewer, analyst, and admin permissions are checked on the server; the UI mirrors those permissions. The Golden Path decision is preserved: once its predicted move is blocked by the one confirmed containment, the incident is marked contained while still listing `host-a` as compromised and explaining that the movement was stopped rather than every affected asset being remediated.

New endpoints: `GET /api/x/feed`, `GET /api/x/role`, `GET /api/x/incidents` (filters and cursor paging), `GET /api/x/incidents/{id}`, `GET /api/x/incidents/{id}/timeline`, `GET /api/x/incidents/{id}/export?format=json|markdown`, `POST /api/x/incidents/{id}/notes`, and `POST /api/x/incidents/{id}/status`. C1 adds six schemas and samples: `incident`, `incident_note`, `timeline_event`, `feed_versions`, `role_info`, and `incident_audit_entry`.

The replay controller extension passes optional severity through only when a hook accepts it; shipped callers remain compatible. `quiet-scan` now marks its scripted alerts LOW so the acceptance scenario has the specified low-severity classification. No NIDS source files changed.

## C1 verification

Environment: Windows 11 desktop, PowerShell, Python 3.11.9, repository `.venv`, offline-model `.venv`, Node/npm, Playwright Chromium with SwiftShader.

| Check | Command or procedure | C1 result |
|---|---|---|
| Full Python suite | `.venv/Scripts/python.exe -m pytest -o "addopts=" -p no:cacheprovider --tb=short` | **390 collected; 389 passed, 1 skipped**, 2 existing Scapy deprecation warnings, 42.25 s. |
| Offline detector suite | `detect/offline_model/.venv/Scripts/python.exe -m pytest -o testpaths=. -o "addopts=" -p no:cacheprovider --tb=short` | **50 passed, 1 skipped**. |
| Web suite | `npm test` in `web/` | **113 passed, 0 failed, 0 skipped** across 22 files. |
| Contracts | `.venv/Scripts/python.exe contracts/check_contracts.py` | **18 contracts OK** (six added). |
| Browser audit | `npm run audit:browser` in `web/` | **54 checks**, sample/live at 390×844, 820×1180, 1440×900; **0 failures, 0 browser errors, 0 axe violations**. The incident note flow and live simulated containment pass. |
| Browser evidence | `docs/audit/phase-c/browser-audit-results.json` and `docs/audit/screenshots/phase-c/` | **54 screenshots** saved. |
| Golden Path | `.venv/Scripts/python.exe lead-core/integration/golden_path.py --runs 2 --speed 1` | **2 of 2 PASS**; both runs confirmed proposal-before-confirmation, one executed simulated containment, blocked-hit outcome, and replay completion. |
| Hosted-style readiness | Local server plus `lead-core/integration/check_hosted.py` | **12 checks OK; READY for the demo**. No public Render deployment or physical-phone installation was performed. |
| Web build and hosted bundle | `npm run build` in `web/`; copied `web/dist` to `lead-core/backend/web_dist` | Build succeeds; hosted bundle refreshed to **22 files**. Vite reports a large-chunk warning; main JS is 827.91 kB (240.10 kB gzip), below the 1.43 MB starting audit figure. |
| Scenario acceptance | `test_golden_path_lateral_spread_quiet_scan_and_repeat_determinism` | Golden Path: exactly one contained incident, one executed action, blocked-hit forecast, source compromise shown. Lateral spread: one growing incident. Quiet scan: one LOW, open incident. Repeated quiet scans normalize identically. |
| Diff hygiene | `git diff --check`; NIDS path check | No whitespace errors and no changes under `lead-core/backend/nids/`. |

C1 is complete on `phase-c1-incidents`. C2–C7 remain unstarted and gated on review/approval. The existing dependency advisories and Vite chunk warning remain; Render and physical-phone behavior are unverified.
