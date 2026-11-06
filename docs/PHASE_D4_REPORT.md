# Phase D4 report — bounded recorded-event streaming pipeline

Date: 2026-11-06
Branch: `phase-d4-streaming-pipeline`
Environment: Windows, Python 3.11, Node 24.22.0, npm 11.19.1.

## Delivered

- Added a bounded SQLite-backed streaming adapter for installed synthetic dataset packs. It reads source packs without modifying them, processes events in batches, and supports pause, resume, stop, event-time bounds, playback speed, and configurable decision points.
- Added the dataset pipeline status endpoint and included its version in the shared feed. Workspace changes stop an active stream; demo-6 continues to use the original replay path.
- Added label playback and a clearly qualified graph-novelty estimate for packs that declare support. Unsupported model modes fail with an explicit explanation.
- Routed streamed detections, incidents, graph updates, forecasts, containment, and recorded-data what-if explanations through the existing simulation hooks. Containment remains propose-then-confirm and never edits the pack database.
- Bounded large-workspace time-travel snapshots and the retained contained-event sample. Added the `dataset_pipeline_status` contract and updated feed, event, and graph contracts with samples and checker coverage.
- Added nine pipeline integration tests, including roles/CSRF, immutable source data, deterministic playback, simulated containment, and a 100,000-event scale check.

## Verification

| Check | Command | Result |
| --- | --- | --- |
| Full Python suite | `.venv\\Scripts\\python.exe -m pytest -q --tb=short` | **531 passed, 1 skipped**; all passed after fixing two test/context issues. The skip requires `PRECOG_REPO_DIR`. |
| Offline detector suite | `detect\\offline_model\\.venv\\Scripts\\python.exe -m pytest -o addopts= detect/offline_model/tests -q -rA --tb=short` | **50 passed, 1 skipped**; skip needs downloaded real data and `RUN_REAL_DATA=1`. |
| Web tests | `npm.cmd test` in `web/` | **151 passed** plus the path-with-spaces runner check. |
| Contract checker | `.venv\\Scripts\\python.exe contracts\\check_contracts.py` | **71 contracts OK**. |
| Dataset validation | `tools/datasets/validate_pack.py` on `demo-6` and four synthetic packs | **5/5 packs valid**. |
| Golden Path | `.venv\\Scripts\\python.exe lead-core\\integration\\golden_path.py --runs 1 --speed 1` | **1/1 PASS**; replay, forecast, confirmation, containment, blocked-hit resolution, and re-evaluation passed. |
| Evaluation parity | `pytest lead-core/precog/tests -k seed_zero_demo_evaluation` | **Passed**; shipped seed-zero evaluation remains reproducible. |
| 100k-event scale check | `pytest lead-core/integration/tests/test_dataset_pipeline.py::test_100k_event_pack_stays_batched_under_memory_and_payload_budgets -q -s` | **Passed**; 100,000 records, batch 1,000, 7.969 s, 3,696,374-byte Python traced peak, 27,358-byte state payload in this local run. |
| Whitespace and protected NIDS | `git diff --check`; `git diff --name-only -- lead-core/backend/nids` | No whitespace errors; no NIDS files changed. |

## Limits and not verified

- All streamed records and resulting detections describe scripted or generated simulation data. Graph novelty is a first-seen-pair heuristic, not a trained detector or real-world protection claim.
- The scale timing and memory figure are from this local Windows environment and are not a hardware-independent performance guarantee.
- D4 adds backend streaming behavior only, so no UI screenshots or browser interaction audit were produced for this phase. Render hosting and physical-phone behavior were not retested.
