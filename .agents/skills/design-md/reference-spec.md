# DESIGN.md Format Specification (condensed)

Upstream full spec: [docs/spec.md](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md) · status: `alpha`

DESIGN.md is a self-contained plain-text design system for humans and AI agents. Two parts:

1. **Optional YAML front matter** — machine-readable design tokens (`---` fences)
2. **Markdown body** — human-readable rationale under `##` sections

Tokens are normative. Prose provides context for how to apply them.

## Token schema

```yaml
version: <string>          # optional, current: "alpha"
name: <string>
description: <string>      # optional
omitted: <string[] | OmittedSection[]> # optional
colors:
  <token-name>: <Color>
typography:
  <token-name>: <Typography>
rounded:
  <scale-level>: <Dimension>
spacing:
  <scale-level>: <Dimension | number>
components:
  <component-name>:
    <token-name>: <string | token reference>
```

### Types

| Type | Format | Example |
|:-----|:-------|:--------|
| Color | Any CSS color | `"#1A1C1E"`, `oklch(...)` |
| Dimension | number + `px`/`em`/`rem` | `48px`, `-0.02em` |
| Token reference | `{path.to.token}` | `{colors.primary}` |
| Typography | object | `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing`, `fontFeature`, `fontVariation` |

**Omitted**: suppress missing-section warnings, e.g. `omitted: [spacing]` or `{ section: rounded, reason: "..." }`.

Hex `#RRGGBB` is the recommended default for colors. Contrast checks convert to sRGB internally.

## Section order

Present sections must appear in this order (`##` headings):

| # | Section | Aliases |
|:--|:--------|:--------|
| 1 | Overview | Brand & Style |
| 2 | Colors | |
| 3 | Typography | |
| 4 | Layout | Layout & Spacing |
| 5 | Elevation & Depth | Elevation |
| 6 | Shapes | |
| 7 | Components | |
| 8 | Do's and Don'ts | |

Optional `#` document title is ignored as a section.

### Section intent (short)

- **Overview** — personality, audience, emotional response; fallback when no token covers a decision
- **Colors** — palettes + roles; prefer `primary` (linter warns if colors exist without it)
- **Typography** — levels/roles (often 9–15); family character + hierarchy
- **Layout** — grid/margins/rhythm; spacing tokens
- **Elevation & Depth** — shadows vs tonal layers / borders
- **Shapes** — corner language; `rounded` tokens
- **Components** — atoms (buttons, chips, lists, inputs…); variants as related keys
- **Do's and Don'ts** — guardrails

### Component tokens

Valid properties: `backgroundColor`, `textColor`, `typography`, `rounded`, `padding`, `size`, `height`, `width`.

```yaml
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    rounded: "{rounded.sm}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "{colors.tertiary-container}"
```

## Recommended token names (non-normative)

- Colors: `primary`, `secondary`, `tertiary`, `neutral`, `surface`, `on-surface`, `error`
- Typography: `headline-display`, `headline-lg`, `headline-md`, `body-lg`, `body-md`, `body-sm`, `label-lg`, `label-md`, `label-sm`
- Rounded: `none`, `sm`, `md`, `lg`, `xl`, `full`

## Consumer behavior for unknown content

| Scenario | Behavior |
|:---------|:---------|
| Unknown section heading | Preserve; do not error |
| Unknown color/typography token name | Accept if value valid |
| Unknown component property | Accept with warning |
| Duplicate section heading | Error; reject |

## CLI lint rules (summary)

`broken-ref` (error), `missing-primary`, `contrast-ratio`, `orphaned-tokens`, `token-summary`, `missing-sections`, `missing-typography`, `section-order`, `unknown-key`, `token-like-ignored`, `omitted-rules`.

```bash
npx -p @google/design.md designmd lint DESIGN.md
npx -p @google/design.md designmd diff DESIGN.md DESIGN-v2.md
npx -p @google/design.md designmd export --format css-tailwind DESIGN.md
npx -p @google/design.md designmd spec
```
