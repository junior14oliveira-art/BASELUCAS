---
name: design-md
description: >-
  Creates, maintains, and applies DESIGN.md visual-identity files (Google Labs
  format: YAML tokens + prose). Use when doing frontend design, UI layout,
  landing/corporate pages, /app styling, design tokens, Tailwind theme export,
  extracting a design system from code, or when the user mentions DESIGN.md,
  design system, visual identity, or design.md.
---

# DESIGN.md — Visual identity for coding agents

Source format: [google-labs-code/design.md](https://github.com/google-labs-code/design.md) (spec `alpha`).

DESIGN.md gives agents a **persistent, structured** design system: machine-readable tokens (YAML front matter) + human-readable rationale (markdown). **Tokens are normative values; prose explains why and how to apply them.**

## When to use

- Creating or updating a project `DESIGN.md`
- Generating UI (React/Vue/CSS/Tailwind) that must match a design system
- Extracting tokens/patterns from existing frontend code into DESIGN.md
- Linting / diffing / exporting tokens via `@google/design.md` CLI
- User asks for design system, visual identity, brand UI, or `/app` styling

## Complementarity with Cursor frontend rules

This skill defines the **DESIGN.md format and workflow**. Project/user **frontend design rules** (composition, hero budget, anti-generic look) still apply when implementing UI.

| Layer | Role |
|:------|:-----|
| Cursor frontend rules | How to compose pages (hero, cards, motion, anti-clichés) |
| This skill / DESIGN.md | What the brand looks like (tokens + rationale) |

Do **not** copy example themes from `examples/` as the project brand. Official examples (Heritage limestone, Atmospheric Glass purple gradients, etc.) illustrate **format only**. Prefer a specific product reference over generic adjectives. Align Do's/Don'ts in DESIGN.md with project rules (e.g. avoid purple-on-white, cream+#F4F1EA+serif terracotta, broadsheet hairline layouts) unless the user explicitly wants that look.

## Quick workflow

1. **Locate or create** `DESIGN.md` at the project root (or path the user names).
2. **Read** existing DESIGN.md before changing visual UI.
3. **Apply** tokens + prose; do not invent colors/fonts/radii absent from the file (extend DESIGN.md first if needed).
4. **Validate** when changing the file: `npx -p @google/design.md designmd lint DESIGN.md` (Windows: use `designmd` alias — see below).
5. **Deep refs** only when needed:
   - Spec: [reference-spec.md](reference-spec.md)
   - Philosophy: [reference-philosophy.md](reference-philosophy.md)
   - Format examples: [examples/](examples/)

## File structure

```md
---
version: alpha
name: <Brand or product name>
description: <optional>
omitted: []   # optional intentional omissions
colors:
  primary: "#..."
typography:
  body-md:
    fontFamily: ...
    fontSize: 1rem
rounded:
  sm: 4px
spacing:
  md: 16px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
---

## Overview
## Colors
## Typography
## Layout
## Elevation & Depth
## Shapes
## Components
## Do's and Don'ts
```

Sections present must keep this order (aliases: Brand & Style; Layout & Spacing; Elevation). Unknown `##` sections are allowed; duplicate headings are invalid.

### Token essentials

- **Color**: any CSS color; hex preferred
- **Dimension**: `px` | `em` | `rem`
- **Reference**: `{colors.primary}`, `{typography.body-md}` inside components
- **Typography object**: `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`, optional `fontFeature` / `fontVariation`
- **Component props**: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, `width` — variants as sibling keys (`button-primary-hover`)

## Authoring principles (from official philosophy)

1. **Prose over token lists** — quality comes from clear intent, not only precise values.
2. **Specific references beat adjectives** — “1970s graduate lecture handout” > “modern, clean, premium”.
3. **Negative constraints** — intentional Don'ts; a strong reference already implies many bans.
4. **Tokens support prose** — they are context/reference, not a replacement for CSS/tooling decades of work.

## Creating DESIGN.md from a codebase

1. Detect stack (`package.json`, Tailwind config, CSS vars, theme files).
2. Extract colors, type, spacing, radius, elevation, key components.
3. Deduplicate near-identical colors; name by **role + character** (not “Blue”).
4. Write YAML front matter with at least `name` + `colors` (prefer `primary`).
5. Write ordered prose sections with **why**, roles, and Do's/Don'ts.
6. Lint with the CLI when available.

## Applying DESIGN.md to UI code

- Map tokens → CSS variables / Tailwind theme / component styles.
- Follow Components + Do's and Don'ts before inventing patterns.
- Prefer export for tooling:
  - `npx -p @google/design.md designmd export --format css-tailwind DESIGN.md`
  - `npx -p @google/design.md designmd export --format json-tailwind DESIGN.md`
  - `npx -p @google/design.md designmd export --format dtcg DESIGN.md`

## CLI (`@google/design.md`)

```bash
# Lint (structured JSON findings)
npx -p @google/design.md designmd lint DESIGN.md

# Diff regressions
npx -p @google/design.md designmd diff DESIGN.md DESIGN-v2.md

# Spec dump for prompts
npx -p @google/design.md designmd spec
```

On Windows/PowerShell, prefer `designmd` via `npx -p @google/design.md designmd …` — the `design.md` bin name can collide with the Markdown file association.

Key lint rules: `broken-ref` (error), `missing-primary`, `contrast-ratio`, `orphaned-tokens`, `missing-typography`, `section-order`, `unknown-key`.

## Checklist before finishing UI work

- [ ] Read current `DESIGN.md` (or created one with user intent)
- [ ] No new hex/fonts/radii outside the file (or file updated first)
- [ ] Section order / refs valid; lint clean when CLI used
- [ ] Frontend composition rules still respected
- [ ] Examples in this skill used as format reference only
