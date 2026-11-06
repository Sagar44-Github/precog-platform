# Phase D3 report — synthetic packs and per-pack evaluation

Date: 2026-11-06
Branch: `phase-d3-synthetic-packs`
Environment: Windows, Python 3.11.9, Node 24.22.0, npm 11.19.1.

## Delivered

- Built four reproducible synthetic packs: `synth-enterprise-30`, `synth-enterprise-120`, `synth-datacenter-300`, and `synth-enterprise-300`. They include enterprise/datacenter zones, 30–300 hosts, feasible links, service roles, marked decoys and simulated weaknesses, generated background traffic, labeled multi-stage campaign routes, replay scenarios and Precog models.
- Added `tools/datasets/evaluate_pack.py`. It performs a seeded route holdout, chooses alpha within training data, writes model and metrics atomically, and validates the generalized `evaluation_result` contract before publishing.
- Extended Precog evaluation with opt-in MRR and candidate-set distribution. Existing callers retain the original output shape.
- Added the `evaluation_result` schema/sample and pack validation for the nested evaluation record. Updated the workspace registry and four cards with actual counts, sizes, content hashes, seeds, source checksum, baseline results and limitations.
- Moved `synth-topology-zoo` out of runnable workspaces into the registry `reserves` list. No Zoo graph was copied into the project. A fourth project-owned synthetic enterprise pack takes its place; see the decision in `docs/DECISIONS.md` and card in `docs/datasets/synth-topology-zoo.md`.
- Added six D3 tests: four pack build/evaluation reproducibility cases, seed sensitivity and demo metric parity.

## Verification

| Check | Command | Result |
| --- | --- | --- |
| Full Python suite | `python -m pytest -o addopts= --tb=short -q` | **522 passed, 1 skipped**, 2 Scapy/cryptography deprecation warnings; 170.71 s. The skip requires `PRECOG_REPO_DIR`. |
| Offline detector suite | `.\detect\offline_model\.venv\Scripts\python.exe -m pytest -o addopts= detect/offline_model/tests -q -rA --tb=short` | **50 passed, 1 skipped**, 50.55 s. The skip requires the downloaded real sample and `RUN_REAL_DATA=1`. |
| Web tests | `npm test` in `web/` | **151 passed**; path-with-spaces runner check **1 passed**. |
| Contract checker | `python contracts/check_contracts.py` | **70 contracts OK**. |
| Golden Path | `python lead-core/integration/golden_path.py --runs 1 --speed 1` | **1/1 PASS**; replay, forecast, confirmed simulated containment, blocked-hit outcome and re-evaluation all passed. |
| Pack validation | `python tools/datasets/validate_pack.py packs/<id>` for `demo-6` and all four synthetic IDs | **5/5 packs valid**, with manifest counts and hashes matching files. |
| Evaluation CLI | `python tools/datasets/evaluate_pack.py synth-enterprise-30` | Exit 0; generated evaluation was reproducible and its content hash remained unchanged. |
| Demo metric parity | Covered by `test_seed_zero_demo_evaluation_keeps_the_shipped_numbers` | **Pass**: 149 forecasts, Markov precision@1 0.6510, rule-based 0.6376, uniform 0.5503, ECE 0.0572. |
| Python compilation | `python -m py_compile` on the new builder, evaluator, pack validator and CLI | **Pass**. |
| Git whitespace / protected NIDS paths | `git diff --check`; `git diff --name-only -- lead-core/backend/nids` | **Pass**; no NIDS files changed. Modified text files use LF endings. |

The four synthetic packs total **3,893,887 bytes**. Their individual content hashes, sizes, counts and held-out metric tables are recorded in `datasets/registry.json` and `docs/datasets/synth-*.md`.

## Limitations and not verified

- All generated routes, labels, decoys, weaknesses, events and evaluation results describe the project’s own deterministic simulation. They are not observed attacks or evidence of real-world performance. Precision@3 remains secondary and should be read with each candidate-set distribution.
- The Zoo-derived synthetic reserve is deferred pending a per-topology rights and attribution review. The [official Zoo page](https://topology-zoo.org/dataset.html) asks users to cite the collection; the [source repository](https://github.com/sk2/topologyzoo) does not establish blanket terms for all contributed topologies. No Zoo topology is included.
- No real datasets were downloaded or converted in D3. Their access, rights, schema and builder work remains a later phase.
- D3 does not implement the D4 streaming replay adapter or claim 100k-event runtime/memory performance. The web interface was not changed, so no Playwright screenshots or browser audit were produced for this phase. `npm test` passed; Render hosting and physical-phone behavior were not tested here.
- The Golden Path check was one run. It is not the final five-run D10 gate.
