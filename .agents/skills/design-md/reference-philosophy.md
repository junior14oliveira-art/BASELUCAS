# DESIGN.md Philosophy

Upstream: [google-labs-code/design.md PHILOSOPHY.md](https://github.com/google-labs-code/design.md/blob/main/PHILOSOPHY.md)

DESIGN.md captures how a design looks, feels, and behaves. **The prose is where the design lives.** Everything else supports it.

**The quality of a generated design is determined less by the precision of its values than by how clearly the intent is described.**

## Prose, not tokens, is the focus

DESIGN.md has tokens and prose. The specification focuses on design context for consistency across generations. Prose is the most vital part. Token values serve as context and are not rendering instructions. Prefer documenting the nature of the design over reinventing CSS/token tooling.

## A specific reference carries more than adjectives

A design that references "A 1970s graduate lecture handout in the tradition of an old and established university" evokes a complete world. That single sentence carries more useful information than a dozen metric values.

"Modern, clean, trustworthy, premium" evokes nothing specific — models produce something in the center of those words (generic output). Adjectives describe a region. A specific reference describes a point.

## Negative constraints

A clear design reference carries restrictions automatically. Naming the object names what it is not. An intentional list of don'ts is useful; a long rambling list often means the description was too vague. Strong reference + intentional do's/don'ts is the sweet spot.

## The format grows through users

The spec defines a structural minimum: name, and categories (colors, typography, spacing, rounded, components) universal enough to standardize. Beyond that minimum is yours. Unknown sections (motion, iconography, etc.) are welcome; agents read the prose; the linter accepts extra context.
