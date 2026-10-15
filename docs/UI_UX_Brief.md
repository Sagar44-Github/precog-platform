# UI/UX Brief

## Precog SOC: the 3D console and the mobile web app (PWA)

---

## 0. Document Control

| Field | Detail |
|---|---|
| **Document** | UI/UX Brief |
| **Version** | 1.0 |
| **Date** | 6 October 2026 |
| **Follows** | Master Project Document, PRD v1.2, TRD v1.2, LEAD-CORE Build Guide Part 1 |
| **Used by** | **GRAPH** (phone app screens) and **VIZ** (3D console, charts, push notifications). LEAD-CORE owns the shared colour file |
| **Decision taken** | The colour system proposed earlier ("red = what happened, violet = what Precog predicts, teal = what you did", dark background) is **kept**. Changing a colour later means editing **one file** (`web/src/shared/theme.css`), never a screen |

---

## Naming Convention (Read This First)

The master document uses real names. **Every other project document, including this brief, uses the role-based aliases below.**

| Alias | Real Name | USN | Role |
|---|---|---|---|
| **LEAD-CORE** | Sagar R | 1DT24CS232 | Team lead — backend add-ons, Precog Engine, integration; the only person who merges code |
| **DETECT** | Neha | 1DT24CS174 | Flow feature preparation, ML detection, security event processing, ATT&CK correlation |
| **GRAPH** | Pallavi Bammanni | 1DT24CS185 | Data ingestion, simulation, attack graph, mobile web app (PWA) |
| **VIZ** | Preethi S Pujari | 1DT24CS195 | 3D visualization, charts, push notifications, containment |

---

## 1. Purpose and How to Use This Brief

This brief says **how the product looks, feels and reads**, so that GRAPH's phone screens and VIZ's console look like one product built by one team, without the two of them having to ask each other.

| If you are | Read first | Then |
|---|---|---|
| **GRAPH** | Sections 2, 3, 4, 8, 10, 11, 12 | Section 6 (components) |
| **VIZ** | Sections 2, 3, 4, 9, 10, 11, 12 | Section 6 (components), Section 7 (charts) |
| **LEAD-CORE** | Sections 3, 14, 15 | |

**There are no images in this brief on purpose.** Every screen is described with a layout sketch in text, an exact list of what appears on it, and the data field each item comes from. Nothing is left to guess.

**One rule above all:** a screen never contains a colour code. Screens use the named variables from `theme.css` (for example `var(--forecast)`). This keeps the whole product consistent and makes any later colour change a one-file job.

---

## 2. Who Uses It and What They Need

| Person | Situation | What the screen must do for them |
|---|---|---|
| **Analyst at a desk** (3D console) | Watching a network on a big screen | Show the attack spreading, show where it is predicted to go next, make the response one clear action |
| **Analyst away from the desk** (phone) | Notification arrives; thumbs only | In five seconds: what is happening, how bad, what to do |
| **Evaluator or faculty** | A demo with limited time, maybe no security background | A "wow moment" that needs no explanation, honest numbers, a clear **SIMULATION** label |

### The three questions every screen answers

1. **What is happening?**
2. **How bad is it?**
3. **What can I do about it?**

If a screen does not help answer one of these, remove the element.

---

## 3. Design Principles

| # | Principle | In practice |
|---|---|---|
| **P1** | **Triage first** | The most urgent thing is at the top-left and the biggest. Details are one tap away, never in the way |
| **P2** | **Calm, dark, high contrast** | People stare at this for hours. Dark surfaces, restrained colour, no decoration |
| **P3** | **Colour means one thing everywhere** | Red = what happened. Violet = what Precog predicts. Teal = what you did. Never reused for anything else |
| **P4** | **Never colour alone** | Every colour is paired with an icon, shape or word (Section 4.5), so it works in grayscale and for colour-blind users |
| **P5** | **Honest about uncertainty** | A forecast always shows its confidence as a percentage and a bar, and says "predicted", never "will". Old data is always marked as stale |
| **P6** | **Friction on dangerous actions** | Contain takes two deliberate steps and states the consequence |
| **P7** | **Motion with a job** | Only three things animate: a newly compromised host, the forecast, and a containment. Nothing moves for decoration |
| **P8** | **Plain English** | A first-year student can read every alert. No jargon without a one-line explanation |
| **P9** | **Always say it is a simulation** | A permanent **SIMULATION** badge is visible on every screen (Section 11.3) |

---

## 4. The Colour System

