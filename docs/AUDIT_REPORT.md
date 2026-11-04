# Precog SOC Phase A Audit Report

**Audit date:** 2026-11-04
**Branch:** `audit-fixes`
**Scope:** Phase A audit, defect fixes, local demo verification, and evidence capture. Phase B was not started.

## Executive summary

The merged project builds and runs locally in both sample and live replay modes. Python, offline-model, web, contract, hosted-style, browser, and golden-path checks completed successfully, with the count differences and unavailable external systems documented below. A Windows path-with-spaces bug, a line-ending-sensitive training hash, and a console timeline overflow were fixed with regression coverage. The bundled web app was rebuilt and refreshed.

No files under `lead-core/backend/nids/` were edited. A byte comparison against the requested upstream NIDS commit found 23 files and zero differences. Containment remains a simulation with propose-then-confirm behavior.

The Phase A result is **PASS with documented exceptions**: the exact optional forecasting-repository commit named by the prompt is unavailable, the DETECT aggregate metrics differ slightly from the prompt's stale expected figures, the installed Node version is newer than the requested Node 22, and npm reports eight unresolved advisories. Render, physical-phone installation, Firebase push, and hardware-GPU performance were not verified.

## Environment

| Component | Used |
|---|---|
| OS / shell | Windows desktop, PowerShell; Python reports `Windows-10-10.0.26300-SP0` |
| Python | 3.11.9, 64-bit |
| Node.js / npm | Node 24.22.0 / npm 11.19.1 (project guide requests Node 22; this run used Node 24) |
| Browser | Playwright 1.64.1 with Chromium 156.0.8078.4 |
| Rendering | Chromium software WebGL via SwiftShader; no physical GPU performance claim |
| Backend Python environment | Repository `.venv`; `attackgraph` and `google-auth` requirements installed |
| Offline model environment | `detect/offline_model/.venv` |

## Branch and baseline inventory

At audit start, local `main` and `origin/main` both pointed to `591413a` (`Merge pull request #5 from Sagar44-Github/lead-core`). The local `lead-core` branch tracked `origin/lead-core` at `9354ede` (`feat(deploy): add web bundle builder and Render blueprint`). Other remote role branches present were `detect`, `graph`, and `viz`, plus the historical `main-backup` and `Sagar44-Github-patch-1` refs. The audit work was kept on `audit-fixes`; no push was made.

`main` contains the merged backend/add-ons, role modules, Precog engine, integration checks, deployment builder and Render blueprint. The audit branch adds the retained demo/UI work, audit fixes, evidence, and refreshed bundle. The main branch remains unchanged.

### Canonical ZIP comparison

Each canonical ZIP member was compared with the same repository path after normalizing CRLF to LF only. There were no missing canonical files. Differences below are classified rather than blindly restored because the ZIPs are partial snapshots and later role merges and audit fixes intentionally changed the repository.

| Archive | Canonical files | Missing | Different contents | Assessment |
|---|---:|---:|---:|---|
| `precog-platform-part1.zip` | 95 | 0 | 44 | Later role integration, deployment/runtime configuration, tests, and shared web updates; retained. Specific Precog hash regression changes are separately listed below. |
| `detect-delivery.zip` | 29 | 0 | 1 | ATT&CK technique data updated from version 19.2 in the archive to version 20.0 in the repository; intentional data refresh. |
| `graph-delivery.zip` | 36 | 0 | 3 | Mobile UI/test changes; intentional demo and responsive-flow improvements. |
| `viz-delivery.zip` | 30 | 0 | 6 | 3D console and panel styling/behavior changes; intentional visual improvements and overflow fix. |
| `precog-platform-part2.zip` | 32 | 0 | 8 | Audit hash fix and regenerated metadata, additional deployment test, ignore rules, and deployment-file refinements; retained. |

The 44 Part 1 differences are:

