# Source / attribution

Skill adapted for Cursor Agent Skills from:

- **Repo:** https://github.com/google-labs-code/design.md
- **Spec:** `docs/spec.md` (alpha)
- **Philosophy:** `PHILOSOPHY.md`
- **CLI package:** `@google/design.md` on npm

## What was adapted (not 1:1)

The upstream repo is primarily a **format specification + CLI**, not a single consumer Cursor skill for UI work. Its `.agents/skills/` folder contains *project-internal* skills (`ink`, `tdd`, …), not a DESIGN.md authoring skill.

Related Google Labs skills in [stitch-skills](https://github.com/google-labs-code/stitch-skills) (`design-md`, `extract-design-md`, `taste-design`) target **Google Stitch** MCP workflows and different output section layouts. This skill instead:

1. Follows the **canonical DESIGN.md token + section order** from `design.md`
2. Adds Cursor discovery (`description` triggers) and a code-first apply/extract workflow
3. Documents complementarity with local frontend composition rules (anti-generic UI)
4. Keeps Stitch-specific MCP steps out of the default path

Upstream examples such as Atmospheric Glass / Heritage are format illustrations only — do not adopt them as this product's brand unless asked.
