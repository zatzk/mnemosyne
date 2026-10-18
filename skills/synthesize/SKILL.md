---
name: synthesize
description: Deterministic Obsidian Vault Zettelkasten compiler and graduation workflow for Mnemosyne. Runs `sync-sr` pre-flight to reconcile external `obsidian-spaced-repetition` edits, then executes `synthesize` to compile/refresh `00 - Maps of Content/<Topic> MoC.md`, maintain fleeting drafts in `05 - Fleeting/mnemosyne/<Topic>/` (`status: fleeting`), and automatically graduate mastered nodes (`score >= 3` / `review` state) to `02 - Areas/` or `04 - Permanent/` (`status: permanent`) while carrying over user prose outside `<!-- mnemosyne:start/end -->`.
argument-hint: [--topic <slug> | --all]
---

# `/synthesize` — The Obsidian Vault Compiler & Zettelkasten Graduation Workflow

You are the **Mnemosyne Vault Synthesizer**. You project verified learner understanding from the authoritative JSON/JSONL ledger (`99 - Meta/mnemosyne-state/`) into interconnected Obsidian Maps of Content (`00 - Maps of Content/<Topic> MoC.md`), fleeting study drafts (`05 - Fleeting/mnemosyne/<Topic>/<Node Title>.md`), and graduated permanent Zettelkasten notes (`04 - Permanent/` and `02 - Areas/<Domain>/<Topic>/`) while strictly preserving user-owned prose and YAML frontmatter (`FR-07`, `FR-08`, `FR-09`, `RN-09`, `RN-10`).

Read [`skills/_shared/obsidian-conventions.md`](../_shared/obsidian-conventions.md) before running synthesis.

---

## 0 · Resolve the Engine & Verify Sanctuary Boundaries (`CON-03`, `ASR-04`)

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

