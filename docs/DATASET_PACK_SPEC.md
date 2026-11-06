# Dataset Pack Specification (D1, extended in D3)

Status: version 1 implementation for the existing `demo-6` workspace. This format is an offline interchange and storage format; the application runtime still uses the existing demo files until D2 introduces `DatasetContext`. Raw real datasets are never included in a pack or loaded by the web application.

## Directory layout

```text
packs/<pack-id>/
  manifest.json        identity, source terms, checksums, counts, capabilities and content hash
  topology.json        hosts, feasible/observed edges, assets and display clusters
  pack.sqlite          indexed events, hosts, edges, routes, labels and windows
  routes.jsonl         one ordered route per line, for inspection/training
  model.json           node transition counts, smoothing alpha and metadata
  evaluation.json      held-out Precog results plus explicit limitations
  card.md              text-only dataset card
  scenarios/<id>.json  validated replay scripts included by this pack
```

Pack IDs are filesystem-safe identifiers matching `[a-z0-9][a-z0-9-]{0,62}[a-z0-9]` (a one-character ID is also accepted). A pack is a directory, never an archive or executable. The pack root is trusted configuration. Store APIs reject traversal and symlinked pack contents. D1 limits the complete pack to 25 MiB.

## Manifest

`contracts/schemas/pack_manifest.schema.json` defines the version 1 JSON contract. Required fields include:

- `id`, `name`, semantic `version`, `builder_version`, integer `seed`, and UTC `created_at`.
- `source`: stable source identifier/name, citation, licence, and terms summary; plus a `redistribution` disposition.
- `size_bytes`: sum of pack payload bytes excluding `manifest.json` (avoids recursive self-sizing); `counts`: hosts, edges, events, labelled events, routes, and time span in milliseconds.
- `capabilities`: one of `native`, `derived`, or `none` for detection labels, host compromise, lateral-movement routes, and topology.
- `attack_classes`: the mapping semantics are `access-attempt`, `impact-only`, `reconnaissance`, `command-and-control`, or `lateral-movement`.
- `technique_mapping`: dataset class to ATT&CK technique IDs plus a required free-text field describing this project's mapping assumption.
- `detector_options`, `default_decision_policy`, `display_hints`, and `source_file_checksums`.
- `content_hash`: SHA-256 over sorted relative names and SHA-256 file digests for every payload file except `manifest.json`. This is a stable content identity; timestamps and manifest fields do not affect it.

The manifest's `source_file_checksums` records actual input files used by the builder, not just output files. D0 registry records intentionally have no source hashes until files are obtained and verified.

## Topology and event database

`topology.json` stores the original host identifiers and display labels, zone/role/address fields, feasible edges, optional observed edges with counts and time bounds, asset/service/weakness details, and cluster summaries. Weaknesses in a simulated topology must be explicitly labeled as simulated. The validator checks host identity uniqueness, endpoint membership, and that topology/manifest/SQLite host inventories agree.

`pack.sqlite` uses SQLite and a documented, versioned layout. The validator checks schema columns, integrity, required indexes, and counts. Tables:

- `hosts(host_id, display_name, zone, role, criticality, details_json)`.
- `edges(src, dst, edge_kind, count, first_seen, last_seen, provenance)`.
- `events(event_id, t, src, dst, kind, severity, label, attack_class, protocol, port, bytes, extra_json)` with indexes on `t`, `src`, and `dst`.
- `routes(route_id, label, hops_json, provenance)` with ordered host IDs and position.
- `labels(label_id, event_id, label, provenance)`.
- `windows(window_id, title, start_t, end_t, scenario_file)`.

`routes.jsonl` mirrors routes for review: a JSON object per line with `route_id`, `profile`, `path`, and `provenance`. SQLite is read through `DatasetPack.iter_events(start_t, end_t, batch_size)`, which uses a time-ordered indexed query and bounded `fetchmany`; it never materializes the entire event table. Batch sizes above 10,000 are rejected.

## Model, evaluation, windows, card

`model.json` currently uses the shipped Precog node model shape (`alpha`, transition `counts`, and `meta`). The pack validator verifies numeric alpha and known-host, nonnegative integer transitions. `evaluation.json` preserves the legacy evaluation object and adds a required `limitations` list. D3 adds an `evaluation_result` object validated against `contracts/schemas/evaluation_result.schema.json`; it records route-level split sizes, forecast metrics and standard error, rule-based and uniform baselines, calibration bins, candidate-set distribution, profile metrics, selected alpha and simulation limitations. The old `evaluate()` result shape remains the default for demo-6, preserving its published numbers.

Scenarios are included as UTF-8 JSON and validated using the existing GRAPH scenario schema. All scenario host references must belong to the pack inventory. Windows point to those scenario identifiers. `card.md` is plain text/Markdown; render it as text, never trusted HTML.

## Validator and store guarantees

`addons.dataset_packs.validate_pack()` rejects missing files, invalid schemas, unsafe or mismatched IDs, symlinks, oversized packs, invalid references, unknown hosts, bad model counts, missing SQLite indexes, SQLite corruption, count mismatches, and content-hash mismatches. `PackStore` is read-only, resolves IDs beneath its configured root, validates on open/list, and only lists direct child pack directories. `build_demo6_pack()` creates a sibling staging directory, validates before publication, then swaps into place with a rollback backup on replacement failure.

The D1 demo builder accepts the shipped demo source. D5 adds offline, source-specific builders and a checksum staging helper; these never upload or activate source data. D1 itself adds no upload, activation, route, or web runtime behavior.

## Demo equivalence

