# Precog Decision and What-if Lab

Precog forecasts are model-based estimates from a scripted attack-path generator and a six-host demo topology. They are not a guarantee of real-world protection. The shipped node model is a first-order Markov model over host transitions. For a feasible candidate `j` from source `i`:

`P(j | i) = (count(i → j) + α) / (sum of counts across feasible candidates + α × candidate count)`

The forecast detail view shows the candidate set, hosts excluded because they were already compromised or contained, transition counts, smoothing value, arithmetic, rule-based and uniform baselines, technique-table source, held-out calibration bin, outcome, and headline standard error. Live replay forecasts carry the candidate context captured when the forecast was created. A preloaded sample forecast has no such recording, so the page marks its candidate context as reconstructed and shows the recomputed model probability beside the sample's recorded confidence.

## Routes

- `GET /api/x/forecasts/{id}/explain` returns the model trace for a forecast in the current in-memory session.
- `POST /api/x/whatif` accepts `from_host`, a hypothetical `host_states` map, and `contain_hosts`. It returns ranked candidates before and after, removed probability mass, and the unchanged latest live forecast. The route is authenticated, read-only, CSRF protected, size limited, and rate limited. It does not change world state, graph state, pending forecasts, or metrics.
- `GET /api/x/analytics/model` returns the shipped held-out comparison, calibration, model card, current session metrics, and separate offline detector report.
- `POST /api/x/analytics/evaluate` accepts an optional seed, held-out fraction, and alpha grid. Analyst/admin only; seed range ±1,000,000, fraction 0.1–0.5, at most six unique alpha values from 0.001–2, and at most three requests per minute. It runs the existing evaluation function without replacing the shipped model or result file.
- `GET /api/x/analytics/experiments` lists recent runs.

Experiment results are cached by parameters and saved atomically under `lead-core/backend/data/analytics/experiments.json`, capped at 50 entries. That folder is local runtime data and may be empty after hosted restarts. The route's seed-zero, 20% split, default alpha grid reproduces the shipped evaluation. Precision@3 is explicitly called trivial because the scripted topology has at most three feasible candidates at each held-out step. CICIDS2017 detector metrics are shown as a separate offline lab report, not as live NIDS performance.
