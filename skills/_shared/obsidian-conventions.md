# Mnemosyne Obsidian Vault & Zettelkasten Conventions (`skills/_shared/obsidian-conventions.md`)

> **Binding Vault & Markdown Specification for `mnemosyne.py`, `/synthesize`, `/learn`, `/review`, `/visualize`, and `/coach`.**
> Enforces `RN-09` (Dual-Write Spaced Repetition Sync), `RN-10` (Vault Sanctuary & Epistemological Note Structure), `CON-03`..`CON-06`, `ASR-01`, `ASR-04`, `ASR-05`, and `SEC-YAML-01`.

---

## 1. The Inviolable Vault Sanctuary Law (`CON-03`, `ASR-04`, Exit Code `2`)

Mnemosyne operates directly inside the user's canonical Obsidian Vault (`MNEMOSYNE_VAULT_PATH`, defaulting to `/home/ozymandias/GoogleDrive/Obsidian/Vault` or submodule `<repo>/vault/Vault`).

> [!CAUTION]
> **HARD SANCTUARY BLOCK — EXIT CODE `2`**
> The following directories are **inviolable sanctuaries**:
> - **`05 - Fleeting/`** (User's private raw scratchpad and fleeting thoughts)
> - **`.git/`** (Git repository internals)
> - **`.obsidian/`** (Obsidian workspace, plugin binaries, and hotkeys)
>
> **Rule:** Neither `scripts/mnemosyne.py` (`VaultGate`) nor any skill or subagent may **ever** read, list, create, modify, or delete any file inside `05 - Fleeting/`, `.git/`, or `.obsidian/`. Any path (lexical or post-symlink `Path.resolve()`) touching these directories immediately aborts with **Exit Code `2`** and zero filesystem changes (`AC-SYNTH-03`).

---

## 2. Canonical Vault Folder Taxonomy (`CON-05`)

All Mnemosyne reads and writes are strictly confined to the following directory taxonomy:

| Vault Directory | Access Mode | Role & File Naming Convention |
| :--- | :---: | :--- |
| **`00 - Maps of Content/`** | Read / Write | Topic Maps of Content: `<Sanitized Topic Title> MoC.md` (e.g., `Raft Distributed Consensus MoC.md`). Contains topic progress summary, mastery table, and a Mermaid dependency DAG (`flowchart TD`) with live status badges (`✅`, `🔄`, `🔒`) and `[[Wikilinks]]`. |
| **`02 - Areas/<Domain>/`** | Read / Write | Domain-scoped atomic Zettelkasten notes when `note_target == "02 - Areas"`: `02 - Areas/<Sanitized Domain>/<Sanitized Node Title>.md`. |
| **`04 - Permanent/`** | Read / Write | Evergreen atomic Zettelkasten notes when `note_target == "04 - Permanent"` (default): `04 - Permanent/<Sanitized Node Title>.md`. |
| **`99 - Meta/00 - Templates/`** | **Read-Only** | User's Obsidian note templates (read-only reference; never overwritten). |
| **`99 - Meta/attachments/`** | Read / Write | Self-verified visual artifacts: `<topic>-<node>.svg` (or `viz-<slug>-<ts>.svg`) and `<topic>-<node>-explorable.html` (or `viz-<slug>-<ts>.html`), plus `report.html` dashboard. |
| **`99 - Meta/mnemosyne-state/`** | Read / Write | **Single Authoritative State Ledger (`HLD-01`):**<br>• `.mnemosyne.lock` (PID-checked POSIX advisory mutex)<br>• `learner-model.json` (FSRS-4.5 $W[0..16]$, retention target, preferences)<br>• `topics/<slug>.json` (Curriculum DAG, node rubrics, FSRS state, OCC metadata)<br>• `receipts/<slug>.jsonl` (Append-only cryptographic receipt ledger)<br>• `stash.jsonl` (Crash-safe ungraded learner productions)<br>• `misconceptions.json` & `experiments.json`<br>• `conflicts/<slug>--<node>--<ts>.md` (OCC & managed-block conflict snapshots) |
| **`05 - Fleeting/`** | **FORBIDDEN (`Exit 2`)** | **Inviolable Sanctuary.** Zero reads, zero writes. |

### 2.1 Slug & Filename Sanitization (`CON-06`)
- **Topic Slugs & Node IDs:** Must match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` (kebab-case recommended, no spaces, slashes, or leading dots).
- **Markdown Filenames (`<Sanitized Title>.md`):** Normalized via Unicode `NFC`, stripped of control characters (`0x00–0x1F`), with filesystem-unsafe characters `/\:*?"<>|` replaced by `-`. The un-sanitized human title is preserved in YAML `title`, `aliases`, and the `# Heading`.

---

## 3. Dual-Write YAML Frontmatter Contract (`RN-09`, `ASR-05`, `SEC-YAML-01`)

Every compiled concept, procedure, or fact note in `02 - Areas/` and `04 - Permanent/` carries a deterministic dual-write YAML frontmatter block that bridges Mnemosyne's FSRS-4.5 engine with the **`obsidian-spaced-repetition`** community plugin:

```yaml
---
title: "Split-Brain & Quorum Intersection"
aliases:
  - "Split-Brain & Quorum Intersection"
  - "split-brain-impossibility"
tags:
  - review
  - sr/concept
  - mnemosyne/consensus-raft
mnemosyne_schema: 1
mnemosyne_topic: "consensus-raft"
mnemosyne_node: "split-brain-impossibility"
mnemosyne_kind: "concept"
mnemosyne_sid: "st-20261018T141205Z-a9f3c1"
mnemosyne_body_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
fsrs_state: "review"
fsrs_stability: 3.7145
fsrs_difficulty: 5.1618
fsrs_due: "2026-10-22"
fsrs_last: "2026-10-18"
fsrs_reps: 1
fsrs_lapses: 0
sr-due: 2026-10-22
sr-interval: 4
sr-ease: 222
---
```

### 3.1 Span-Preserving YAML Rules (`SEC-YAML-01`)
1. **User-Owned Keys Preserved Byte-for-Byte:** Any custom YAML keys added by the user (e.g., `cssclasses`, `up: "[[Distributed Systems MoC]]"`, `status`, custom `tags` or `aliases`) are preserved untouched across re-syntheses.
2. **Additive Tag Merging:** Mnemosyne ensures `#review`, `#sr/concept` (or `#sr/procedure`, `#sr/fact`), and `#mnemosyne/<topic>` are present in `tags` without removing any user-added tags.
3. **Unquoted `sr-*` Scalars for Plugin Regex Compatibility:**
   - `sr-due` MUST be emitted as an unquoted ISO date (`sr-due: YYYY-MM-DD`).
   - `sr-interval` MUST be emitted as an integer $\ge 1$ (`max(1, round(fsrs.interval))`).
   - `sr-ease` MUST be emitted as an integer in $[130, 300]$ computed from FSRS difficulty $D \in [1, 10]$:
     $$\text{sr-ease} = \text{round}\left(300 - \frac{D - 1.0}{9.0} \times 170\right)$$
4. **Bi-Directional `sync-sr` Reconciliation (`ASR-05`):**
   - When the user reviews a note inside Obsidian using `obsidian-spaced-repetition`, the plugin updates `sr-due`, `sr-interval`, and `sr-ease` while `mnemosyne_sid` remains equal to `node.last_sid`.
   - Running `python3 scripts/mnemosyne.py sync-sr` (also run automatically before `synthesize`) detects `sr-due != fsrs_due` (ignoring `*.sync-conflict*` files), infers the FSRS rating $G \in \{1..4\}$ from $\Delta \text{sr-ease}$ and `sr-interval`:
     - $\text{sr-interval}_{\text{md}} \le 1 \lor \Delta \text{sr-ease} \le -15 \implies G = 1\ (\text{again / lapsed})$
     - $-15 < \Delta \text{sr-ease} < 0 \implies G = 2\ (\text{hard / partial})$
     - $\Delta \text{sr-ease} == 0 \implies G = 3\ (\text{good / recalled})$
     - $\Delta \text{sr-ease} > 0 \implies G = 4\ (\text{easy / recalled})$
   - Applies the FSRS-4.5 transition at $d_{\text{rev}} = \text{clamp}(\text{sr\_due} - \text{sr\_interval},\, \text{fsrs.last},\, \text{today})$, appends a receipt with `"source": "obsidian-sr"`, and re-synchronizes the YAML frontmatter.

---

## 4. Managed Block Rules (`<!-- mnemosyne:start/end -->`) & OCC Safety (`RN-10`, `NFR-07`)

Every compiled note separates **Mnemosyne-managed epistemological synthesis** from **user-owned freeform Zettelkasten prose**:

```markdown
# <Human Node Title>

<!-- mnemosyne:start -->
> [!important] Unconditional Truth
> <Caveat-free universal statement or generative definition ($LaTeX$ enabled)>

## Motivated Discovery
<3Blue1Brown "Pain before Pill" derivation showing how the learner could have invented this bridge>

**Core Claim:** <Declarative testable claim>

**Prerequisites:** [[<Prerequisite Note Title>]] | **Contrasts With:** [[<Contrast Note Title>]] | **Topic MoC:** [[<Topic Title> MoC]]

> [!quote] Learner's Own Words (Verified Receipt `<sid>` · `<YYYY-MM-DD>`)
> <Verbatim learner production from the latest recalled/partial receipt>

## Visual Model
```mermaid
<Validated Mermaid diagram if node.mermaid_block is present>
```
![[<Attached SVG or Explorable HTML if node.artifact is present>|500]]

> [!warning] Misconceptions & Traps Overcome
> - <Resolved/logged misconceptions and contrast boundaries>
<!-- mnemosyne:end -->

## Personal Notes & Further Connections
(User-authored prose, backlinks, literature citations, and code snippets outside the managed markers are 100% preserved across all re-syntheses.)
```

### 4.1 Optimistic Concurrency Control (OCC) & Corruption Guards (`AC-SYNTH-04`)
1. **5 Epistemological Blocks Inside Managed Markers:**
   - `[!important] Unconditional Truth`
   - `## Motivated Discovery` (with Core Claim & Prerequisite/MoC wikilinks)
   - `[!quote] Learner's Own Words (Verified Receipt)`
   - `## Visual Model` (only rendered when a verified Mermaid block or attachment exists)
   - `[!warning] Misconceptions & Traps Overcome`
2. **Marker Escape Sanitization (`SEC-MD-*`):**
   - Any literal occurrence of `<!-- mnemosyne:start -->`, `<!-- mnemosyne:end -->`, or standalone YAML fences `\n---\n` inside untrusted learner productions or rationales is neutralized before compilation so it can never break the managed block parser.
3. **Malformed File Halt (Exit Code `3`):**
   - If an existing target `.md` file has corrupted YAML frontmatter (missing closing `---`) or mismatched/inverted `<!-- mnemosyne:start -->` / `<!-- mnemosyne:end -->` markers, `mnemosyne.py synthesize` refuses to clobber the file and exits with **Exit Code `3`**.
4. **Conflict Snapshotting (`99 - Meta/mnemosyne-state/conflicts/`):**
   - If the SHA-256 hash of the existing content inside `<!-- mnemosyne:start --> ... <!-- mnemosyne:end -->` differs from `mnemosyne_body_hash` (meaning the user manually edited inside the managed block), or if `st_mtime_ns` changed concurrently during synthesis, `mnemosyne.py` snapshots the full prior file to `99 - Meta/mnemosyne-state/conflicts/<slug>--<node>--<timestamp>.md` before performing an atomic `.mnemosyne_tmp_*` $\rightarrow$ `os.fsync` $\rightarrow$ `os.replace` update.
