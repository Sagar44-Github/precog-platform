# contracts/

The agreed shape of every piece of data that passes between roles.
Each role builds and tests against these files, so nobody waits for anybody.

- `schemas/NAME.schema.json` — the rules (JSON Schema)
- `samples/NAME.sample.json` — a valid example that follows the rules

## Rules

1. **Only LEAD-CORE changes this folder.** Need a change? Tell LEAD-CORE what and why.
2. A sample must always follow its schema. Run `pytest` to check (the tests do it for you).
3. No unknown fields: a contract lists every field allowed.
4. Times are ISO 8601 UTC text like `2026-10-03T10:00:03Z`. NIDS's own packet times are plain `YYYY-MM-DD HH:MM:SS` and also mean UTC.
5. Severity words are NIDS's: `HIGH`, `MEDIUM`, `LOW`, `NORMAL`. Risk score is 0 to 100.
6. Threat-actor, ASN and location values from NIDS are **simulated**. Never show them as real intelligence.

## The shared host list

`data/hosts.json` is the one list of demo hosts (id, name, zone, network address). Every role reads it. Only LEAD-CORE changes it.

## The twelve contracts

| Contract | What it describes | Who produces it | Who reads it |
|---|---|---|---|
| `packet_record` | A packet row in NIDS's own shape | NIDS, GRAPH's replay writer | DETECT |
| `security_event` | A detection explained in plain English | DETECT | everyone |
| `graph_snapshot` | The live attack graph | GRAPH | web apps, Precog |
| `forecast` | Precog's Top-3 next targets | LEAD-CORE (Precog) | web apps |
| `containment_action` | A proposed or executed containment | VIZ | web apps |
| `reeval_result` | What happened after containing | VIZ | web apps |
| `audit_entry` | One audit-log line | DETECT, VIZ, LEAD-CORE | log file |
| `replay_status` | Where the replay is | GRAPH | web apps |
| `session_metrics` | Live accuracy numbers | LEAD-CORE | web apps, charts |
| `session_record` | One whole session | LEAD-CORE | history screen |
| `detection_report` | Offline CICIDS2017 results | DETECT | web apps |
| `world_state` | What a polling client receives | LEAD-CORE | web apps |

## Hook rules (how a role plugs its module into the backend)

Each role's Python package has a `register(ctx)` function. Inside it you hand over your finished object:

| Hook | Role | Object must offer |
|---|---|---|
| `replay` | GRAPH | `list_scenarios()`, `status()`, `start(scenario_id, speed)`, `pause()`, `resume()`, `restart()` |
| `events` | DETECT | `process_packets(rows)`, `process_technique(host, technique_id, note, compromise, severity, risk_score)`, `audit_record(entry_type, ref_id, summary)`, `reset()` |
| `graph` | GRAPH | `snapshot()`, `reset()`, `add_connection(src, dst)`, `mark_compromised(host)`, `set_host_state(host, state)`, `host_state(host)`, `attempt(from_host, to_host)`, `feasible_targets(host)`, `topology` |
| `precog` | LEAD-CORE | `reset()`, `on_compromise(host)`, `on_attempt(from_host, to_host, blocked)` |
| `containment` | VIZ | `propose(world, target_host, forecast_id, requested_by)`, `confirm(world, action_id)`, `cancel(world, action_id)` |
| `push` | VIZ | `register(token)` |

`ctx` gives you `ctx.world` (the shared state), `ctx.hooks`, `ctx.config`, `ctx.contracts` and `ctx.nids`.
Raise `addons.errors.HookError(code, message, status)` to send a clean error to the web app.
Full details: `lead-core/backend/addons/hooks.py`.
