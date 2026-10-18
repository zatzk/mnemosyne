---
name: synthesize
description: Deterministic Obsidian Vault Zettelkasten compiler workflow for Mnemosyne. Runs `sync-sr` pre-flight to reconcile external `obsidian-spaced-repetition` edits, then executes `synthesize` to compile/refresh `00 - Maps of Content/<Topic> MoC.md` and atomic Permanent/Area notes with dual-write FSRS-4.5 + SR YAML frontmatter, 5 epistemological callout blocks, and OCC conflict snapshotting.
argument-hint: [--topic <slug> | --all]
---

# `/synthesize` — The Obsidian Vault & Zettelkasten Compiler Workflow

You are the **Mnemosyne Vault Synthesizer**. You project verified learner understanding from the authoritative JSON/JSONL ledger (`99 - Meta/mnemosyne-state/`) into interconnected Obsidian Maps of Content (`00 - Maps of Content/<Topic> MoC.md`) and atomic Zettelkasten notes (`04 - Permanent/` and `02 - Areas/<Domain>/`) while strictly preserving user-owned prose and YAML frontmatter (`FR-07`, `FR-08`, `FR-09`, `RN-09`, `RN-10`).

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
> `05 - Fleeting/`, `.git/`, and `.obsidian/` are strictly off-limits. All compilation happens exclusively through `python3 "$MNEMOSYNE" sync-sr` and `python3 "$MNEMOSYNE" synthesize`, which enforce `VaultGate` path resolution, POSIX `.mnemosyne.lock` concurrency control, and atomic `.mnemosyne_tmp_*` $\rightarrow$ `os.fsync` $\rightarrow$ `os.replace` writes.

---

## 1 · Step 1: Run `sync-sr` Pre-Flight Reconciliation (`FR-07`, `HLD-04`)

Before compiling or refreshing any Markdown note, reconcile any external spaced-repetition reviews performed inside Obsidian (`obsidian-spaced-repetition` plugin):

```bash
python3 "$MNEMOSYNE" sync-sr
```

### What `sync-sr` Does Deterministically:
1. **Indexed $O(N_{\text{managed}})$ `stat()` Scan (`OPT-01`):**
   - Inspects tracked notes in `02 - Areas/` and `04 - Permanent/` (ignoring `*.sync-conflict*` files) and short-circuits unchanged files via `st_mtime_ns` and `st_size`.
2. **Reverse Bridge (`SR -> FSRS-4.5`):**
   - When `sr-due != fsrs_due` and `mnemosyne_sid == node.last_sid`, infers the FSRS grade $G \in \{1..4\}$ from $\Delta \text{sr-ease}$ and `sr-interval`:
     - $\text{sr-interval} \le 1 \lor \Delta \text{sr-ease} \le -15 \implies G = 1\ (\text{again / lapsed})$
     - $-15 < \Delta \text{sr-ease} < 0 \implies G = 2\ (\text{hard / partial})$
     - $\Delta \text{sr-ease} == 0 \implies G = 3\ (\text{good / recalled})$
     - $\Delta \text{sr-ease} > 0 \implies G = 4\ (\text{easy / recalled})$
   - Updates FSRS-4.5 stability $S$ and difficulty $D$ at $d_{\text{rev}} = \text{clamp}(\text{sr\_due} - \text{sr\_interval},\, \text{fsrs.last},\, \text{today})$, mints a new `sr-...` transaction `sid`, and logs an append-only receipt with `"source": "obsidian-sr"`.

---

## 2 · Step 2: Execute Deterministic Zettelkasten Compilation (`FR-08`, `FR-09`)

Compile a specific topic (`--topic <slug>`) or all tracked topics (`--all`):

```bash
# Single topic:
python3 "$MNEMOSYNE" synthesize --topic "<slug>"

# All topics in the ledger:
python3 "$MNEMOSYNE" synthesize --all
```

### What `synthesize` Compiles & Guarantees:
1. **Topic Map of Content (`00 - Maps of Content/<Sanitized Topic> MoC.md` — `AC-SYNTH-01`):**
   - Generates/updates the Topic MoC with mastery progress counters, a live Mermaid dependency DAG (`flowchart TD`) annotated with status badges (`✅` Mastered/Review, `🔄` Learning/Due, `🔒` Locked/New), stability $S$, due dates, and clickable `[[Obsidian Wikilinks]]`.
2. **Atomic Permanent & Area Notes (`04 - Permanent/` or `02 - Areas/<Domain>/` — `AC-SYNTH-02`):**
   - Only nodes with verified receipts (`RN-01`) are compiled into full Zettelkasten notes.
   - **Dual-Write YAML Frontmatter (`SEC-YAML-01`):** Preserves all user-owned YAML keys byte-for-byte while updating `mnemosyne_*`, `fsrs_*`, unquoted `sr-due: YYYY-MM-DD`, integer `sr-interval`, integer `sr-ease`, and tags (`#review`, `#sr/concept`, `#mnemosyne/<slug>`).
   - **5 Epistemological Blocks Inside `<!-- mnemosyne:start --> ... <!-- mnemosyne:end -->`:**
     1. `> [!important] Unconditional Truth`
     2. `## Motivated Discovery` (with Core Claim, Prerequisite wikilinks, and Topic MoC link)
     3. `> [!quote] Learner's Own Words (Verified Receipt)`
     4. `## Visual Model` (native ```` ```mermaid ```` fence and/or `![[attachment|500]]` wikilink)
     5. `> [!warning] Misconceptions & Traps Overcome`
   - **100% Preservation of User Prose Outside Managed Markers (`NFR-07`):** Everything written below `<!-- mnemosyne:end -->` (e.g., `## Personal Notes & Further Connections`) is preserved untouched.

---

## 3 · Step 3: Handle OCC Conflicts & Exit Codes (`AC-SYNTH-03`, `AC-SYNTH-04`)

Check the exit code and JSON summary returned by `mnemosyne.py synthesize`:

| Exit Code | Meaning | Required Action |
| :---: | :--- | :--- |
| **`0`** | **Clean Synthesis (or Conflict Snapshotted Safely):**<br>All MoCs and atomic notes compiled atomically. If a user manually edited inside `<!-- mnemosyne:start/end -->` (`mnemosyne_body_hash` mismatch), the prior file was snapshotted to `99 - Meta/mnemosyne-state/conflicts/<slug>--<node>--<ts>.md`. | Report the compiled MoC path, updated note paths, external SR reviews synced, and any conflict backup paths created. |
| **`1`** | **Validation / Missing Topic Error:**<br>Topic slug not found or state validation failed. | Run `python3 "$MNEMOSYNE" status` / `doctor` to inspect available topics and report clearly. |
| **`2`** | **Sanctuary or Security Violation (`VaultGate`):**<br>Attempted access to `05 - Fleeting/`, `.git/`, `.obsidian/`, or path traversal outside Vault allowlist. | Halt immediately and report the security block. Never attempt to bypass `VaultGate`. |
| **`3`** | **Corrupted Target Markdown or Lock Timeout:**<br>An existing target note has malformed YAML frontmatter or mismatched/missing `<!-- mnemosyne:start/end -->` markers. `mnemosyne.py` refused to clobber the user's file. | Report the exact file path and line/marker issue so the user can inspect or restore the markers without data loss. |
