# Mnemosyne Rubric & Probe Contract (`skills/_shared/rubric-contract.md`)

> Canonical companion to [`skills/_shared/rubrics.md`](./rubrics.md).
> Defines Probe-Rubric co-authoring (`RN-06`), bare-claim diagnostic quiz distractors, stem-mirroring prevention, the `produced: false` ceiling (`score <= 2`), and the Blind Assessor JSON contract (`RN-01`, `RN-02`).

See [`skills/_shared/rubrics.md`](./rubrics.md) for the complete specification:
1. **Probe and Rubric Co-Authoring (`RN-06`):** Every criterion in `rubric` must be necessitated by `probe` alone, and zero criteria may mirror facts already stated in the probe's stem.
2. **1–4 FSRS Score & Grade Mapping:**
   - `score: 1` $\leftrightarrow$ `rating: "again"`, `grade: "lapsed"` (Core wrong/absent or 0 criteria met)
   - `score: 2` $\leftrightarrow$ `rating: "hard"`, `grade: "partial"` (Core present with missing secondary criterion, procedure `"slip"`, or `produced: false` ceiling)
   - `score: 3` $\leftrightarrow$ `rating: "good"`, `grade: "recalled"` (All criteria met, `produced: true`)
   - `score: 4` $\leftrightarrow$ `rating: "easy"`, `grade: "recalled"` (All criteria met with precision, `produced: true`, `confidence == 4`)
3. **Hard Ceilings:**
   - `produced: false` caps the score at `score <= 2` (`"hard"` / `"partial"`).
   - Zero criteria met or wrong central mechanism is always `score: 1` (`"again"` / `"lapsed"`).
   - `probe_gap: [<1-based-indices>]` flags unfair rubric criteria without inflating the grade.
