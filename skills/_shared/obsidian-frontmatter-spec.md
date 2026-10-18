# Mnemosyne Obsidian Frontmatter & Managed Block Specification (`skills/_shared/obsidian-frontmatter-spec.md`)

> Canonical companion to [`skills/_shared/obsidian-conventions.md`](./obsidian-conventions.md).
> Defines the Dual-Write FSRS-4.5 + `obsidian-spaced-repetition` YAML Frontmatter Contract (`RN-09`, `ASR-05`, `SEC-YAML-01`), Vault Sanctuary enforcement (`05 - Fleeting/` hard Exit Code `2`, `RN-10`), and `<!-- mnemosyne:start/end -->` managed block rules.

See [`skills/_shared/obsidian-conventions.md`](./obsidian-conventions.md) for the complete specification:
1. **Vault Sanctuary Law (`CON-03`):** `05 - Fleeting/`, `.git/`, and `.obsidian/` are strictly off-limits (`sys.exit(2)`).
2. **Dual-Write YAML Frontmatter (`RN-09`):**
   - Native FSRS-4.5 keys: `mnemosyne_schema: 1`, `mnemosyne_topic`, `mnemosyne_node`, `mnemosyne_kind`, `mnemosyne_sid`, `mnemosyne_body_hash`, `fsrs_state`, `fsrs_stability`, `fsrs_difficulty`, `fsrs_due`, `fsrs_last`, `fsrs_reps`, `fsrs_lapses`.
   - `obsidian-spaced-repetition` bridge keys: unquoted `sr-due: YYYY-MM-DD`, integer `sr-interval`, integer `sr-ease` ($\text{round}(300 - \frac{D-1}{9}\times 170) \in [130, 300]$), and tags `#review`, `#sr/concept`.
3. **Managed Block (`<!-- mnemosyne:start --> ... <!-- mnemosyne:end -->`):**
   - Contains the 5 epistemological sections (`[!important] Unconditional Truth`, `## Motivated Discovery`, `[!quote] Learner's Own Words`, `## Visual Model`, `[!warning] Misconceptions & Traps Overcome`).
   - Preserves all user-owned YAML keys and all Markdown prose outside the managed markers (`NFR-07`).
