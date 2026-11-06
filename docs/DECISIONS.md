# Project decisions

## Phase D0 dataset gate — 2026-11-06

- Keep `demo-6` as the default and only currently runnable dataset workspace until pack equivalence is proven in D1.
- Treat all real-data workspaces as proposals. Do not commit raw datasets or derived packs until source-file hashes, exact terms, label semantics, and selected-window checks are recorded.
- Leave source checksums empty in `datasets/registry.json` because no raw files were downloaded in D0. An explicit unverified status is preferable to fabricated hashes.
- Keep synthetic workspaces as separate proposed packs with generated labels explicitly marked as simulation. Preserve topology-only sources as topology-only; they do not create native traffic, compromise, or route truth.
- Record the browser audit failures as a D0 baseline. Fix them in the relevant later UI phase with regression coverage rather than changing the application during the baseline/gate phase.
