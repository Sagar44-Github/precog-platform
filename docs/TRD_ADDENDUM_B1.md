# TRD Addendum — Phase B1

**Date:** 2026-11-04
**Branch:** `codex/phase-b1-app-shell`

## Frontend structure

- `web/src/App.jsx` owns the authenticated route shell and wraps the current console route with `AppShell`.
- `web/src/shared/AppShell.jsx` provides workspace navigation, breadcrumb, operator sign-out, command trigger, command palette, and the under-1024 px handoff.
- `web/src/shared/icons.jsx` is the local 1.5 px stroke SVG icon set. It adds no runtime dependency.
- `web/src/shared/theme-context.jsx` owns the `ThemeProvider`, `useTheme`, and shared theme toggle. The preference key is `precog-color-theme`; values are `dark` or `light`.
- `web/src/shared/theme.css` owns semantic color tokens and the light theme. Screens continue to read semantic variables rather than declaring color literals.
- `web/src/areas/console/Scene3D.jsx` recreates the six-host scene when the theme changes. Both Chart.js components recreate their chart when the theme changes.

## Route and event behavior

| Route | B1 behavior |
|---|---|
| `/app/login` | Existing login with a theme toggle and permanent simulation notice. |
| `/app/console` | Existing 3D console inside the desktop workspace at viewport widths of 1024 px or more. |
| `/app/console` below 1024 px | A static handoff page links to `/app/mobile`; the heavy console scene is not mounted. |
| `/app/mobile/*` | Existing PWA routes remain unchanged and include the theme toggle. |

The command palette sends a local `precog:console-command` browser event for existing console actions (`view` and `start-demo`). This event is not a backend API and does not bypass replay controls or containment confirmation.

## API and contract table

| Surface | Change |
|---|---|
| `/api/x/*` endpoints | None |
| JSON schemas / contracts | None |
| Authentication / containment rules | Unchanged; sign-out still uses the existing authenticated logout route; containment remains propose then confirm. |

## Verification additions

- `web/src/shared/app-shell.test.jsx` checks shell navigation, simulation labeling, command inventory, and narrow handoff.
- `web/scripts/browser-audit.mjs` now writes to `AUDIT_OUTPUT_DIR` when provided, checks desktop shell/handoff behavior, tests Ctrl+K and theme persistence, and reserves the canvas pixel check for desktop-width console captures.
- B1 evidence is stored in `docs/phase-b1/browser-audit-results.json` and `docs/phase-b1/screenshots/`.
