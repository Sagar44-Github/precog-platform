# Phase D7 — dataset workspace interface

## Delivered

Added `/app/datasets`, `/app/datasets/:id`, and `/app/datasets/compare`; an analyst/admin workspace switcher for desktop and phone navigation; active data-scope context on authenticated pages; capability and redistribution disclosures; command-palette entries; and a dataset-selection step in the operator tour. Existing backend contracts and server-side activation checks are reused.

## Verification

- Web tests: 161 passed.
- Workspace API/role tests: 7 passed.
- Production Vite build: passed; Flask static bundle rebuilt with 53 files.
- Playwright dataset audit: switched the active workspace, opened list/detail/comparison, zero browser errors, no horizontal overflow at 390×844, 820×1180, or 1440×900.
- Screenshots: `docs/audit/screenshots/phase-d7/`.

The browser audit stubs workspace API responses to exercise the interface; authorization and activation behavior are covered by the existing Flask workspace tests. The production build reports the existing 818 KB lazy 3D chunk and unresolved `/app/fonts/` URLs; these are unrelated to D7's lazy-loaded dataset pages.
