# Precog prediction audit

## Findings before the fix

The active workspace path is not using the demo model by mistake. `WorkspaceManager._configure` loads `model.json` from the selected pack, replaces `engine.model`, calls `engine.reset()`, and rebuilds the workspace graph. This clears pending forecasts, explanation sidecars, replay state, and graph state on a switch.

The failure is primarily model fit and feature scope:

- The deployed predictor is a first-order Markov table keyed only by exact source and target host IDs. The runtime does not use event protocol, port, byte count, detector labels, attack technique, route stage, or host role/zone to rank targets.
- The synthetic packs have 30–300 hosts but only 180–360 labelled routes. Most source-host transition rows are sparse. The existing alpha grid stops at `1.0`; all four synthetic pack evaluations choose `1.0`, with validation negative log-likelihood still improving at that upper bound.
- The model therefore has little reusable evidence for a new source host or a route stage it has not observed. Its tie-break is host ID, which is deterministic but carries no predictive meaning. A forecast can be syntactically valid and still be close to chance.
- Pack events are used by the replay/detection pipeline, but the Precog model is trained from `routes.jsonl`; event labels are not currently model features. This is a deliberate host-transition forecasting design, but it means packet-volume changes alone cannot affect the forecast.

Workspace activation does not show evidence of cross-pack prediction leakage. It swaps the model and graph and resets Precog state. Regression coverage will be added to assert that the active model identity, prediction context, and forecasts change/reset correctly across repeated switches.

## Held-out results before the fix

The following pack-supplied evaluation files use held-out route sequences. They describe only each pack's simulated route generator, not real attacker behavior. `Precision@3` is not a Top-1 accuracy metric.

| Workspace | Held-out forecasts | Top-1 | Uniform Top-1 | Top-3 | Uniform Top-3 | ECE | Selected alpha |
|---|---:|---:|---:|---:|---:|---:|---:|
| demo-6 | 149 | 65.10% | 55.03% | 100.00% | 100.00% | 0.0572 | 0.01 |
| synth-enterprise-30 | 74 | 22.97% | 21.62% | 50.00% | 58.11% | 0.0638 | 1.0 |
| synth-enterprise-120 | 98 | 13.27% | 10.20% | 34.69% | 38.78% | 0.0664 | 1.0 |
| synth-enterprise-300 | 153 | 15.03% | 10.46% | 44.44% | 39.87% | 0.0352 | 1.0 |
| synth-datacenter-300 | 157 | 15.92% | 14.01% | 39.49% | 36.94% | 0.0439 | 1.0 |

For the synthetic packs, the small Top-1 differences from uniform are not strong evidence of useful predictive skill. The task has next-host route labels, not a separate held-out benign-vs-attack decision set for Precog. Classification metrics below therefore use one-vs-rest candidate decisions for the Top-1 recommendation, not event detection.

## Evaluation scope and limits

Synthetic route labels are generated ground truth and are valid only for evaluating recovery of the same documented generator. The route files do not carry capture timestamps, so a route-order split is not a defensible real-time test. The current reproducible split is route-held-out, not event-time-held-out. This audit will retain that limitation rather than claim temporal or real-network accuracy.

## Fix applied

The initial model was not accidentally loading the demo model after a workspace switch. It was receiving the active pack's route-trained model, but that model only counted exact `(source host, next host)` pairs. In the 30–300-host packs, each source had little training evidence and host IDs from a seeded generator have no meaning by themselves. The model also ignored route stage and reusable topology roles. Several synthetic routes begin in different zones and their target-zone patterns shift as the route advances; the model could not use either signal.

Precog now keeps its exact host-transition component and, for packs that provide complete zone metadata, adds a validation-selected context distribution over (1) route-stage target zones and (2) route-stage transitions conditioned on the source zone. These distributions are renormalized over the graph's feasible candidates and blended with exact-host evidence. The alpha grid now extends through 20; alpha and both context weights are selected on an inner split of the training routes by negative log-likelihood. The outer held-out routes are used only for the reported metrics. Legacy models without this capability continue to use their exact-host model; no pack name chooses a prediction or fallback.

At inference, the route stage comes from the active graph's compromised path. The live Precog engine, dry-run forecasts, explanation view, and what-if view now pass that stage into the same model. Workspace changes continue to load that workspace's `model.json`, reset the graph and Precog sidecars, and clear the active lab cache before loading that workspace's own saved experiments. A test cycles twice through all five installed workspaces, compares the loaded model to its active pack, checks that forecasts contain only feasible active hosts, verifies reset behavior, and compares repeat forecasts after normalizing timestamps.

The event stream remains outside this forecast model. Protocols, ports, byte counts and detector labels do not have route-aligned next-host labels for every pack; using them as if they did would mix unrelated records or leak scripted outcomes. Precog continues to forecast from the explicitly labeled route sequences and the active feasible topology. The models and outcomes are estimates over those supplied route sources.

## Held-out results after the fix

