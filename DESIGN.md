---
version: alpha
name: BASE ANTIGRAVITY
description: >-
  Hub operacional B2B 4M&C — painel OMS/logística estilo BaseLinker funcional,
  leitura de feed ML + SQLite local. Densidade corporativa, azul sinal, sem
  estética de landing genérica.
colors:
  primary: "#0066FF"
  primary-hover: "#0052CC"
  on-primary: "#FFFFFF"
  background: "#F4F6F9"
  surface: "#FFFFFF"
  surface-muted: "#F8FAFC"
  sidebar: "#FAFBFD"
  rail: "#212836"
  text: "#1E293B"
  text-muted: "#64748B"
  border: "#E2E8F0"
  accent-soft: "#EBF3FF"
  success: "#0D8000"
  warning: "#EA864D"
  danger: "#CC0000"
  chart-line: "#0066FF"
  chart-muted: "#94A3B8"
typography:
  display-sm:
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif'
    fontSize: 1.15rem
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  title-md:
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif'
    fontSize: 0.92rem
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body-md:
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif'
    fontSize: 0.85rem
    fontWeight: 500
    lineHeight: 1.45
  body-sm:
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif'
    fontSize: 0.78rem
    fontWeight: 500
    lineHeight: 1.4
  label-xs:
    fontFamily: '"JetBrains Mono", ui-monospace, monospace'
    fontSize: 0.68rem
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0.04em"
  kpi-value:
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif'
    fontSize: 1.5rem
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  mono-sm:
    fontFamily: '"JetBrains Mono", ui-monospace, monospace'
    fontSize: 0.72rem
    fontWeight: 600
    lineHeight: 1.35
rounded:
  xs: 4px
  sm: 6px
  md: 8px
spacing:
  xs: 6px
  sm: 10px
  md: 14px
  lg: 20px
  xl: 28px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    padding: 8px 16px
    typography: "{typography.body-md}"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
  kpi-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: 14px 16px
  dash-banner:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: 12px 16px
  meta-bar:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    padding: 8px 12px
  badge-readonly:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.primary-hover}"
    rounded: "{rounded.xs}"
    typography: "{typography.mono-sm}"
  panel-section:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: 16px 18px
  shell-sidebar:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.text}"
  shell-rail:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.on-primary}"
  border-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.border}"
  status-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.on-primary}"
  status-warning:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.warning}"
  status-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-primary}"
  chart-series:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.chart-line}"
  chart-axis:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.chart-muted}"
---

# BASE ANTIGRAVITY — Design system

## Overview

BASE ANTIGRAVITY is an **ops console for 4M&C**, not a marketing site. The reference is a **BaseLinker-style OMS desk**: dense queues, filters, KPIs that answer “what needs shipping today?”, and honest read-only data from Mercado Livre into local SQLite.

Visual personality: **corporate signal blue on cool gray workspace** — calm, scannable, slightly technical (mono labels for metrics and badges). It should feel like opening a warehouse control panel at 07:00, not a SaaS landing page. Prefer flat surfaces, thin borders, and tight vertical rhythm over glass, glow, or decorative gradients.

**Scope note for agents:** the **icon rail + status/filas sidebar are frozen** in this revision cycle — do not restyle them. Apply tokens to isolated main panes: **dashboard** (`#view-dashboard`) and **financeiro** (`#view-finance`) — banner/header, KPIs, breakdowns, charts, summary, and table hierarchy. When Financeiro is active, compact global chrome (hide order/BL sub-toolbar) via `body.module-finance` without touching the sidebar.

## Colors

Primary `#0066FF` is the brand signal (CTAs, active chips, chart line). Surfaces stay cool: workspace `#F4F6F9`, cards `#FFFFFF`, muted strips `#F8FAFC`. Text is slate (`#1E293B` / `#64748B`); borders `#E2E8F0` define structure instead of shadows.

Semantic colors are operational, not playful: green for healthy sync, amber for caution/lock, rose for errors. Soft blue `#EBF3FF` tints banners and read-only affordances. Do not introduce purple/indigo as brand primary on the light ops UI.

## Typography

**IBM Plex Sans** carries UI copy in the dashboard — industrial, B2B, distinct from Inter defaults. **JetBrains Mono** is reserved for KPI labels, badges (READ-ONLY), timestamps, and IDs — the “telemetry” layer operators scan first.

