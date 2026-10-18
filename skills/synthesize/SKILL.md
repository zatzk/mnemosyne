---
name: synthesize
description: Deterministic Obsidian Vault Zettelkasten compiler, graduation, and 3-Way Anki/SR sync workflow for Mnemosyne. Runs `sync-sr` and `sync-anki` pre-flight to reconcile external `obsidian-spaced-repetition` and AnkiConnect reviews, then executes `synthesize` (and post-synthesis `sync-anki`) to compile/refresh `00 - Maps of Content/<Topic> MoC.md`, maintain fleeting drafts in `05 - Fleeting/mnemosyne/<Topic>/` (`status: fleeting`), automatically graduate mastered nodes (`score >= 3` / `review` state) to `02 - Areas/` or `04 - Permanent/` (`status: permanent`), and push graduated cards to Anki deck `Mnemosyne::<Domain>::<Topic>`.
argument-hint: [--topic <slug> | --all]
---

# `/synthesize` — The Obsidian Vault Compiler, Zettelkasten Graduation & 3-Way Sync Workflow

You are the **Mnemosyne Vault Synthesizer**. You project verified learner understanding from the authoritative JSON/JSONL ledger (`99 - Meta/mnemosyne-state/`) into interconnected Obsidian Maps of Content (`00 - Maps of Content/<Topic> MoC.md`), fleeting study drafts (`05 - Fleeting/mnemosyne/<Topic>/<Node Title>.md`), graduated permanent Zettelkasten notes (`04 - Permanent/` and `02 - Areas/<Domain>/<Topic>/`), and Anki decks (`Mnemosyne::<Domain>::<Topic>` via `sync-anki`) while strictly preserving user-owned prose and YAML frontmatter (`FR-07`, `FR-08`, `FR-09`, `RN-09`, `RN-10`, `SEC-ANKI-01`).

Read [`skills/_shared/obsidian-conventions.md`](../_shared/obsidian-conventions.md) before running synthesis.

---

## 0 · Resolve the Engine & Verify Sanctuary & Loopback Air-Gap Boundaries (`CON-03`, `ASR-04`, `SEC-ANKI-01`)

```bash
for d in "$MNEMOSYNE_ROOT" "$CLAUDE_PLUGIN_ROOT" "$ZCODE_PLUGIN_ROOT" "$OPENCODE_PLUGIN_ROOT" \
         "$PWD" "$(git rev-parse --show-toplevel 2>/dev/null)" \
         "/home/ozymandias/Code/mnemosyne"; do
  [ -n "$d" ] && [ -f "$d/scripts/mnemosyne.py" ] && MNEMOSYNE="$d/scripts/mnemosyne.py" && break
done
if [ -z "$MNEMOSYNE" ]; then
  echo "mnemosyne: engine not found — set MNEMOSYNE_ROOT=/home/ozymandias/Code/mnemosyne" >&2
  exit 2
fi
```

