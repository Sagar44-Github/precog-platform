# Dataset Pack Specification (D1)

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

`model.json` currently uses the shipped Precog node model shape (`alpha`, transition `counts`, and `meta`). The pack validator verifies numeric alpha and known-host, nonnegative integer transitions. `evaluation.json` preserves the existing evaluation object and adds a required `limitations` list. D2/D3 will generalize evaluation schemas and reports; D1 does not retrain or alter the shipped model/results.

Scenarios are included as UTF-8 JSON and validated using the existing GRAPH scenario schema. All scenario host references must belong to the pack inventory. Windows point to those scenario identifiers. `card.md` is plain text/Markdown; render it as text, never trusted HTML.

## Validator and store guarantees

`addons.dataset_packs.validate_pack()` rejects missing files, invalid schemas, unsafe or mismatched IDs, symlinks, oversized packs, invalid references, unknown hosts, bad model counts, missing SQLite indexes, SQLite corruption, count mismatches, and content-hash mismatches. `PackStore` is read-only, resolves IDs beneath its configured root, validates on open/list, and only lists direct child pack directories. `build_demo6_pack()` creates a sibling staging directory, validates before publication, then swaps into place with a rollback backup on replacement failure.

The builder accepts the shipped demo source only in D1; it does not accept user raw files. Future real-data builders must separately document their exact input schema, time/window and sampling rules, label semantics, pseudonymization, legal gate, and checksums. D1 adds no upload, activation, route, or web runtime behavior.

## Demo equivalence

`python tools/datasets/build_pack.py --source demo-6 --out packs/demo-6 --force` converts the existing six-host fixture, four scenarios, 300 training sequences, Precog model, and held-out evaluation. `validate_existing_demo_equivalence()` asserts the exact host inventory, feasible edges, route order, model, scenario JSON, projected event stream, and evaluation match. The existing Golden Path is also run as a regression. D1 does not yet route the live replay controller through the pack; that runtime equivalence remains a D2 gate. Existing routes, NIDS files, and default sample/live behavior remain unchanged.

## Commands

```powershell
python tools/datasets/build_pack.py --source demo-6 --out packs/demo-6 --force
python tools/datasets/validate_pack.py packs/demo-6
python tools/datasets/inspect_pack.py packs/demo-6
```
\n