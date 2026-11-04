# PRD Addendum — Phase B1

**Date:** 2026-11-04
**Applies to:** desktop shell, current console, login, and mobile SOC entry points.

This addendum extends the original PRD without changing its replay-only safety boundary, API requirements, or data contracts.

## New product requirements

| ID | Requirement | Priority | Acceptance |
|---|---|---:|---|
| FR-UI-1 | The authenticated desktop console shall use a persistent workspace navigation rail and a shared top bar with the current location, operator actions, and a visible SIMULATION label. | M | The rail, route context, sign-out action, and simulation label are present on the console at 1024 px and wider. |
| FR-UI-2 | The desktop shell shall provide a searchable command palette opened by Ctrl+K or Cmd+K. | M | Keyboard search and Enter navigate to the mobile SOC; commands also expose the current alert/report views, deterministic Golden Path start, and theme switch. |
| FR-UI-3 | The product shall offer dark and light themes using the shared semantic design tokens. | M | Theme choice applies to the shell, console, mobile screens, 3D scene, and charts; preference persists across reload. |
| FR-UI-4 | The desktop 3D console shall require a viewport at least 1024 px wide. Narrower viewports shall provide a clear route to the phone SOC. | M | At 390 px and 820 px, the handoff has no horizontal overflow and retains the SIMULATION label. |
| FR-UI-5 | Shared controls shall use a consistent icon set, visible keyboard focus, reduced-motion behavior, and concise operator-facing copy. | S | Keyboard and browser checks cover the shell controls; the existing reduced-motion and simulation behaviors remain active. |

## User flow update

An authenticated operator can move between the desktop console and phone SOC from the shared shell, use the command palette to reach existing console views, and choose a theme without losing the active replay or changing its state.

## Non-goals in B1

Incident, asset, forecast-ledger, playbook, analytics, and scenario-builder pages are scheduled for later B phases. B1 adds no server-side role model and no new backend API.