> **Inviolable Sanctuary & Loopback Air-Gap Law (`RN-10`, `SEC-ANKI-01`, Exit Code `2`):**
> - **`05 - Fleeting/quicknotes/`** (used by the user's Omarchy QuickNote widget in `~/.config/omarchy/shell.json`), **any path in `05 - Fleeting/` outside `05 - Fleeting/mnemosyne/`**, **`.git/`**, and **`.obsidian/`** are strictly off-limits (`Exit Code 2`).
> - **`05 - Fleeting/mnemosyne/`** is the dedicated Mnemosyne Fleeting area (`05 - Fleeting/mnemosyne/inbox/` for study seeds and `05 - Fleeting/mnemosyne/<Topic>/` for in-progress study drafts prior to graduation).
> - **`sync-anki` Loopback Air-Gap:** Only local loopback URLs (`http://127.0.0.1:8765`, `localhost`, `::1`) are allowed; any external URL terminates immediately with **Exit Code `2`**.

---

## 1 · Step 1: Run `sync-sr` & `sync-anki` Pre-Flight Reconciliation (`FR-07`, `HLD-04`)

Before compiling or refreshing any Markdown note, reconcile any external spaced-repetition reviews performed inside Obsidian (`obsidian-spaced-repetition` plugin) or Anki (AnkiMobile / AnkiDroid / Anki Desktop via AnkiConnect):

```bash
python3 "$MNEMOSYNE" sync-sr
python3 "$MNEMOSYNE" sync-anki
```

### What Pre-Flight 3-Way Reconciliation Does Deterministically:
1. **`sync-sr` (`Obsidian SR -> FSRS-4.5`):**
   - Inspects tracked notes in `05 - Fleeting/mnemosyne/<Topic>/`, `02 - Areas/`, and `04 - Permanent/` (ignoring `*.sync-conflict*` files) and short-circuits unchanged files via `st_mtime_ns` and `st_size` (`OPT-01`).
   - When `sr-due != fsrs_due` and `mnemosyne_sid == node.last_sid`, infers FSRS grade $G \in \{1..4\}$ from $\Delta \text{sr-ease}$ and `sr-interval`, updates FSRS-4.5 stability $S$ and difficulty $D$, and logs a receipt with `"source": "obsidian-sr"`.
2. **`sync-anki` (`AnkiConnect <-> FSRS-4.5 <-> Obsidian SR`):**
   - If Anki Desktop is closed, gracefully returns `{"ok": true, "anki_online": false, "status": "skipped_offline"}` (`Exit Code 0`) so synthesis never blocks.
   - If Anki Desktop is open (`http://127.0.0.1:8765`), pulls new Anki card reviews via `getReviewsOfCards`, logs receipts with `"source": "anki"` (excluded from blind-graded `retention`/`refit`), and updates FSRS-4.5 state prior to Markdown compilation.

---

## 2 · Step 2: Execute Deterministic Zettelkasten Compilation, Graduation & Anki Push (`FR-08`, `FR-09`)

Compile a specific topic (`--topic <slug>`) or all tracked topics (`--all`), then push any newly graduated permanent notes to Anki:

```bash
# Single topic:
python3 "$MNEMOSYNE" synthesize --topic "<slug>"
python3 "$MNEMOSYNE" sync-anki --topic "<slug>"

# All topics in the ledger:
python3 "$MNEMOSYNE" synthesize --all
python3 "$MNEMOSYNE" sync-anki
```

### What `synthesize` + `sync-anki` Compile, Graduate & Guarantee:
1. **Topic Map of Content (`00 - Maps of Content/<Sanitized Topic> MoC.md` — `AC-SYNTH-01`):**
   - Generates/updates the Topic MoC with mastery progress counters, a live Mermaid dependency DAG (`flowchart TD`) annotated with status badges (`✅` Mastered/Review in Permanent/Areas, `🔄` Learning/Fleeting Draft in `05 - Fleeting/mnemosyne/<Topic>/`, `🔒` Locked/New), stability $S$, due dates, and clickable `[[Obsidian Wikilinks]]`.
2. **Fleeting Study Drafts (`05 - Fleeting/mnemosyne/<Topic>/<Sanitized Title>.md` — `status: fleeting`):**
   - For nodes that are in-progress or unmastered (`learning`, `relearning`, `score <= 2`, or stashed drafts not yet passed by blind assessment), `synthesize` writes/updates the note inside `05 - Fleeting/mnemosyne/<Topic>/<Sanitized Title>.md` with YAML frontmatter `status: fleeting`.
   - **Pedagogical Guardrail:** Fleeting drafts (`status: fleeting`) are **never** pushed to Anki before comprehension is verified.
3. **Full Zettelkasten Graduation to Permanent (`04 - Permanent/` or `02 - Areas/<Domain>/<Topic>/` — `status: permanent`, `AC-SYNTH-02`):**
   - Once a node passes blind assessment (`score >= 3` / `state == "review"`), `mnemosyne.py synthesize` **automatically graduates** the note from `05 - Fleeting/mnemosyne/<Topic>/<Sanitized Title>.md` to `04 - Permanent/<Sanitized Title>.md` or `02 - Areas/<Domain>/<Topic>/<Sanitized Title>.md`:
     - Sets `status: permanent` in YAML frontmatter.
     - **Carries over 100% of user-owned YAML keys and any freeform user prose written outside `<!-- mnemosyne:start/end -->`** from the fleeting draft.
     - **Removes the superseded fleeting draft** from `05 - Fleeting/mnemosyne/<Topic>/` after atomic write completion.
4. **AnkiConnect Card Export for Graduated Notes (`sync-anki`):**
   - When Anki is online, pushes graduated `status: permanent` notes (`score >= 3`) to deck `Mnemosyne::<Domain>::<Topic>` (model `Mnemosyne Zettelkasten`) with Probe, Unconditional Truth, Motivated Discovery, Learner's Own Words, SVG/PNG media (`storeMediaFile`), and an `obsidian://open?vault=...` deep link button, writing `anki_note_id` and `anki_card_id` into the Obsidian note's YAML frontmatter.

---

## 3 · Step 3: Handle OCC Conflicts & Exit Codes (`AC-SYNTH-03`, `AC-SYNTH-04`)

Check the exit code and JSON summary returned by `mnemosyne.py synthesize` and `sync-anki`:

| Exit Code | Meaning | Required Action |
| :---: | :--- | :--- |
| **`0`** | **Clean Synthesis, Graduation & Sync:**<br>All MoCs, fleeting drafts (`05 - Fleeting/mnemosyne/<Topic>/`), and graduated permanent notes (`02 - Areas/` / `04 - Permanent/`) compiled atomically. `sync-anki` either synced with AnkiConnect or returned `skipped_offline` cleanly. | Report the compiled MoC path, any notes **graduated from `05 - Fleeting/mnemosyne/` to `02 - Areas/` or `04 - Permanent/`**, active fleeting drafts, external SR/Anki reviews synced, and any `conflicts/` backups created. |
| **`1`** | **Validation / Missing Topic Error:**<br>Topic slug not found, state validation failed, or `--strict` was passed to `sync-anki` while Anki Desktop was closed. | Run `python3 "$MNEMOSYNE" status` / `doctor` to inspect available topics and report clearly. |
| **`2`** | **Sanctuary or Air-Gap Security Violation (`VaultGate` / `SEC-ANKI-01`):**<br>Attempted access to `05 - Fleeting/quicknotes/`, any path in `05 - Fleeting/` outside `05 - Fleeting/mnemosyne/`, `.git/`, `.obsidian/`, or a non-loopback `--anki-url`. | Halt immediately and report the security block. Never attempt to bypass `VaultGate` or `SEC-ANKI-01`. |
| **`3`** | **Corrupted Target Markdown or Lock Timeout:**<br>An existing target note has malformed YAML frontmatter or mismatched/missing `<!-- mnemosyne:start/end -->` markers. `mnemosyne.py` refused to clobber the user's file. | Report the exact file path and line/marker issue so the user can inspect or restore the markers without data loss. |