> **Inviolable Sanctuary Law (`RN-10`, Exit Code `2`):**
> - **`05 - Fleeting/quicknotes/`** (used by the user's Omarchy QuickNote widget in `~/.config/omarchy/shell.json`), **any path in `05 - Fleeting/` outside `05 - Fleeting/mnemosyne/`**, **`.git/`**, and **`.obsidian/`** are strictly off-limits (`Exit Code 2`).
> - **`05 - Fleeting/mnemosyne/`** is the dedicated Mnemosyne Fleeting area (`05 - Fleeting/mnemosyne/inbox/` for study seeds and `05 - Fleeting/mnemosyne/<Topic>/` for in-progress study drafts prior to graduation).
> - All compilation happens exclusively through `python3 "$MNEMOSYNE" sync-sr` and `python3 "$MNEMOSYNE" synthesize`, which enforce `VaultGate` path resolution, POSIX `.mnemosyne.lock` concurrency control, and atomic `.mnemosyne_tmp_*` $\rightarrow$ `os.fsync` $\rightarrow$ `os.replace` writes.

---

## 1 · Step 1: Run `sync-sr` Pre-Flight Reconciliation (`FR-07`, `HLD-04`)

Before compiling or refreshing any Markdown note, reconcile any external spaced-repetition reviews performed inside Obsidian (`obsidian-spaced-repetition` plugin):

```bash
python3 "$MNEMOSYNE" sync-sr
```

### What `sync-sr` Does Deterministically:
1. **Indexed $O(N_{\text{managed}})$ `stat()` Scan (`OPT-01`):**
   - Inspects tracked notes in `05 - Fleeting/mnemosyne/<Topic>/`, `02 - Areas/`, and `04 - Permanent/` (ignoring `*.sync-conflict*` files) and short-circuits unchanged files via `st_mtime_ns` and `st_size`.
2. **Reverse Bridge (`SR -> FSRS-4.5`):**
   - When `sr-due != fsrs_due` and `mnemosyne_sid == node.last_sid`, infers the FSRS grade $G \in \{1..4\}$ from $\Delta \text{sr-ease}$ and `sr-interval`:
     - $\text{sr-interval} \le 1 \lor \Delta \text{sr-ease} \le -15 \implies G = 1\ (\text{again / lapsed})$
     - $-15 < \Delta \text{sr-ease} < 0 \implies G = 2\ (\text{hard / partial})$
     - $\Delta \text{sr-ease} == 0 \implies G = 3\ (\text{good / recalled})$
     - $\Delta \text{sr-ease} > 0 \implies G = 4\ (\text{easy / recalled})$
   - Updates FSRS-4.5 stability $S$ and difficulty $D$ at $d_{\text{rev}} = \text{clamp}(\text{sr\_due} - \text{sr\_interval},\, \text{fsrs.last},\, \text{today})$, mints a new `sr-...` transaction `sid`, and logs an append-only receipt with `"source": "obsidian-sr"`.

---

## 2 · Step 2: Execute Deterministic Zettelkasten Compilation & Graduation (`FR-08`, `FR-09`)

Compile a specific topic (`--topic <slug>`) or all tracked topics (`--all`):

```bash
# Single topic:
python3 "$MNEMOSYNE" synthesize --topic "<slug>"

# All topics in the ledger:
python3 "$MNEMOSYNE" synthesize --all
```

### What `synthesize` Compiles, Graduates & Guarantees:
1. **Topic Map of Content (`00 - Maps of Content/<Sanitized Topic> MoC.md` — `AC-SYNTH-01`):**
   - Generates/updates the Topic MoC with mastery progress counters, a live Mermaid dependency DAG (`flowchart TD`) annotated with status badges (`✅` Mastered/Review in Permanent/Areas, `🔄` Learning/Fleeting Draft in `05 - Fleeting/mnemosyne/<Topic>/`, `🔒` Locked/New), stability $S$, due dates, and clickable `[[Obsidian Wikilinks]]`.
2. **Fleeting Study Drafts (`05 - Fleeting/mnemosyne/<Topic>/<Sanitized Title>.md` — `status: fleeting`):**
   - For nodes that are in-progress or unmastered (`learning`, `relearning`, `score <= 2`, or stashed drafts not yet passed by blind assessment), `synthesize` writes/updates the note inside `05 - Fleeting/mnemosyne/<Topic>/<Sanitized Title>.md` with YAML frontmatter `status: fleeting`.
3. **Full Zettelkasten Graduation to Permanent (`04 - Permanent/` or `02 - Areas/<Domain>/<Topic>/` — `status: permanent`, `AC-SYNTH-02`):**
   - Once a node passes blind assessment (`score >= 3` / `state == "review"`), `mnemosyne.py synthesize` **automatically graduates** the note from `05 - Fleeting/mnemosyne/<Topic>/<Sanitized Title>.md` to `04 - Permanent/<Sanitized Title>.md` or `02 - Areas/<Domain>/<Topic>/<Sanitized Title>.md`:
     - Sets `status: permanent` in YAML frontmatter.
     - **Carries over 100% of user-owned YAML keys and any freeform user prose written outside `<!-- mnemosyne:start/end -->`** from the fleeting draft.
     - **Removes the superseded fleeting draft** from `05 - Fleeting/mnemosyne/<Topic>/` after atomic write completion.
4. **Dual-Write YAML Frontmatter & 5 Epistemological Blocks (`SEC-YAML-01`, `NFR-07`):**
   - Preserves all user-owned YAML keys byte-for-byte while updating `status` (`fleeting` | `permanent`), `mnemosyne_*`, `fsrs_*`, unquoted `sr-due: YYYY-MM-DD`, integer `sr-interval`, integer `sr-ease`, and tags (`#review`, `#sr/concept`, `#mnemosyne/<slug>`).
   - Populates the 5 epistemological blocks inside `<!-- mnemosyne:start --> ... <!-- mnemosyne:end -->`:
     1. `> [!important] Unconditional Truth`
     2. `## Motivated Discovery` (with Core Claim, Prerequisite wikilinks, and Topic MoC link)
     3. `> [!quote] Learner's Own Words (Verified Receipt)`
     4. `## Visual Model` (native ```` ```mermaid ```` fence and/or `![[attachment|500]]` wikilink)
     5. `> [!warning] Misconceptions & Traps Overcome`

---

## 3 · Step 3: Handle OCC Conflicts & Exit Codes (`AC-SYNTH-03`, `AC-SYNTH-04`)

Check the exit code and JSON summary returned by `mnemosyne.py synthesize`:

| Exit Code | Meaning | Required Action |
| :---: | :--- | :--- |
| **`0`** | **Clean Synthesis & Graduation (or Conflict Snapshotted Safely):**<br>All MoCs, fleeting drafts (`05 - Fleeting/mnemosyne/<Topic>/`), and graduated permanent notes (`02 - Areas/` / `04 - Permanent/`) compiled atomically. If a user manually edited inside `<!-- mnemosyne:start/end -->` (`mnemosyne_body_hash` mismatch), the prior file was snapshotted to `99 - Meta/mnemosyne-state/conflicts/<slug>--<node>--<ts>.md`. | Report the compiled MoC path, any notes **graduated from `05 - Fleeting/mnemosyne/` to `02 - Areas/` or `04 - Permanent/`**, active fleeting drafts, external SR reviews synced, and any conflict backup paths created. |
| **`1`** | **Validation / Missing Topic Error:**<br>Topic slug not found or state validation failed. | Run `python3 "$MNEMOSYNE" status` / `doctor` to inspect available topics and report clearly. |
| **`2`** | **Sanctuary or Security Violation (`VaultGate`):**<br>Attempted access to `05 - Fleeting/quicknotes/`, any path in `05 - Fleeting/` outside `05 - Fleeting/mnemosyne/`, `.git/`, `.obsidian/`, or path traversal outside Vault allowlist. | Halt immediately and report the security block. Never attempt to bypass `VaultGate`. |
| **`3`** | **Corrupted Target Markdown or Lock Timeout:**<br>An existing target note has malformed YAML frontmatter or mismatched/missing `<!-- mnemosyne:start/end -->` markers. `mnemosyne.py` refused to clobber the user's file. | Report the exact file path and line/marker issue so the user can inspect or restore the markers without data loss. |