All values already exist in `web/src/shared/theme.css` (written by LEAD-CORE in Part 1 of the lead's guide). This section adds the **meaning**, the **rules** and a few extra variables, which LEAD-CORE adds to the same file (Section 4.6).

### 4.1 Surfaces and text

| Variable | Value | Use |
|---|---|---|
| `--bg` | `#0b0f14` | Page background |
| `--surface` | `#121821` | Cards, panels, bars |
| `--surface-raised` | `#1a2230` | Inputs, hovered cards, bottom sheets |
| `--border` | `#263042` | Card edges, dividers (**decoration only**, see 4.4) |
| `--text` | `#e6edf3` | Main text |
| `--text-muted` | `#9aa7b8` | Secondary text, captions, labels |
| `--accent` | `#38bdf8` | Buttons, links, focus ring, selected tab |

### 4.2 The three meanings

| Meaning | Colour | Variable | Used for | Never used for |
|---|---|---|---|---|
| **What happened** | Red `#ef4444` | `--state-compromised`, `--severity-critical` | Compromised hosts, critical alerts | Errors in the app itself (those use the amber banner and text, Section 6.18) |
| **What Precog predicts** | Violet `#a855f7` | `--forecast` | Forecast cones, forecast bars, anything predicted | Anything that has already happened |
| **What you did** | Teal `#14b8a6` | `--state-contained` | Contained hosts, "contained" chips, the success of a containment | Healthy or normal hosts |

**Normal hosts** are slate `#64748b` (`--state-normal`): quiet, nothing to see. There is deliberately **no green** in this product, because green would suggest "safe" for a simulated environment that is never safe to claim.

### 4.3 Severity ramp (NIDS's own four words)

| NIDS severity | Variable | Value | Icon | Label shown |
|---|---|---|---|---|
| `HIGH` | `--severity-high` | `#f97316` | triangle with `!` | **High** |
| `MEDIUM` | `--severity-medium` | `#f59e0b` | diamond | **Medium** |
| `LOW` | `--severity-low` | `#64748b` | circle | **Low** |
| *(critical)* | `--severity-critical` | `#ef4444` | octagon with `!` | **Critical** (used only by the threat-level card, Section 8.2) |

NIDS produces HIGH, MEDIUM, LOW and NORMAL. NORMAL traffic is never an alert and never has a badge.

### 4.4 Contrast rules (these numbers were calculated, not guessed)

Accessibility standard used: WCAG 2.2 AA (text 4.5:1, large text and icons 3:1).

| Combination | Contrast | Rule |
|---|---|---|
| `--text` on `--bg` / `--surface` / `--surface-raised` | 16.3 / 15.1 / 13.5 | Always fine |
| `--text-muted` on `--bg` / `--surface` / `--surface-raised` | 7.9 / 7.3 / 6.5 | Always fine, use for captions and labels |
| `--accent` on `--surface` | 8.3 | Fine for links and focus rings |
| Button text `#04121c` on `--accent` | 8.8 | Fine |
| `--severity-high` on `--surface` | 6.4 | Fine for text |
| `--severity-medium` on `--surface` | 8.3 | Fine for text |
| `--state-contained` (teal) on `--surface` | 7.2 | Fine for text |
| `--state-compromised` (red) on `--surface` | 4.7 | Fine for text, but only just. Prefer `--text-red` for small text (4.6) |
| `--forecast` (violet) on `--surface` | 4.5 | **Borderline.** Use violet for shapes and large text. For small text use `--forecast-text` (6.7) |
| `--severity-low` / `--state-normal` (slate) on `--surface` | 3.7 | **Fails for small text.** Use slate only for icons, shapes and large text. Write the word in `--text-muted` |
| `--border` on `--bg` | 1.45 | Decoration only. **Never** the only thing that shows where a control is |
| White text on a violet fill | 4.0 | **Not allowed.** Use dark text `#0b0f14` on violet fills (4.9) |
| White text on a red fill | 3.8 | **Not allowed.** Use dark text `#0b0f14` on red fills (5.1) |

### 4.5 Never colour alone (every state has a shape and a word)

| State | Colour | Shape or icon (2D screens) | Word | In the 3D console |
|---|---|---|---|---|
| Normal | slate | hollow circle | Normal | small slate sphere |
| Compromised | red | filled octagon with `!` | Compromised | red **octahedron**, pulsing once when it appears |
| Contained | teal | shield with a check | Contained | teal **cube** with a thin ring |
| Predicted next target | violet | dashed ring | Predicted, with the percentage | dashed violet ring around the host plus the cone |

### 4.6 Extra variables LEAD-CORE adds to `theme.css`

Add these lines inside the existing `:root { ... }`. LEAD-CORE does this once, and tells GRAPH and VIZ.

```css
  --border-strong: #66758f;    /* control outlines: 4.1 on bg, 3.8 on surface, meets 3:1 */
  --forecast-text: #c084fc;    /* small violet text: 6.7 on surface */
  --text-red: #f87171;         /* small red text: 6.4 on surface */
  --text-slate: #94a3b8;       /* slate words: 6.9 on surface */
  --focus-ring: 2px solid var(--accent);
  --radius-s: 6px;
  --radius-m: 12px;
  --radius-l: 20px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
```

Rule: **inputs and buttons that are not filled use `--border-strong`**. `--border` is only for card edges.

---

## 5. Typography, Spacing and Shape

### 5.1 Fonts (both free)

| Use | Font | Fallback (already in `theme.css`) |
|---|---|---|
| Interface text | **Inter** | system fonts |
| Numbers, ids, times, addresses, log lines | **JetBrains Mono** | system monospace |

If the demo laptop has no internet, the fallbacks are used automatically and nothing breaks. Do not add other fonts.

### 5.2 Type scale

| Name | Size / line height | Weight | Use |
|---|---|---|---|
| Display | 32 / 38 | 700 | The threat-level word on the home card |
| Title | 22 / 28 | 600 | Screen titles |
| Heading | 18 / 24 | 600 | Card titles |
| Body | 16 / 24 | 400 | Normal text. **Never below 16 on the phone** |
| Caption | 14 / 20 | 400, `--text-muted` | Times, helper text |
| Mono | 14 / 20 | 500 | Host ids, event ids, percentages, times. Use tabular numbers so digits line up |

### 5.3 Shape and spacing

- Spacing steps are multiples of 4 px (`--space-*`).
- Cards: `--radius-m`, `--surface`, 1 px `--border`, padding `--space-4`.
- Bottom sheets: `--radius-l` on the top corners.
- Touch targets: at least **44 × 44 px**.
- Phone content never touches the screen edges: `--space-4` side padding, plus the safe-area padding already in `theme.css`.

---

## 6. Component Catalogue

Each component says what it shows, where the data comes from, and its states. **Owner** says who builds it. Where a component is used by both areas, the owner builds it **once** and the other imports it (see Section 15).

Data fields refer to the world state the web app receives from `/api/x/state` (the `world_state` contract).

### 6.1 SimulationBadge — Owner: LEAD-CORE (shared)

A small pill: `SIMULATION`, text `--text-muted`, 1 px `--border-strong`, mono 12 px. Fixed in the top bar of the console and the top of every phone screen. Never hidden. Details in Section 11.3.

### 6.2 ThreatLevelCard — Owner: GRAPH (phone home) and VIZ (console top bar uses the same word and colour)

The biggest thing on the home screen.

| Level | Rule (PROPOSED, see Section 16) | Colour | Icon | Word |
|---|---|---|---|---|
| **Calm** | No alerts yet | slate | hollow circle | Calm |
| **Watching** | There are alerts, but no host is compromised | `--severity-medium` | diamond | Watching |
| **Under attack** | At least one host is `compromised` | `--severity-critical` | octagon `!` | Under attack |
| **Contained** | Hosts were compromised, and **none** is still `compromised` (all contained) | `--state-contained` | shield check | Contained |

Data: `graph.hosts[].state`, `alerts`. Shows: the level word in Display size, one caption line ("2 hosts compromised, 1 forecast pending"), and the last update time in mono. **Stale:** the card keeps its last level, gets the stale banner (6.18) and the word's colour is dimmed to `--text-muted`.

### 6.3 SeverityBadge — Owner: GRAPH (exported for VIZ)

A pill with the icon and the word from Section 4.3, fill = the severity colour at 16 % opacity, text `--text`, icon the full colour.

### 6.4 StateChip — Owner: GRAPH (exported for VIZ)

A pill with the icon and word from Section 4.5 for `normal`, `compromised` and `contained`.

### 6.5 AlertCard — Owner: GRAPH

```text
┌───────────────────────────────────────┐
│ [▲ High]                  10:00:01    │   severity badge, time (mono, muted)
│ Workstation A sent a 2500-byte TCP    │   explanation, 2 lines then "..."
│ packet to port 22 (SSH, remote login) │
│ on Workstation B. NIDS rated it ...   │
│ [SSH · T1021.004]            host-a › │   technique chip (if any), host id (mono)
└───────────────────────────────────────┘
```

| Element | Source field |
|---|---|
| Severity badge | `alerts[].severity` |
| Time | `alerts[].ts` shown as local time `HH:MM:SS` |
| Explanation | `alerts[].explanation` |
| Technique chip | `alerts[].technique_name` and `technique_id` (hidden when null) |
| Host | `alerts[].host` |

A **scripted** alert (`source` = `scripted`) shows a small mono `scripted` tag, so nobody thinks it came from NIDS's detector. Tap opens the alert detail (8.4).

### 6.6 ForecastBars — Owner: GRAPH (phone) and VIZ (console panel reuses it)

The Top-3 list, the heart of the product.

```text
Precog predicts the next target        (violet icon: dashed ring)
┌───────────────────────────────────────┐
│ 1  Web Server B   ██████████████ 74 % │   violet bar, mono percentage
│ 2  Workstation B  ███            15 % │
│ 3  File Server    █               7 % │
│ Likely next technique: Remote Services│   only when technique_hint is not null
└───────────────────────────────────────┘
```

| Element | Source field |
|---|---|
| Rows | `forecast.targets[]` (rank, host_id mapped to a name, confidence × 100) |
| Heading | The word **predicts**, never "will" |
| Technique line | `forecast.technique_hint.technique_name` |
| Bar | Fills `--forecast`; width = confidence; the number is always printed |

Empty state (no pending forecast): "No forecast right now. Precog predicts the next target after a host is compromised." States: `pending` shows as above; once resolved the card shows the outcome (6.15).

### 6.7 ContainButton and ConfirmSheet — Owner: GRAPH (phone), VIZ (console version uses the same wording)

**Contain is a two-step action** that mirrors the backend's propose, then confirm.

| Step | What the person does | What the app does |
|---|---|---|
| 1 | Taps **Contain Web Server B** (teal outline button) | Calls `propose` (target = rank-1 host unless another row is chosen) |
| 2 | A bottom sheet opens (below). The person **slides to confirm** | Calls `confirm` |

```text
┌───────────────────────────────────────┐
│ Contain Web Server B?                 │   Heading
│ This marks the host as contained.     │
│ It is a SIMULATION: nothing on a real │   always this sentence
│ network changes.                      │
│                                       │
│ [  ›››  Slide to confirm  ]           │   teal slider, 44 px high
│ [ Cancel ]                            │   text button; calls cancel
└───────────────────────────────────────┘
```

Rules: the sheet expires after 60 seconds (the backend expires the action too) and shows "This request expired. Try again." The slider needs a **deliberate drag across 80 % of its width**; keyboard users get a "Confirm" button instead. Cancel is always reachable. While waiting for the answer the slider shows a small spinner and cannot be pressed twice.

After confirmation: the sheet closes and the host's chip turns teal "Contained"; a toast says "Web Server B contained (simulated)". If the backend answers an error, show its plain message in the sheet (Section 11).

### 6.8 StaleBanner — Owner: LEAD-CORE (already in `theme.css` as `.stale-banner`)

Amber strip at the very top: "Connection lost: showing old data". Appears when no reply has arrived for twice the polling interval. Never hides content. Disappears by itself after the next reply.

### 6.9 ReplayControls — Owner: VIZ (console only; the phone shows status text only)

A compact group in the console top bar: **Start**, **Pause**, **Resume**, **Restart**, a speed selector (1×, 2×, 4×), and a status word from `replay.state`: Idle, Running, Paused, **Waiting for your decision** (violet text, because it is waiting on the forecast), Finished. Buttons are disabled when they do nothing. The scenario name comes from `replay.scenario_id`.

### 6.10 AccuracyCounter — Owner: VIZ (console), GRAPH shows the same on the phone home screen

Text: "Precog accuracy this session", then `hits / forecasts_resolved` in mono, for example `1 / 1` and `100 %`. When nothing is resolved yet: "No forecasts resolved yet". Label underneath, always: "Session counter, not the model's overall accuracy." (This protects against overclaiming; see TRD Section 9.9.) Data: `metrics.hits`, `metrics.forecasts_resolved`, `metrics.hit_rate`.

### 6.11 AttackPath2D — Owner: GRAPH

A simple vertical or horizontal chain of host chips connected by arrows, in order of `graph.compromised_path`, ending in a dashed violet arrow to the rank-1 predicted host. Used on the alert detail and the forecast screens. No zooming, no dragging.

### 6.12 HostNode3D, EdgeLine3D, ForecastCone3D — Owner: VIZ

See Section 9.2.

### 6.13 NodeDetailPanel — Owner: VIZ

Right panel in the console: host name and id (mono), zone, StateChip, its recent alerts (AlertCards, compact), and if it is a predicted target, its ForecastBars row and a Contain button.

### 6.14 Toast — Owner: LEAD-CORE (shared)

Bottom of the screen on the phone, bottom-right on the console. Dark `--surface-raised`, 1 px `--border-strong`, auto-closes after 4 seconds, never covers the slide-to-confirm control. Used for: containment done, copied, login problems.

### 6.15 OutcomeCard — Owner: GRAPH (phone), VIZ (console)

Shown when a forecast is resolved:

| Forecast status | Wording | Colour |
|---|---|---|
| `hit` with `blocked: true` | "Precog was right. The move toward Web Server B was blocked." | teal (what you did) with a violet check |
| `hit` with `blocked: false` | "Precog was right. The attacker reached Web Server B." | red text (it happened) |
| `miss` | "Precog missed. The attacker went to Workstation B instead." | `--text-muted`, never celebrated |

Always honest: a miss is shown as plainly as a hit.

### 6.16 EmptyState, LoadingState — Owner: LEAD-CORE (shared)

| State | Look | Words |
|---|---|---|
| Loading | Three grey skeleton bars, no spinner longer than 1 second | (none) |
| Empty alerts | Hollow circle icon | "No alerts yet. Start the replay to see activity." |
| Empty history | Same | "No past sessions yet." |
| Empty forecast | Dashed ring icon | See 6.6 |

### 6.17 TabBar (phone) and LeftRail (console) — Owner: GRAPH and VIZ respectively

See Sections 8.1 and 9.1.

### 6.18 Errors

The product has two kinds of problem, and they look different.

| Kind | Example | Look |
|---|---|---|
| **Connection** | The backend cannot be reached | Amber StaleBanner (never red) |
| **Request** | The backend refused or failed | A short plain message in the place where the action was, text `--text-red`, with a "Try again" text button. Messages come from the backend's `error.message` |

Red is reserved for "what happened to the network", so app problems are **never** red fills.

---

## 7. Charts (VIZ)

Built with **Chart.js** (decided). The two components are `ForecastAccuracyChart` and `AlertVolumeChart`; their names and properties are fixed by the placeholders in `web/src/areas/charts/index.jsx` and must not change.

### 7.1 Rules for every chart

| Rule | Detail |
|---|---|
| Background | Transparent on a `.card` |
| Grid | `--border` lines, 1 px, only horizontal |
| Text | `--text-muted`, 12 px for ticks, `--text` for the title |
| Never colour alone | Different line styles or markers as well as colours |
| Phone | Fills the card width; height 180 px; at most 5 ticks per axis |
| Empty | Show the EmptyState, never an empty frame |
| Animation | Off when the person prefers reduced motion; otherwise one 300 ms draw-in on first display |
| Numbers | Tooltips use mono tabular numbers |

### 7.2 The two charts

| Chart | Type | Data (property) | Look |
|---|---|---|---|
| **ForecastAccuracyChart** | Line over resolved forecasts | `metrics.calibration_bins` for the calibration view, and the hit rate over time when the history view supplies it. Until a series exists, the chart shows the **calibration view**: stated confidence on one axis, observed hit rate on the other, with a straight dashed reference line from 0 to 100 % | Violet line with round markers; reference line `--text-muted` dashed |
| **AlertVolumeChart** | Stacked columns | `alerts` grouped by minute and by severity | HIGH orange, MEDIUM amber, LOW slate; each severity also gets a different fill pattern (solid, diagonal lines, dots) |

A caption under the calibration chart explains it in one sentence: "Closer to the dashed line means the stated confidence matches reality."

---

## 8. The Mobile App Screens (GRAPH)

The phone app is a **PWA** installed on the phone's home screen, portrait only. Width target 360 to 430 px.

### 8.1 Frame and navigation

```text
┌───────────────────────────────────────┐
│ ‹safe area›                           │
│ Precog SOC             [SIMULATION]   │   top bar: title, badge
│ ┌ stale banner (only when stale) ───┐ │
│                                       │
│            (screen content)           │
│                                       │
├───────────────────────────────────────┤
│  Home    Alerts   Forecast   History  │   bottom tab bar (4 tabs)
└───────────────────────────────────────┘
```

The tab bar has 4 tabs with an icon and a word each: **Home**, **Alerts** (with a count badge of HIGH alerts), **Forecast** (a violet dot when a forecast is pending), **History**. The selected tab uses `--accent` for the icon and word, plus a 2 px bar above it (so it is not colour alone). Routes live under `/app/mobile/`.

### 8.2 Home

```text
┌───────────────────────────────────────┐
│ ┌───────────────────────────────────┐ │
│ │  ▓ UNDER ATTACK                   │ │   ThreatLevelCard (Display size)
│ │  2 hosts compromised              │ │
│ │  1 forecast pending   10:00:03    │ │
│ └───────────────────────────────────┘ │
│ ┌───────────────────────────────────┐ │
│ │ Precog predicts the next target   │ │   ForecastBars (Top 3), with
│ │ 1 Web Server B ██████████ 74 %    │ │   Contain button when pending
│ │ [ Contain Web Server B ]          │ │
│ └───────────────────────────────────┘ │
│ ┌───────────────────────────────────┐ │
│ │ Latest alert                      │ │   one AlertCard
│ └───────────────────────────────────┘ │
│ ┌───────────────────────────────────┐ │
│ │ Precog accuracy this session 1/1  │ │   AccuracyCounter
│ └───────────────────────────────────┘ │
└───────────────────────────────────────┘
```

Order is fixed (triage first): threat level, forecast with its action, latest alert, accuracy. Pull-to-refresh is **not** needed because the screen updates itself.

### 8.3 Alerts

A list of AlertCards, newest first (`alerts`), with a filter row: **All / High / Medium / Low** (filter chips with the severity icon and word). Shows up to 50. Empty state from 6.16.

### 8.4 Alert detail (opens from an AlertCard)

```text
‹ Back                          [▲ High]
Workstation A › Workstation B            (hosts, mono ids underneath)
10:00:01
────────────────────────────────────────
What happened
Workstation A sent a 2500-byte TCP packet to
port 22 (SSH, remote login) ...          (full explanation)
────────────────────────────────────────
Attack technique                          (hidden when none)
SSH (T1021.004) · lateral movement
[ Open MITRE page ↗ ]                     (link is built from the technique id)
────────────────────────────────────────
Where it is in the attack                 AttackPath2D (6.11)
Risk score  49.9 / 100                    mono
Source      NIDS detector | scripted
```

### 8.5 Forecast tab

The full ForecastBars card, the Contain button (6.7), the AttackPath2D (6.11) and the OutcomeCard for the last resolved forecast. When nothing is pending: the empty state and the last outcome.

### 8.6 History tab

| Block | Content | Source |
|---|---|---|
| Accuracy | AccuracyCounter and `ForecastAccuracyChart` | `metrics` |
| Past sessions | A list: scenario name, time, hits over forecasts | `/api/x/sessions` |
| Detection quality | A card "Offline detection test": model, precision, recall, F1, false-positive rate and the **notes text**, including the honest line that unseen attacks are mostly missed | `/api/x/metrics/detection` (`detection_report`) |
| About this data | "All data in this app is simulated." | fixed text |

### 8.7 Login

Centered card (already built by LEAD-CORE): app name, "Demo account sign-in", username (pre-filled `admin`), password, sign-in button. Wrong password: "Wrong username or password." in `--text-red`. No "forgot password" and no sign-up (PRD non-goal).

### 8.8 Notification primer (VIZ builds the notification code, GRAPH places this screen)

Shown once after the first sign-in, before the browser's permission box: "Get an alert when something serious happens. We only send high-risk alerts." Buttons: **Turn on alerts** and **Not now**. "Not now" is remembered and never nagged. Notification text format is in Section 11.2.

### 8.9 Every screen has these states

| State | Behaviour |
|---|---|
| Loading | Skeleton bars (6.16) |
| Empty | The wording from 6.16 |
| Stale | StaleBanner; content stays |
| Logged out | The app sends the person to Login |
| Request error | Plain message in place (6.18) |

---

## 9. The 3D Console (VIZ)

Desktop browser, landscape, width 1280 px and up (it must still work at 1024). Route: `/app/console/`.

### 9.1 Layout

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Precog SOC  [SIMULATION]   Threat: UNDER ATTACK    ▶ ⏸ ↺  1×  Running │  top bar
├────┬──────────────────────────────────────────────────┬─────────────┤
│Rail│                                                  │ Right panel │
│ ◉  │            3D graph (fills the space)            │ Node detail │
│ ≡  │                                                  │ or Forecast │
│ ◔  │                                                  │ + Contain   │
│    │                                                  │             │
├────┴──────────────────────────────────────────────────┴─────────────┤
│ Timeline strip: alerts as marks along time, newest at the right       │
└─────────────────────────────────────────────────────────────────────┘
```

| Area | Content |
|---|---|
| Top bar | App name, SimulationBadge, threat level (same rule and colours as 6.2), ReplayControls (6.9), accuracy counter (6.10), connection indicator |
| Left rail (56 px) | Three icon buttons with tooltips: **Graph** (default), **Alerts** (list in the right panel), **Reports** (charts in the right panel) |
| Centre | The 3D graph |
| Right panel (360 px) | Default: ForecastBars + Contain. When a host is selected: NodeDetailPanel (6.13). When "Alerts" is chosen: AlertCards. When "Reports": the two charts |
| Timeline strip (72 px) | One mark per alert (shape and colour by severity), the replay position, and a violet marker where a forecast was made |

### 9.2 The 3D scene

Uses `3d-force-graph` (built on Three.js; VIZ confirms the exact API in its own guide). **With six hosts the scene must feel spacious, calm and readable, not busy.**

| Element | Spec |
|---|---|
| **Background** | `--bg` (transparent canvas over the page background) |
| **Normal host** | Small sphere, radius 4 units, slate, no glow |
| **Compromised host** | **Octahedron**, radius 6 units, red, a soft red glow. When a host becomes compromised it **pulses once** (scale 1 → 1.6 → 1, 600 ms) and a ring expands from it and fades (900 ms) |
| **Contained host** | **Cube**, 8 units, teal, a thin teal ring around it. On containment the cone pointing to it fades out in 400 ms |
| **Predicted target** | The host keeps its own shape, plus a **dashed violet ring** and the label "74 %" in mono above it |
| **Labels** | Host name in `--text` 12 px under each host, always visible (sprites facing the camera). Mono id appears on hover |
| **Edges (observed connections)** | Thin lines, `--text-muted` at 50 % opacity. The edge along the attack path is **red** and slightly thicker. A small particle travels along a new edge once when it appears (the propagation animation) |
| **Forecast cone** | A cone from the compromised host toward each of the Top-3 predicted hosts, `--forecast`. **Width and opacity grow with confidence** (confidence 0.74 → clearly strong; 0.07 → faint, barely visible). The cone "breathes" slowly (opacity ± 8 %, 2.4 s loop). Only the pending forecast is shown, and it disappears when resolved |
| **Zone hint** | The three zones (user, dmz, internal) are shown as faint, large, rounded translucent areas behind the hosts with a small zone word in `--text-muted`, so the picture reads as a network |
| **Camera** | Starts slightly above and in front, auto-rotating **very slowly** (one turn per 90 s) until the person touches it. Rotation stops while a forecast is pending, so the cone is stable to look at |
| **Interaction** | Hover highlights a host and its edges; click selects it (right panel shows NodeDetailPanel); drag rotates; scroll zooms; double-click resets the camera |
| **Performance** | Six hosts only. Target 60 frames per second on a modest laptop. No shadows, no post-processing, at most 20 particles at once |
| **Reduced motion** | If the person prefers reduced motion: no auto-rotation, no pulse (the octahedron simply appears), no breathing, no travelling particles |

### 9.3 Console states

| State | Behaviour |
|---|---|
| Idle (no replay) | The six hosts in slate; right panel says "Start the replay to see an attack." |
| Running | As above |
| Waiting for your decision | The ReplayControls word turns violet; the forecast and **Contain** are the focus; a subtle violet outline appears around the right panel |
| After containment | The cone fades, the host becomes teal, the attacker's blocked attempt shows as a short red dashed edge that stops before the host and fades; the OutcomeCard appears in the right panel |
| Stale | StaleBanner across the top; scene frozen but visible |
| Loading | Skeleton in the right panel; the scene shows the hosts from the first reply |

### 9.4 The demo moment (design the screen for this)

The golden path in the order the audience sees it: **(1)** a host turns red and pulses, **(2)** violet cones grow from it toward the likely targets and the right panel lists the Top-3, **(3)** the phone buzzes with the same forecast, **(4)** Contain is slid on the phone, **(5)** the cone toward the contained host fades and the cube turns teal, **(6)** the next attacker move is shown stopping short, **(7)** the accuracy counter ticks up. Every one of these must be visible without clicking anything on the console.

---

## 10. Motion

| Moment | Effect | Duration | Easing |
|---|---|---|---|
| Host becomes compromised (3D) | Single pulse and expanding ring | 600 ms and 900 ms | ease-out |
| Forecast appears | Cones grow from the compromised host to full length | 500 ms | ease-out |
| Forecast breathing | Opacity ± 8 % | 2400 ms loop | ease-in-out |
| Containment (3D) | Cone fade-out, host shape swaps to cube with a short scale pop | 400 ms | ease-in-out |
| Phone: sheet opens/closes | Slide up/down | 240 ms | ease-out |
| Phone: new alert in the list | Fade and slide in from the top by 8 px | 200 ms | ease-out |
| Charts | One draw-in | 300 ms | ease-out |
| Everything else | **No animation** | | |

All motion is switched off when the browser reports "reduce motion" (`prefers-reduced-motion`).

---

## 11. Words and Behaviour

### 11.1 Voice

Short, plain, calm, factual. Present tense for what is happening, "predicts" for the forecast, "simulated" for any action. No exclamation marks, no emoji, no scary language ("attack detected!!"). Numbers in mono.

### 11.2 The text library

| Where | Text |
|---|---|
| Threat levels | Calm / Watching / Under attack / Contained |
| Threat caption | "{n} hosts compromised, {m} forecast pending" (omit a part that is zero) |
| Forecast heading | "Precog predicts the next target" |
| Forecast confidence | "74 %" (always with the bar) |
| Contain button | "Contain {host name}" |
| Contain sheet | "Contain {host name}?" / "This marks the host as contained. It is a SIMULATION: nothing on a real network changes." / "Slide to confirm" / "Cancel" |
| Contain done (toast) | "{host name} contained (simulated)" |
| Expired | "This request expired. Try again." |
| Stale | "Connection lost: showing old data" |
| Outcome hit blocked | "Precog was right. The move toward {host} was blocked." |
| Outcome hit not blocked | "Precog was right. The attacker reached {host}." |
| Outcome miss | "Precog missed. The attacker went to {host} instead." |
| Waiting | "Waiting for your decision" |
| Accuracy | "Precog accuracy this session" / "Session counter, not the model's overall accuracy." |
| Empty alerts | "No alerts yet. Start the replay to see activity." |
| Login error | "Wrong username or password." |
| Notification title | "{Severity} alert: {host name}" (for example "High alert: Workstation A") |
| Notification body | The first sentence of the alert's explanation |
| Notification primer | "Get an alert when something serious happens. We only send high-risk alerts." |

Host names always come from the shared host list (`contracts/data/hosts.json`), shown as the name ("Web Server B"), with the id (`server-b`) only in mono secondary text.

### 11.3 Always say it is a simulation

| Rule | Detail |
|---|---|
| Badge | The SimulationBadge is on every phone screen and in the console top bar. It cannot be closed |
| Containment | The sentence in the sheet and the toast says "simulated" |
| Threat actors | NIDS invents "threat actor", ASN and location values. **They are never shown**, anywhere (they are simulated and could be mistaken for real intelligence) |
| Detection card | The notes text from the offline report is shown in full, including that unseen attacks are mostly missed |
| History | "All data in this app is simulated." |

---

## 12. Accessibility

| Topic | Rule |
|---|---|
| Contrast | Follow Section 4.4. Check any new colour pair against 4.5:1 for text and 3:1 for controls and icons before using it |
| Colour | Never the only signal (Section 4.5) |
| Touch | Targets 44 × 44 px minimum on the phone |
| Text size | Body 16 px or larger on the phone; the app must stay usable at 200 % text zoom |
| Focus | Every control shows `--focus-ring`; tab order follows reading order |
| Keyboard | Everything in the console works without a mouse except the 3D camera. The slide-to-confirm has a keyboard "Confirm" button |
| Screen readers | Icons have text labels (`aria-label`); the threat-level card is a live region that politely announces changes; alerts in the list are list items; the 3D canvas has a text summary beside it: "6 hosts. 1 compromised: Workstation A. 1 forecast: Web Server B 74 %." (this same summary is also a list for non-3D reading) |
| Motion | Respect reduced motion (Section 10) |
| Language | The page sets `lang="en"` |

---

## 13. PWA Details (GRAPH with LEAD-CORE)

| Item | Spec |
|---|---|
| Name | "Precog SOC" (short name "Precog") |
| Icon | The two icons LEAD-CORE already delivered (`web/public/icons`): dark square, violet ring, teal ring, red dot (this is the meaning of the three colours in one picture) |
| Colours | Background and theme colour `#0B0F14` (already in the manifest) |
| Display | Standalone (no browser bars), portrait |
| Install | The app shows **no custom install banner**. The browser's own install control is used. The History tab's "About" card says how to install ("Use your browser's Add to Home Screen") |
| Offline | The stale rule only; there is no offline mode beyond showing the last data |
| Updates | When a new version is available the next full load uses it; nothing to design |

---

## 14. Where Things Live and Who Owns Them

| File or folder | Owner | Note |
|---|---|---|
| `web/src/shared/theme.css` | LEAD-CORE | The only place colours live. LEAD-CORE adds the Section 4.6 lines |
| `web/src/shared/` (SimulationBadge, Toast, StaleBanner, Empty/Loading states) | LEAD-CORE | Shared components, placed here so neither GRAPH nor VIZ edits the other's folder |
| `web/src/areas/mobile/` | GRAPH | Phone screens, ThreatLevelCard, AlertCard, SeverityBadge, StateChip, ForecastBars, ContainButton/ConfirmSheet, AttackPath2D, OutcomeCard, tab bar |
| `web/src/areas/console/` | VIZ | 3D scene, top bar, rail, panels, ReplayControls, timeline strip |
| `web/src/areas/charts/` | VIZ | The two Chart.js components |
| `web/src/areas/push/` | VIZ | Notification code and the notification wording from 11.2 |

**Sharing rule:** if both areas need the same small component (for example SeverityBadge or ForecastBars), the **phone area exports it** and the console imports it through the area's entry file. VIZ never edits GRAPH's files: it uses what GRAPH exports. Until GRAPH merges a component, VIZ builds against the lead's placeholder with the same name (Section 6.4 of the TRD describes this arrangement).

---

## 15. Design Quality Checklist (Run Before Asking for a Merge)

| # | Check |
|---|---|
| 1 | No colour code (`#...`) and no `rgb(...)` appears in any screen file: search your folder for `#` colours |
| 2 | Every colour is paired with an icon, shape or word |
| 3 | Violet appears only for predictions; red only for what happened to the network; teal only for what was done |
| 4 | The SimulationBadge is visible; containment text says "simulated"; no threat-actor, ASN or location value appears |
| 5 | Every screen has Loading, Empty, Stale and Error states |
| 6 | The phone screens work at 360 px width and at 430 px width |
| 7 | Contain needs two steps and states the consequence |
| 8 | A miss is shown as plainly as a hit |
| 9 | Tab through the screen with the keyboard: focus is always visible |
| 10 | Turn on "reduce motion" in the operating system: nothing moves |
| 11 | Text meets the contrast rules in Section 4.4 |
| 12 | Screenshots of each screen are attached to the merge request message (phone and console) |

---

## 16. Items for Team Confirmation

Nothing below was decided silently. Each is a proposal in this brief that the team may change before building.

| # | Item | Proposed |
|---|---|---|
| 1 | The threat-level rule (Section 6.2): Calm, Watching, Under attack, Contained | As written. There is no threat-level field in the data, so the app works it out from `alerts` and `graph.hosts[].state` |
| 2 | Slide-to-confirm for Contain on the phone | As written (a drag across 80 %) |
| 3 | Contain target | The rank-1 predicted host by default, with the option to pick another of the Top-3 |
| 4 | Fonts Inter and JetBrains Mono (free) with system fallbacks | As written |
| 5 | The extra variables in Section 4.6 | LEAD-CORE adds them to `theme.css` |
| 6 | The host shapes in 3D (octahedron, cube, sphere) | As written |
| 7 | Slow auto-rotation of the 3D camera | As written, off while a forecast is pending |
| 8 | Charts: the calibration view as the first chart | As written |
| 9 | Notification wording | As written (Section 11.2) |
| 10 | No custom install banner | As written |

---

## 17. Inspiration (Look, Do Not Copy)

For the console: CrowdStrike Falcon, Microsoft Sentinel, Elastic Security and the Wazuh dashboard. For phone alert handling: PagerDuty and Opsgenie. On Dribbble or Behance search "SOC dashboard dark UI" and "incident response mobile app". Take **ideas of layout and hierarchy only**; do not copy any product's artwork, icons or text.
