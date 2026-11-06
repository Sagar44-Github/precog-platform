# Dataset uploads

Dataset upload is an administrator-only, local simulation feature at `/app/datasets/upload`.
It accepts a validated workspace ZIP or UTF-8 CSV, TSV, and JSON event rows. Raw files are
staged under the ignored backend data directory and removed when the job ends. Converted
packs are stored under `lead-core/backend/data/user_packs`; they are excluded from Git and
are not durable on Render's ephemeral filesystem.

Uploads require the same-origin `X-Precog-Request: 1` header and a multipart form request.
Local uploads default to 1 GiB; Render is capped at 50 MiB. Set `UPLOAD_MAX_BYTES` to a
smaller limit when needed. ZIP expansion and each generated pack are capped at 25 MiB;
conversion scans at most 2 million rows, retains at most 100,000 events and 500 hosts,
and the local pack quota is 20 packs / 200 MiB. User rows are never executed. Endpoint
names are pseudonymized by default, uploaded labels remain user-provided labels, and
derived topology and estimates are explicitly marked as such.

The API is `POST /api/x/workspaces/upload/preview`, followed by
`POST /api/x/workspaces/upload/jobs/{job_id}/build` and status polling at
`GET /api/x/workspaces/upload/jobs/{job_id}`. Cancellation uses
`POST /api/x/workspaces/upload/jobs/{job_id}/cancel`. Existing workspace deletion removes
an inactive uploaded pack after an administrator confirms the request.