- Root/config/docs: `.env.example`, `.github/CODEOWNERS`, `.gitignore`, `README.md`, `pytest.ini`.
- Role integration: `detect/detect_events/__init__.py`, `detect/offline_model/README.md`, `graph/graph_net/__init__.py`, `graph/graph_replay/__init__.py`, `graph/requirements.txt`, `viz/requirements.txt`, `viz/viz_containment/__init__.py`.
- Backend integration: `lead-core/backend/NIDS_VERSION.txt`, `lead-core/backend/requirements.txt`, `lead-core/backend/run_app.py`, `lead-core/backend/wsgi.py`, and all add-on modules under `lead-core/backend/addons/` (`__init__.py`, `auth.py`, `config.py`, `contracts.py`, `errors.py`, `hooks.py`, `loader.py`, `routes.py`, `sample_loader.py`, `webapp.py`, `world_state.py`).
- Integration tests: `lead-core/integration/tests/conftest.py`, `test_api.py`, `test_loader_and_webapp.py`.
- Shared web project: `web/index.html`, `web/package.json`, `web/package-lock.json`, `web/public/manifest.webmanifest`, `web/public/push/push-sw.js`, `web/scripts/run-tests.mjs`, `web/src/App.jsx`, area entry points for charts, console, mobile, and push, and shared `AuthContext.jsx`, `components.test.jsx`, and `theme.css`.

Part 2 differences were `.gitignore`, `deploy/build_web_bundle.py`, `render.yaml`, `lead-core/integration/tests/test_deploy_and_config.py`, `lead-core/precog/precog_engine/model.py`, `lead-core/precog/results/precog_evaluation.json`, `lead-core/precog/results/precog_experiments.csv`, and `lead-core/precog/tests/test_precog_register_and_tools.py`. The builder and blueprint changes improve clarity; the added test covers root redirect behavior; the model changes normalize training-file hashes and regenerate their recorded metadata. The metrics remain unchanged. Repo-only additions are subsequent role merges and audit artifacts; they are not missing canonical files.

## Verification results