Hierarchy: mono uppercase labels → large KPI numerals → short body hints → section titles at ~0.92rem. Avoid display serifs and oversized marketing headlines inside `/app`.

## Layout

Dashboard main uses a **4-up KPI row**, then **2fr / 1fr** for chart + status distribution, full-width orders table, then a two-column bank/integrations summary. Gaps sit around `12–20px`; content viewport padding `20px` (desktop). Keep density high: operators should see KPIs + charts without scrolling on a 1440px laptop when possible.

Financeiro detalhado mirrors that density: **header row** (title + discrete READ-ONLY meta + Excel/CSV), **4-up KPI row**, then **equal two-column** status/day breakdowns and the filtered orders table. Date filter bar stays (KPIs are filter-aware); the Add-order / BaseLinker sub-toolbar hides under `body.module-finance`.

### Responsividade (`/app` shell)

Breakpoints (CSS `max-width`):

| Breakpoint | Intenção |
|:-----------|:---------|
| **≥1280px** | Desktop: rail + sidebar em fluxo, KPI 4 colunas, topbar em linha |
| **≤1279px** | Tablet/laptop estreito: KPI **2** colunas; charts empilham; sidebar ainda inline |
| **≤767px** | Mobile: KPI **1** coluna; topbar empilha; search full-width; ações secundárias compactas; filtros de data com chips em wrap e De/Até full-width |
| **≤374px** | Telefone estreito (~375): padding/rail um pouco mais apertados |

**Sidebar / drawer:** em desktop o painel de filas/menus (`.status-tree-sidebar`) permanece como está (rail + painéis). Em **&lt;768px** o mesmo markup vira **drawer off-canvas** aberto pelo hamburger na topbar (`body.sidebar-open`) — **não** redesenhar filas BL nem itens de guia; só comportamento. Backdrop + Escape fecham o drawer. O icon-rail continua visível (estreito).

**Tabelas:** sem scroll horizontal na página; scroll só dentro de `.table-wrap`. Touch targets ≥44px em controles principais no mobile.

Do not expand the status-tree sidebar width or rail for design experiments on desktop.

## Elevation & Depth

Depth is **border-first**: 1px `border` + optional 1–2px left accent on KPIs. Shadows, if any, stay under `0 1px 2px rgba(0,0,0,0.04)` — no multi-layer glow. Banner uses tonal fill (`accent-soft`), not a floating card stack. Charts sit flush in bordered panels without inset media frames.

## Shapes

Corners are restrained: `4px` chips/badges, `6px` controls, `8px` panels. Prefer sharp-enough rectangles over pill clusters. Full-round pills are limited to small system badges (e.g. READ-ONLY), not KPI containers.

## Components

- **KPI card** — flat surface, mono title, large numeral, one-line hint; optional primary left edge.
- **Dash banner** — compact status strip (local DB + sync CTA); keep secondary text muted.
- **Meta bar** — single muted strip for bank totals (static vs filtered).
- **Panel section** — chart/summary/table wrappers; title + muted parenthetical for filter context.
- **Primary button** — solid `#0066FF`, short label (“Atualizar feed”); hover `#0052CC`.
- **Badge READ-ONLY** — mono, soft blue, never compete with KPIs.

Filter/date chrome outside the dashboard pane stays conservative unless explicitly redesigned.

## Do's and Don'ts

**Do**

- Design for a **logistics OMS desk** (BaseLinker functional density).
- Keep **sidebar / rail markup and CSS untouched** unless the user lifts the freeze.
- Scope visual experiments to `#view-dashboard` / `#view-finance` (or equally isolated main panes).
- Prefer borders and tonal fills over cards-on-cards.
- Preserve filter/KPI JS contracts (`getFilteredOrders`, `updateDashboardKpis`) and the READ-ONLY badge.

**Don't**

- Restyle `.status-tree-sidebar`, `.icon-rail`, filas BL counts, or guide-tree items “for consistency.”
- Use purple-on-white, cream `#F4F1EA` + terracotta serif, or broadsheet hairline newspaper layouts.
- Add hero marketing blocks, stat-strip clutter, or glow/neon accents on the dashboard.
- Invent new hex/fonts outside this file — extend tokens here first.
- Soften global date-filter chrome if it risks layout coupling with the sidebar shell.
