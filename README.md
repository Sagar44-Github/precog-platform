# Precog SOC Platform

AI cyber threat detection, attack-path reconstruction, **Precog** next-target forecasting, 3D and mobile visualization,
and simulated containment. 5th-semester PBL project, Department of Computer Science and Engineering.

Everything runs in **Replay Mode**: scripted and recorded events only. No live attack is ever run against any network.

## Who edits what

| Folder | Owner (alias) | Notes |
|---|---|---|
| `lead-core/` | LEAD-CORE | NIDS-based backend, Precog Engine, integration tests |
| `detect/` | DETECT | Security events, ATT&CK correlation, offline CICIDS2017 model |
| `graph/` | GRAPH | Replay controller and writer, attack graph |
| `viz/` | VIZ | Containment and re-evaluation |
| `web/src/areas/mobile/` | GRAPH | Phone app screens |
| `web/src/areas/console/`, `charts/`, `push/` | VIZ | 3D console, charts, push notifications |
| `web/` (everything else), `contracts/` | LEAD-CORE | Shared web setup and data contracts |
| `docs/` | LEAD-CORE | Project documents |

## Rules

1. Work only on **your own branch** (named after your alias, for example `detect`). Never work on `main`.
2. Edit only the folders listed for you above.
3. When a piece is finished and committed, **tell LEAD-CORE and ask for a merge**. Only LEAD-CORE merges.
4. Never commit `.env` or any password, key or token.
5. Data formats between roles live in `contracts/`. Changing one goes through LEAD-CORE.

## Run it (Windows PowerShell, from the repo root)

```powershell
python -m venv .venv                                  # one time
.\.venv\Scripts\Activate.ps1                          # every new terminal
pip install -r lead-core/backend/requirements.txt     # one time
copy .env.example .env                                # one time, then fill in .env
python lead-core/backend/run_app.py                   # starts the backend
```

Open http://127.0.0.1:5000/app/ (the web app must be built first: `cd web`, `npm install`, `npm run build`).

## Licences

`lead-core/backend/nids/` is an unchanged copy of [123dars/NIDS](https://github.com/123dars/NIDS), MIT licence
(see `lead-core/backend/nids/LICENSE`, copyright Darshan B.).
