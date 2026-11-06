# D3 synthetic workspaces

Phase D3 ships four seeded, project-generated dataset packs. Each is a **SIMULATION** built from a deterministic topology, scripted attack profiles, generated background records and marked decoy assets. None contains captured traffic, observed attackers or real vulnerabilities.

## Packs

| Workspace | Hosts | Zones | Edges | Events | Routes | Decoys | Seed | Payload SHA-256 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `synth-enterprise-30` | 30 | 4 | 180 | 711 | 180 | 1 | 3001 | `045c2a310578535a6e7a9783814105450c1187dffe67e6baa6522bdf508ce681` |
| `synth-enterprise-120` | 120 | 6 | 960 | 1355 | 240 | 7 | 12001 | `3decea5ef1373ce266241b9f7bc75b8024cb420dc909cecc7e2ce74efe44980a` |
| `synth-datacenter-300` | 300 | 6 | 2400 | 1998 | 360 | 17 | 30001 | `d2324cb07b8eea8c6bd68f636c2ca5b0d27b3e28f0b0740cea08fa255d448fc9` |
| `synth-enterprise-300` | 300 | 6 | 2400 | 1989 | 360 | 17 | 33001 | `13a401d46b08d0151aebe58793041b852e5718ab254496520cb170d77c4a42f1` |

Enterprise profiles separate user, engineering/operations, DMZ, application and data tiers as appropriate to scale. The datacenter profile models edge, web, application, data, storage and control tiers. Host roles include workstations, service endpoints, identity systems, storage, monitoring and network devices. Generated service weaknesses use `DEMO-SIM-*` identifiers and are explicitly simulated. Decoy assets are marked in topology metadata and SQLite host details.

## Build and validate

Run from the repository root:

```powershell
python tools/datasets/build_pack.py --source synth-enterprise-30 --force
python tools/datasets/build_pack.py --source synth-enterprise-120 --force
python tools/datasets/build_pack.py --source synth-datacenter-300 --force
python tools/datasets/build_pack.py --source synth-enterprise-300 --force
python tools/datasets/validate_pack.py packs/synth-enterprise-30
```

The builder records the generator version, seed, source-script checksum, counts, payload hash and a fixed reproducible timestamp. It creates a staging directory, validates the full pack, evaluates it, and atomically publishes it. `--seed` can be used for a separate deterministic variant; it must be a nonnegative 32-bit integer.

## Per-pack Precog evaluation

Evaluate a bundled pack again with:

```powershell
python tools/datasets/evaluate_pack.py synth-enterprise-30
python tools/datasets/evaluate_pack.py synth-enterprise-30 --seed 0 --test-fraction 0.2
```

The tool uses a seeded route-level holdout, selects smoothing alpha on a validation split drawn only from training routes, and writes a full-route model plus an `evaluation_result` record containing precision@1 and its standard error, precision@3, MRR, ECE, calibration bins, candidate-set sizes and rule-based/uniform baselines.

`precision@3` is a secondary measure. Check each pack’s recorded candidate-set distribution. The metrics describe route prediction inside this generator, not real-world attack detection, security or protection. A generated pack’s “native” capability means truth exists in the generator by construction; it does not make the records empirical.

The D3 acceptance suite rebuilds each pack twice, compares all files byte-for-byte, reevaluates a second copy and checks the generated evaluation output. Seed 0 also verifies parity with the shipped demo evaluation. The demo’s default evaluation output remains backward-compatible; extended metrics are opt-in.

## Deferred topology reserve

The proposed Zoo-derived synthetic pack is not bundled. The official [Topology Zoo dataset page](https://topology-zoo.org/dataset.html) requests citation, but source topologies are individual contributions and the [source repository](https://github.com/sk2/topologyzoo) does not provide a blanket license covering all of them. D3 keeps `synth-topology-zoo` in the registry’s `reserves` list until specific files are allowlisted and attributed. `synth-enterprise-300` provides the fourth project-owned synthetic pack instead.
