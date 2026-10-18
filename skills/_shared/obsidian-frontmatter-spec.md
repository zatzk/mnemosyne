# Mnemosyne Obsidian Frontmatter & Managed Block Specification (`skills/_shared/obsidian-frontmatter-spec.md`)

> Canonical companion to [`skills/_shared/obsidian-conventions.md`](./obsidian-conventions.md).
> Defines the 3-Way Spaced Repetition Bridge (FSRS-4.5 $\leftrightarrow$ `obsidian-spaced-repetition` `sync-sr` $\leftrightarrow$ AnkiConnect `sync-anki`), Vault Sanctuary enforcement (`05 - Fleeting/quicknotes/` and non-`mnemosyne` fleeting paths hard Exit Code `2`, `RN-10`), Loopback Air-Gap enforcement (`SEC-ANKI-01`), `05 - Fleeting/mnemosyne/` Zettelkasten Graduation, and `<!-- mnemosyne:start/end -->` managed block rules.

See [`skills/_shared/obsidian-conventions.md`](./obsidian-conventions.md) for the complete specification:
1. **Vault Sanctuary & Loopback Air-Gap Law (`CON-03`, `SEC-ANKI-01`):**
   - `05 - Fleeting/quicknotes/` (Omarchy QuickNote widget in `~/.config/omarchy/shell.json`), any path in `05 - Fleeting/` outside `05 - Fleeting/mnemosyne/`, `.git/`, and `.obsidian/` are strictly off-limits (`sys.exit(2)`).
   - `sync-anki` permits only loopback URLs (`http://127.0.0.1:8765`, `localhost`, `::1`); any external URL terminates with Exit Code `2`.
2. **Dedicated Mnemosyne Fleeting Workspace & Graduation (`05 - Fleeting/mnemosyne/`):**
   - `05 - Fleeting/mnemosyne/inbox/`: Study Inbox managed via `mnemosyne.py inbox add` / `inbox list` and surfaced by `/coach` and `/learn`.
   - `05 - Fleeting/mnemosyne/<Topic>/<Node Title>.md`: Fleeting study drafts (`status: fleeting`) for in-progress / unmastered nodes (`learning`, `relearning`, `score <= 2`, or stashed drafts). **Never pushed to Anki before comprehension.**
   - **Full Zettelkasten Graduation:** Once a node passes blind assessment (`score >= 3` / `review` state), `mnemosyne.py synthesize` automatically graduates it from `05 - Fleeting/mnemosyne/<Topic>/` to `02 - Areas/<Domain>/<Topic>/` or `04 - Permanent/` (`status: permanent`), carrying over all user prose outside `<!-- mnemosyne:start/end -->` (and user YAML keys) and removing the fleeting draft.
3. **3-Way Spaced Repetition YAML Frontmatter (`RN-09`, `ASR-05`):**
   - Lifecycle status: `status: fleeting` (in `05 - Fleeting/mnemosyne/<Topic>/`) or `status: permanent` (in `02 - Areas/` and `04 - Permanent/`).
   - Native FSRS-4.5 keys: `mnemosyne_schema: 1`, `mnemosyne_topic`, `mnemosyne_node`, `mnemosyne_kind`, `mnemosyne_sid`, `mnemosyne_body_hash`, `fsrs_state`, `fsrs_stability`, `fsrs_difficulty`, `fsrs_due`, `fsrs_last`, `fsrs_reps`, `fsrs_lapses`.
   - `obsidian-spaced-repetition` bridge keys: unquoted `sr-due: YYYY-MM-DD`, integer `sr-interval`, integer `sr-ease` ($\text{round}(300 - \frac{D-1}{9}\times 170) \in [130, 300]$), and tags `#review`, `#sr/concept`.
   - **AnkiConnect bridge keys (on graduated `status: permanent` notes):** `anki_note_id` and `anki_card_id` synced to deck `Mnemosyne::<Domain>::<Topic>` (model `Mnemosyne Zettelkasten`), with graceful offline fallback (`{"ok": true, "anki_online": false, "status": "skipped_offline"}`) when Anki Desktop is closed, and inbound `getReviewsOfCards` reconciliation logged with `source: "anki"` (excluded from blind-graded `retention`/`refit`).
4. **Managed Block (`<!-- mnemosyne:start --> ... <!-- mnemosyne:end -->`):**
   - Contains the 5 epistemological sections (`[!important] Unconditional Truth`, `## Motivated Discovery`, `[!quote] Learner's Own Words`, `## Visual Model`, `[!warning] Misconceptions & Traps Overcome`).
   - Preserves all user-owned YAML keys and all Markdown prose outside the managed markers (`NFR-07`), including seamlessly migrating them upon graduation from `05 - Fleeting/mnemosyne/<Topic>/` to permanent storage.