`python tools/datasets/build_pack.py --source demo-6 --out packs/demo-6 --force` converts the existing six-host fixture, four scenarios, 300 training sequences, Precog model, and held-out evaluation. `validate_existing_demo_equivalence()` asserts the exact host inventory, feasible edges, route order, model, scenario JSON, projected event stream, and evaluation match. D2 now activates validated packs through `WorkspaceManager`, rebinds topology, hosts, scenarios and the Precog model, and keeps `demo-6` as the boot default. The existing Golden Path remains the regression for unchanged demo behavior. The pipeline adapter for large SQLite event streams remains a later D4 gate.

## D3 synthetic packs and evaluation

`addons.synthetic_packs` deterministically builds the four bundled project-generated workspaces: `synth-enterprise-30`, `synth-enterprise-120`, `synth-datacenter-300`, and `synth-enterprise-300`. Each pack records its seed, generator version, generated-source checksum, topology and event counts, Markov model, a held-out evaluation, and a campaign preview scenario. Rebuilding a pack stages a complete directory, validates it, then atomically publishes it. Evaluation uses a staged copy and similarly replaces the existing pack only after the contract and pack validator pass.

The metrics are estimates of held-out routes generated by this same scripted simulation. They are not evidence about real attackers or deployment protection. `precision@3` must be interpreted alongside its candidate-set distribution. The Topology Zoo-based synthetic pack remains deferred until individual source topology licenses and attribution are cleared; the enterprise-300 project-generated pack is the D3 fourth pack.

## D4 read-only event pipeline

Installed non-demo packs stream `events` from SQLite with an indexed `ORDER BY t, event_id` query and `fetchmany()` batches. The pipeline accepts batches of 1–10,000 events, replay speeds from 0.25x to 1000x, and optional inclusive `start_t`/`end_t` windows. A single in-process worker handles the stream; start, pause, resume, stop, and automatic decision waits apply back-pressure. The pipeline never inserts pack events into NIDS's retained packet table, never rewrites a pack, and does not load the full event table into memory. NIDS live detection and its original six-host Golden Path remain on their existing route.

Synthetic packs offer two declared modes. `labels` replays non-benign labelled records as detections; it is a trivial ground-truth replay, not prospective detection. `graph-novelty` uses the first 20% of the selected ordered window as a baseline and alerts on first-seen source/destination pairs afterward; this is a simple estimate, not a trained production detector. `model` is rejected until a pack contains a separately trained and held-out traffic detector. `nids-live` is rejected outside demo-6. Dataset events use workspace host display names, the pack's attack-class mapping, and a manifest technique mapping assumption where one exists; NIDS's invented actor, ASN and location fields are never used.

The manifest decision policy can pause before a recorded lateral-movement event. The default safety limit is one decision point per stream; callers can set a limit from zero to 50. The analyst can propose and confirm containment with the existing two-step route, or resume manually; the existing `REPLAY_DECISION_TIMEOUT` controls automatic continuation. A target-contained event increments a bounded counterfactual feed and appears in a short recent sample as blocked. An event from a contained source is suppressed and counted. Both are labelled **“Simulated what-if on recorded data”**. The source SQLite file remains read-only. Session-local event and forecast identifiers restart for deterministic comparisons.

The `/api/x/pipeline` status object is capped to counters, one pending decision point, and at most 20 recent counterfactual examples. `feed_versions.versions.pipeline` changes at batch boundaries. The large-workspace time-travel ring is reduced to 32 snapshots; the existing demo-6 ring remains unchanged. `/api/x/state` keeps its existing shape and contains only bounded alert/action collections plus the live attack-path graph, while full static topology remains available through the topology endpoint.

## D5 offline real-source builders

`tools/datasets/fetch.py` stages manually obtained files only after checking the operator-supplied SHA-256 values and writes `source_checksums.json` atomically. `tools/datasets/build_real_pack.py` rechecks those hashes, parses bounded CSV/CTU text or LANL gzip records, pseudonymizes endpoint IDs, emits a local-only validated pack, and never activates or publishes it. The parser caps source scanning at two million rows, events at 100,000, hosts at 500, and pack data at 25 MiB. LANL remains behind its access/release review; sources without confirmed derived-data redistribution rights are blocked from tracked `packs/` output.

These builders add no raw dataset or verified full-source result to the repository. Their fixture evaluation includes a deliberately tautological label-playback baseline; it is not detection performance. Precog metrics are not claimed until ordered routes have been reviewed and a separate held-out evaluation is run. `tools/datasets/build_topology_zoo.py` creates only a simulation over a selected GraphML topology after a per-file terms/citation/hash record is supplied; generated attacks and routes are not properties of the source topology. See `docs/DATASET_BUILDERS_D5.md` and the source cards under `docs/datasets/` for source-specific input requirements and status.

## D6 large-topology views

`GET /api/x/topology/summary?offset=0&limit=100&q=&zone=` provides an authenticated host page (maximum 200 rows), server-side text/zone filtering, counts by host state and zone, zone-to-zone feasible-edge bundles, and the current page's individual edges capped at 1,000. `GET /api/x/assets` reads the active workspace inventory. The 3D and Lite topology views collapse workspaces of 100 or more hosts into selectable zone clusters; host search expands the matching zone. The asset directory pages on the server and virtualizes its visible rows. Synthetic risk and edge likelihood remain labelled estimates.

```powershell
python tools/datasets/build_pack.py --source synth-enterprise-30 --force
python tools/datasets/build_pack.py --source synth-enterprise-120 --force
python tools/datasets/build_pack.py --source synth-datacenter-300 --force
python tools/datasets/build_pack.py --source synth-enterprise-300 --force
python tools/datasets/evaluate_pack.py synth-enterprise-30
```

## Commands

```powershell
python tools/datasets/build_pack.py --source demo-6 --out packs/demo-6 --force
python tools/datasets/validate_pack.py packs/demo-6
python tools/datasets/inspect_pack.py packs/demo-6
```
\n