| Area | Command / procedure | Prompt expectation | Observed result | Status |
|---|---|---|---|---|
| Python syntax | `python -m compileall -q contracts lead-core detect graph viz deploy docs/audit` | No compile errors | Completed with no errors | PASS |
| Contracts | `python contracts/check_contracts.py` | `12 contracts OK` | `12 contracts OK` | PASS |
| Full Python suite | `\.venv\Scripts\python.exe -m pytest -o addopts="" -p no:cacheprovider` | 370 passed, 1 skipped | **372 passed, 1 skipped**, 2 deprecation warnings | PASS; two extra regression tests are present relative to the prompt's count (the demo root-redirect test and line-ending hash regression). |
| Optional real-repo forecasting test | `test_the_export_tool_on_the_real_repository_when_it_is_available` with `PRECOG_REPO_DIR` | Pass at commit `e188cc6ec96d6f0a5ea62d7ccfb53be3c5a4df14` | That exact commit was not available from the remote. The advertised remote HEAD was `e188cc6ec96df0288470380dbafccda1591e2c95`; with that checkout, the targeted export test passed. The full suite retains the single expected skip when the variable is unset. | EXPLAINED; exact pinned revision remains unverified |
| Offline model suite | `detect/offline_model/.venv/Scripts/python.exe -m pytest -o testpaths=. -o addopts="" -p no:cacheprovider` | 50 passed, 1 skipped | **50 passed, 1 skipped** | PASS |
| Web tests | `npm.cmd test` in `web/` | 91 passed | **93 component/shared tests passed**, plus the path-with-spaces Node regression test passed (94 cases total) | PASS; extra coverage explains count difference |
| Web production build | `npm.cmd run build` in `web/` | Build succeeds | Build succeeded. Vite emitted its existing large-chunk warning (largest bundle about 1.43 MB). | PASS with performance warning |
| Web bundle copy | `python deploy/build_web_bundle.py` | Build and copy into backend bundle | Succeeded; **16 files** copied to `lead-core/backend/web_dist`. `web/dist` and backend bundle were byte-identical at verification. | PASS |
| Backend health and hosted-style readiness | `python docs/audit/run_hosted_check.py` | `/api/x/health` healthy; checker ends `READY for the demo` | Isolated live backend started with temporary SQLite; all hooks and modules registered; `/app/`, manifest, service worker, icon, unauthenticated 401, login, live state, and four scenarios verified; output ended `READY for the demo`. | PASS |
| Golden path | `python lead-core/integration/golden_path.py --runs 2 --speed 1 --log docs/audit/rehearsals.csv` | 2 consecutive PASS runs | **2 of 2 PASS**; all checks reported `ok`; decision reached in 4.61–4.98 seconds and completion followed in 2.27–2.30 seconds. | PASS |
| Browser routes and layout | `npm.cmd run audit:browser` in `web/` | Sample and live, seven routes, three viewports, screenshots, no errors/overflow; nonblank 3D canvas | **42 route/viewport checks, 0 failures, 0 browser errors**; SIMULATION label present and no horizontal overflow on every check. Six console canvases were nonblank under SwiftShader. Screenshots are in `docs/audit/screenshots/`. | PASS |
| Live containment | Browser audit flow | Propose then confirm; simulated state changes | Proposal and confirmation completed in live replay; host state changed to contained in simulation. | PASS |
| Precog evaluation | `\.venv\Scripts\python.exe lead-core/precog/tools/evaluate_precog.py` | 149 forecasts; 60 test / 240 train; alpha .01; P@1 .6510; rule .6376; uniform .5503; P@3 1.0; ECE .0572 | Exact expected values reproduced. | PASS |
| DETECT evaluation | Fresh pinned-dataset evaluation, artifacts in `docs/audit/detect-evaluation/` | Precision .9978, recall .9969, F1 .9973, FPR .0023; unseen types 0–7% | LCCDE: precision **.9978**, recall **.9971**, F1 **.9974**, FPR **.0023**. Held-out unseen detection spans **0–6.1%**. | EXPLAINED; current reproducible output differs slightly from stale expected recall/F1 |
| Pinned NIDS copy | Compare `lead-core/backend/nids/` to upstream commit `b30070f20de1d1e22d44d0ad86140892c86c43e6`; inspect Git diff | Byte-identical; no edits | **23 files, zero byte differences**; `git diff main...HEAD -- lead-core/backend/nids/` empty. | PASS |
| Static policy scans | Color-code tests; search `APT29`, `Lazarus`, `FIN7`, `TODO`, `FIXME`, `XXX`, secret paths, URL path handling | No hard-coded screen colors, actor data, TODO markers, committed secrets, or faulty URL pathname handling | Color tests passed; actor-name and TODO searches had no matches in target UI paths; tracked secret scan found only example templates; URL search found only React Router `location.pathname`. Local `.env` is ignored. | PASS |

The expected Precog evaluation values are preserved as honest limitations: precision@3 is trivial for a candidate set of at most three reachable hosts, and the Markov model narrowly exceeds the rule baseline. The DETECT model results are from the checked-in CICIDS2017 sample evaluation and do not establish live-traffic performance.

## Defects found and fixes

| ID | Symptom and root cause | Fix and regression evidence | Files / commit |
|---|---|---|---|
| A-01 | Web test runner derived a filesystem path from URL `.pathname`; spaces remained percent-encoded on Windows. | Added `fileURLToPath` path handling and a Node regression test that exercises a project path containing a space. | `web/scripts/run-tests.mjs`, `web/scripts/path-utils.mjs`, `web/scripts/run-tests-paths.test.mjs`, `web/package.json`; `7cb2bcd` |
| A-02 | Precog training hash used raw bytes, so Windows CRLF checkout produced a different hash from the shipped LF-trained model. | Normalize CRLF to LF before hashing; added regression coverage; added `.gitattributes` line-ending and binary rules; regenerated the model metadata and evaluation artifacts. Metrics did not change. | `lead-core/precog/precog_engine/model.py`, `lead-core/precog/precog_engine/data/node_model.json`, `lead-core/precog/results/precog_evaluation.json`, `lead-core/precog/results/precog_experiments.csv`, `lead-core/precog/tests/test_precog_register_and_tools.py`, `.gitattributes`; `8879465` |
| A-03 | Browser audit found a 5-pixel horizontal overflow: event/forecast timeline markers were positioned against the full strip instead of the inner track. | Positioned markers within `.c-timeline-track`; added a component assertion. Re-ran Chromium audit at all widths with no overflow. | `web/src/areas/console/panels.jsx`, `web/src/areas/console/panels.test.jsx`; `08135c8` |
| A-04 | Windows Git checkout line-ending conversion could make the protected NIDS working tree appear different from upstream. | Added a path-specific `.gitattributes` rule that preserves CRLF in the NIDS worktree on Windows. No NIDS file was edited; upstream byte comparison passed. | `.gitattributes`; `5e05feb` |
| A-05 | Backend environment lacked the declared `attackgraph` and `google-auth` packages; topology selected its networkx fallback and push sender construction fell back to `LogSender`, causing two tests to fail. | Installed project-declared backend requirements, including `graph/requirements.txt` and `viz/requirements.txt`. The topology engine and FCM sender tests then passed. No runtime fallback behavior or assertions were weakened. | Environment setup only; dependency declarations already existed. |
| A-06 | Backend-served static bundle could lag behind the current web build, so `/app/` might serve older UI assets. | Rebuilt and copied all 16 static files; verified the web and backend bundles match; local browser and hosted-style checks passed. | `lead-core/backend/web_dist/`; `51905d4` |

