# Project decisions

## Phase D0 dataset gate — 2026-11-06

- Keep `demo-6` as the default and only currently runnable dataset workspace until pack equivalence is proven in D1.
- Treat all real-data workspaces as proposals. Do not commit raw datasets or derived packs until source-file hashes, exact terms, label semantics, and selected-window checks are recorded.
- Leave source checksums empty in `datasets/registry.json` because no raw files were downloaded in D0. An explicit unverified status is preferable to fabricated hashes.
- Keep synthetic workspaces as separate proposed packs with generated labels explicitly marked as simulation. Preserve topology-only sources as topology-only; they do not create native traffic, compromise, or route truth.
- Record the browser audit failures as a D0 baseline. Fix them in the relevant later UI phase with regression coverage rather than changing the application during the baseline/gate phase.

## Phase D3 synthetic pack selection — 2026-11-06

- Ship four reproducible project-generated packs: `synth-enterprise-30`, `synth-enterprise-120`, `synth-datacenter-300`, and `synth-enterprise-300`. These satisfy the synthetic pack count without importing third-party topology records.
- Keep the Zoo-derived synthetic pack as a reserve, outside the runnable workspace registry, until individual topology files have verified redistribution terms and attribution. The [official dataset page](https://topology-zoo.org/dataset.html) requests citation; the [official source repository](https://github.com/sk2/topologyzoo) does not establish blanket terms for all contributed records. No Zoo topology is included in D3.
- Label every generated event, route, weakness and capability as simulation. Per-pack held-out scores evaluate only generator-produced route patterns and are not real-world security-performance claims.
- Preserve demo-6 evaluation output by keeping the extended metrics opt-in for generated packs; legacy `evaluate()` callers retain the prior schema and values.

## Phase D4 streaming adapter — 2026-11-06

- Use one bounded in-process worker for dataset-pack streaming. Keep demo-6 on the original NIDS replay path and reject `nids-live`/traffic `model` modes for synthetic packs until a separately evaluated detector exists.
- Expose two synthetic pack modes: trivial ground-truth label playback and a simple graph-novelty estimate with a 20% ordered warm-up window. Do not present either as real-world protection.
- Use one automatic analyst decision point by default so a large synthetic replay is demonstrable without stalling at every generated campaign. The request can set the limit from 0 to 50; the existing replay decision timeout still applies.
- Keep dataset SQLite files immutable. Count every record addressed to a contained destination as blocked and every record from a contained source as suppressed; retain only 20 recent blocked examples. Containment remains in-memory and two-step.
- Reduce only the large-workspace time-travel ring to 32 snapshots and keep the demo-6 ring unchanged. The full world-state field shape stays the same; static pack topology remains the source for complete feasible links.
- Generalize `graph_snapshot.zone` to bounded workspace-specific text because a 300-host pack has six named zones; the original demo values stay valid.
