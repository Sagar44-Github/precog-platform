# Phase D5 verification

Date: 2026-11-06
Branch: `phase-d5-real-data-builders`

## Delivered

- Added checksum-staged, bounded builders for LANL Cyber1, CSE-CIC-IDS2018, CIC-IDS2017, CTU-13 CSV exports, CIC-IoT-2023, ToN_IoT network CSV, UNSW-NB15, and CIDDS-001.
- Added a per-file GraphML license gate and synthetic replay builder for topology-only sources.
- Added fixture coverage for all parsers, deterministic output, pseudonymization, bounds, LANL endpoint priority, CIDDS `AttackType`, UNSW route limits, license gates, and verified staging.
- Updated dataset cards, registry statuses, builder instructions, source citations, pack specification, changelog, and phase map.
- No runtime endpoint, contract, UI, or NIDS file changed.

## Verification

| Check | Result |
| --- | --- |
| Focused D5 builders and existing synthetic pack tests | 24 passed |
| Root Python suite | 549 passed, 1 skipped; 2 existing Scapy/cryptography deprecation warnings |
| Web tests | 151 passed, 0 failed; includes the project-path-with-spaces check |
| Offline DETECT model suite | 50 passed, 1 skipped |
| Contract checker | 71 contracts OK |
| Golden Path | 1/1 PASS; blocked-hit forecast and two-step containment confirmed |
| Bundled pack validation | 5/5 valid (`demo-6` and four synthetic packs) |
| `git diff --check` | Passed |
| `lead-core/backend/nids/` diff | Empty; NIDS remains unchanged |
| Screenshot/browser audit | Not run: D5 changes only offline builders, tests, registry, and source documentation; no UI code changed |

Commands run:

```powershell
.venv\Scripts\python.exe -m pytest lead-core\integration\tests\test_real_dataset_builders.py lead-core\integration\tests\test_topology_zoo_builder.py lead-core\precog\tests\test_synthetic_packs.py -q
.venv\Scripts\python.exe -m pytest --tb=short
npm test                         # from web/
detect\offline_model\.venv\Scripts\python.exe -m pytest -q  # from detect/offline_model/
.venv\Scripts\python.exe contracts\check_contracts.py
.venv\Scripts\python.exe lead-core\integration\golden_path.py --runs 1 --speed 1
Get-ChildItem packs -Directory | ForEach-Object { .venv\Scripts\python.exe tools\datasets\validate_pack.py $_.FullName }
git diff --check
git diff --exit-code -- lead-core/backend/nids
```

## Limits

No raw public dataset was downloaded, so the eight real-source records remain uninstalled and no full-source pack or real-data evaluation is claimed. Several sources require manual access or written rights review. CTU-13 binary Argus files need an explicit CSV export. Topology Zoo remains uninstalled until an individual topology's source, citation, license, and redistribution terms are reviewed; its generated attacks and routes are simulation data. Dataset builders write local packs only and do not activate them.
