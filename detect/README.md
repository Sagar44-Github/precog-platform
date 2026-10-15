# detect/ — DETECT's folder

Only DETECT edits files in this folder.

- `detect_events/` — security event processing, ATT&CK correlation, audit logging (runs inside the backend)
- `offline_model/` — CICIDS2017 feature preparation, training and evaluation (own Python environment, never imported by the backend)

Build guide: `docs/` (DETECT build guide).