The four synthetic packs were rebuilt deterministically with the context-aware model and per-pack evaluator. `demo-6` remains byte-for-byte on its shipped model and evaluation baseline; its metrics below were freshly computed from its unchanged routes and topology. Splits are seeded 80/20 route-held-out; context and alpha selection use a further training-only validation split. `Top-3 hit` is the legacy `precision_at_3` field (whether the actual next host is among the first three), not classical precision at three.

| Workspace | Hosts | Held-out routes / forecasts | Top-1 (SE) | Uniform Top-1 | Rule Top-1 | Top-3 hit / uniform | MRR | Log loss / uniform | ECE | Selected alpha; exact/source-zone weights |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| demo-6 | 6 | 60 / 149 | 0.6510 (0.0390) | 0.5503 | 0.6376 | 1.0000 / 1.0000 | 0.8121 | 0.686470 / 0.730818 | 0.0572 | 0.01; exact-only legacy model |
| synth-enterprise-30 | 30 | 36 / 74 | 0.2703 (0.0516) | 0.2162 | 0.1892 | 0.6622 / 0.5811 | 0.5106 | 1.715770 / 1.774513 | 0.0340 | 20; 0.00 / 0.00 |
| synth-enterprise-120 | 120 | 48 / 98 | 0.1735 (0.0382) | 0.1020 | 0.0612 | 0.4898 / 0.3878 | 0.3943 | 1.992443 / 2.073991 | 0.0316 | 10; 0.00 / 0.00 |
| synth-enterprise-300 | 300 | 72 / 153 | 0.1569 (0.0294) | 0.1046 | 0.1503 | 0.4444 / 0.3987 | 0.3804 | 2.051357 / 2.075951 | 0.0467 | 2; 0.00 / 0.50 |
| synth-datacenter-300 | 300 | 72 / 157 | 0.1783 (0.0306) | 0.1401 | 0.1210 | 0.3758 / 0.3694 | 0.3694 | 2.083141 / 2.076039 | 0.0339 | 2; 0.50 / 1.00 |

Top-1 is above uniform on each synthetic held-out set, but the differences are modest relative to the reported standard errors. The 300-host datacenter model has slightly worse held-out log loss than uniform, despite a higher Top-1 rate; its probabilities are not consistently better under this proper scoring rule. This is an unresolved quality limitation, not a passing accuracy claim. The new contexts improve reuse across hosts and stages, but the available route sample is too small to support a claim that each synthetic workspace's next-host predictions are reliable.

## Candidate-level classification results

For each held-out forecast, rank 1 is the single positive prediction and the actual next host is the positive label. Matrices use `[[TN, FP], [FN, TP]]`. There is one positive host per forecast, while every other feasible candidate is negative. This makes plain candidate accuracy look high on large topologies; Top-1 forecast accuracy is the useful headline.

| Workspace | Candidate accuracy | Precision / recall / F1 | FPR / FNR | Confusion matrix |
|---|---:|---:|---:|---|
| demo-6 | 0.6858 | 0.6510 / 0.6510 / 0.6510 | 0.2857 / 0.3490 | `[[130,52],[52,97]]` |
| synth-enterprise-30 | 0.7529 | 0.2703 / 0.2703 / 0.2703 | 0.1488 / 0.7297 | `[[309,54],[54,20]]` |
| synth-enterprise-120 | 0.7923 | 0.1735 / 0.1735 / 0.1735 | 0.1188 / 0.8265 | `[[601,81],[81,17]]` |
| synth-enterprise-300 | 0.7885 | 0.1569 / 0.1569 / 0.1569 | 0.1209 / 0.8431 | `[[938,129],[129,24]]` |
| synth-datacenter-300 | 0.7939 | 0.1783 / 0.1783 / 0.1783 | 0.1178 / 0.8217 | `[[966,129],[129,28]]` |

The matching candidates in every matrix are held-out feasible route hops. There is no evidence here for event-level detection precision/recall, since that is a separate DETECT task and uses different labels.

## Workspace switching and regression evidence

- All five installed packs were activated in forward and reverse order. Each active Precog model matched that pack's serialized model, source and target IDs matched the active topology, and a new stage-0 forecast was generated from a newly compromised active host.
- Before every activation, the test seeded a memory-only cache marker in the previous workspace and verified it was absent after switching. The new workspace uses its own experiment directory; its own persisted experiment history can be reloaded by design.
- No route in the five packs has a hop absent from its feasible topology. The active graph, replay endpoints and host details are covered by existing per-pack integration tests.
- Validation was run on Windows with Python 3.11.9. The full Python run collected 581 tests and completed with 580 passed, 1 skipped, and no failures. `npm.cmd test` completed with 174 passed and no failures. `contracts/check_contracts.py` validated 71 contracts. `git diff --check` found no whitespace errors.
- The updated local Flask process is serving on `http://127.0.0.1:5000`; `/api/x/health` and `/app/` both returned HTTP 200 after restart.
- All changes remain on the current working branch. Nothing was merged or pushed to `main`.
