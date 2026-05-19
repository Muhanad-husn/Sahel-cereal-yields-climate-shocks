# Notebook structure — the five-part decision block

This is the decision-discipline pattern for `02_main.ipynb` and
`03_robustness.ipynb`. It is the **lab-work signal** that distinguishes a
portfolio piece from a tutorial — the project's "Show Your Work" discipline.

## When a decision block is required

Every meaningful data-processing decision gets a five-part block: cleaning,
imputing, transforming, categorizing, feature engineering, outlier handling,
threshold setting, deduplication, aggregation. **No conventional choices** —
never "just impute with the mean". Every choice is *educated* and anchored in
a diagnostic.

If a step is mechanical and has no defensible alternative, it does not need a
block — but if you can name two reasonable options, it does.

## The five parts

Each block is a short markdown cell followed by the diagnostic/decision code.

1. **Problem / choice point** — what must be decided, and why it matters
   downstream. Name the consequence of getting it wrong.
2. **Diagnostic analysis** — actual code that explores the data to inform the
   choice. Use the helpers in `src/sahel_yields/diagnostics.py`. This is not
   decoration: the decision in part 4 must follow from what this code shows.
3. **Options considered** — at least 2-3 reasonable alternatives, named
   explicitly (e.g. "Option A: area-weighted", "Option B: cropland-weighted").
4. **Decision + rationale** — the choice, anchored in the part-2 diagnostic,
   not in convention. State *why this option given what we just saw*.
5. **Sensitivity** — a robustness check showing how much the result moves if
   the choice changes; or an explicit, justified note that the result is not
   sensitive to this choice.

## Canonical block skeleton (markdown cell)

```markdown
### Decision N — <short title>

**Problem.** <what must be decided; downstream consequence>

**Options.**
- Option A — <name> : <one line>
- Option B — <name> : <one line>
- Option C — <name> : <one line>

**Decision.** <chosen option>, because <rationale tied to the diagnostic below>.

**Sensitivity.** <result of the robustness check, or justified not-sensitive note>
```

The diagnostic code (part 2) and the sensitivity code (part 5) go in code
cells around this markdown cell.

## The six decisions in this project

Each gets one block inline in `02_main.ipynb` and one row in the README
methodological-decisions table:

1. Drought definition — SPI threshold, growing-season window, single vs.
   cumulative deficit. *(Session 5A)*
2. Trend specification — linear vs. quadratic vs. spline detrend. *(Session 5B)*
3. Spatial weighting — area-weighted vs. cropland-weighted CRU aggregation. *(Session 5A)*
4. Partial drought years — include or exclude years where only some countries
   are in drought. *(Session 5B)*
5. Robust standard errors — country / year / two-way clustering vs. wild-cluster
   bootstrap, given n=6 clusters. *(Session 5B)*
6. FAOSTAT snapshot pinning — which access-date snapshot is canonical, with the
   revision-magnitude diagnostic. *(Session 5A)*