### Audit branch commits

Each audit fix was kept in its own commit. The history also retains `4d0022a` (`feat(demo): polish entry flow and SOC console`), which predates the specific audit fixes and contains the requested local demo/UI improvements.

- `8879465` — `fix(precog): normalize training hashes across line endings`
- `7cb2bcd` — `fix(web): test runner paths with spaces`
- `08135c8` — `fix(console): keep timeline markers within track`
- `5e05feb` — `fix(repo): preserve pinned NIDS checkout line endings`
- `4f0c385` — `test(audit): add browser and hosted verification evidence`
- `51905d4` — `fix(deploy): refresh bundled web assets`
- The report commit and `baseline-audited` tag follow this report.

## Dependency audit and remaining risks

After a safe `npm audit fix`, `npm audit` still reports **8 advisories: 5 high and 3 moderate** across Firebase/Firestore, `@grpc/grpc-js`, `esbuild`, React Router, and Vite. The suggested fixes require breaking major-version upgrades, which could disrupt the pinned React 18 / React Router 6 / Vite 5 stack. These upgrades were not forced during a stability audit. Review and schedule them as a dedicated dependency migration.

The production build reports a large chunk (about 1.43 MB). It builds and runs, but this remains a bundle-size/performance risk on lower-end phones.

## Not verified

- **Render deployment:** No cloud deployment was created or tested. The local hosted-style checker passed; deployment still requires the project owner's Render account and configured secrets.
- **Physical phone PWA:** Browser routes and manifest/service worker assets passed Chromium checks, but installation and operation on a physical Android/iOS device were not available to test.
- **Firebase push:** Requires the owner's Firebase project and credentials, which were not present. Sender selection tests passed after installing `google-auth`; actual delivery was not tested.
- **Hardware GPU performance:** 3D canvases rendered nonblank with software WebGL. No physical GPU, 60 FPS, thermal, or battery-performance result is claimed.
- **Node 22 compatibility:** This audit used Node 24.22.0 because that was installed in the environment; repeat the web suite/build on the requested Node 22 runtime before treating that version as verified.
- **Exact optional Precog repo revision:** The requested full commit hash was not available from the remote. The currently advertised remote HEAD passed the targeted exporter test, but that does not prove behavior at the unavailable hash.
- **Actual production secrets/configuration:** The local demo used an isolated temporary SQLite database. Production environment variables and account credentials remain owner-managed.

## Evidence files

- Browser results: `docs/audit/browser-audit-results.json`
- Browser screenshots: `docs/audit/screenshots/`
- Golden-path timings: `docs/audit/rehearsals.csv`
- Hosted-style checker launcher: `docs/audit/run_hosted_check.py`
- Fresh DETECT evaluation artifacts: `docs/audit/detect-evaluation/`

## Final result

Phase A is complete on `audit-fixes`. The test totals and evaluation values that differ from the prompt are explained above; no known failing test remains in the recorded environment. The repository is ready for a review of the audit report. The `baseline-audited` tag marks this verified Phase A state. Work stops here; Phase B requires the user's approval.
