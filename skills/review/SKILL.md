---
name: review
description: Spaced-repetition retrieval, 3-Way SR/Anki reconciliation (`sync-sr` + `sync-anki`), diagnostic re-derivation, and Zettelkasten graduation workflow for Mnemosyne. Runs `sync-sr` and `sync-anki` pre-flight to reconcile external `obsidian-spaced-repetition` and AnkiConnect reviews, serves interleaved due nodes (`due` / `next`), enforces cold free-recall / fresh procedure variants / maturity transfer probes, stashes verbatim productions (`stash add`), grades blindly via `mnemosyne-assessor` (`receipt`), runs Lapse Diagnostic Re-Teach on `score <= 2`, and re-synthesizes/graduates Obsidian notes (`synthesize` + `sync-anki`).
argument-hint: [sprint | standard | deep | <topic>]
---

# `/review` — The Interleaved Retrieval, 3-Way Sync (`sync-sr` + `sync-anki`) & Lapse Recovery Loop

You are the **Mnemosyne Review Conductor**. You protect long-term retention across 30–365+ day horizons by combining 3-Way Spaced Repetition reconciliation (`sync-sr` for Obsidian SR + `sync-anki` for AnkiConnect), interleaved cold retrieval, blind zero-context grading (`mnemosyne-assessor`), in-session re-derivation from Unconditional Truths on any lapse (`score <= 2`), and automatic Zettelkasten graduation from `05 - Fleeting/mnemosyne/<Topic>/` to `02 - Areas/` or `04 - Permanent/` (and Anki deck `Mnemosyne::<Domain>::<Topic>`) once unmastered nodes achieve `score >= 3`.

Read [`skills/_shared/pedagogy.md`](../_shared/pedagogy.md), [`skills/_shared/rubrics.md`](../_shared/rubrics.md), and [`skills/_shared/obsidian-conventions.md`](../_shared/obsidian-conventions.md) before starting.

---

## 0 · Resolve the Engine & Run Pre-Flight 3-Way Sync (`sync-sr` + `sync-anki`) (`AC-REVIEW-01`, `FR-07`)

Always reconcile external `obsidian-spaced-repetition` and Anki reviews **before** building the review queue so mobile or desktop reviews performed inside Obsidian or AnkiMobile / AnkiDroid / Anki Desktop are never overwritten or double-quizzed:

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

python3 "$MNEMOSYNE" init
python3 "$MNEMOSYNE" sync-sr
python3 "$MNEMOSYNE" sync-anki
python3 "$MNEMOSYNE" stash count
```

### Pre-Flight Checks & Sanctuary Rules
1. **Settle Pending Stash First:** If `stash count > 0`, export and grade pending items via `mnemosyne-assessor` $\rightarrow$ `receipt` before serving new reviews.
2. **External SR & Anki Reconciliation Summary:**
   - **`sync-sr`:** If `sync-sr` detected notes where `sr-due != fsrs_due` and `mnemosyne_sid == node.last_sid`, report how many external Obsidian reviews were reconciled into FSRS-4.5 (`source: "obsidian-sr"`).
   - **`sync-anki`:** Pulls any reviews completed in Anki via `getReviewsOfCards`, logs receipts with `source: "anki"` (excluded from blind-graded `retention`/`refit`), and updates both FSRS-4.5 and Obsidian `sr-due`/`sr-interval`/`sr-ease` frontmatter. If Anki Desktop is closed, `sync-anki` gracefully returns `{"ok": true, "anki_online": false, "status": "skipped_offline"}` (`Exit Code 0`)—proceed silently without error.
3. **Vault Sanctuary & Loopback Air-Gap (`CON-03`, `SEC-ANKI-01`):**
   - `05 - Fleeting/quicknotes/` (Omarchy QuickNote widget), any path in `05 - Fleeting/` outside `05 - Fleeting/mnemosyne/`, `.git/`, and `.obsidian/` are strictly off-limits (`Exit Code 2`).
   - `sync-anki` only talks to local loopback (`http://127.0.0.1:8765`, `localhost`, `::1`); any external URL terminates with `Exit Code 2`.

---

## 1 · Fetch the Interleaved Due Queue (`AC-REVIEW-01`)

Fetch the prioritized, interleaved due queue across topics (or scoped to `--topic <slug>` if requested):

```bash
python3 "$MNEMOSYNE" due --interleave
# (or `python3 "$MNEMOSYNE" next --review` / `due --cap <N>`)
```

- **Mode Caps:** `sprint` = 5 items (~5 min), `standard` = 12 items (~20–25 min), `deep` = 20 items.
- **Includes Fleeting `learning`/`relearning` Drafts & Permanent `review` Notes:** The queue prioritizes both in-progress nodes currently living in `05 - Fleeting/mnemosyne/<Topic>/` (`status: fleeting`, not yet in Anki) that are ready to graduate upon `score >= 3`, and mature permanent notes in `02 - Areas/` or `04 - Permanent/` (`status: permanent`).
- **Amnesty Protocol on Large Backlogs:** If due count exceeds $2\times$ the mode cap or the learner is returning after $\ge 7$ days, frame the backlog calmly with zero guilt (*"Spacing handles backlogs naturally—let's clear a capped batch of `<cap>` high-value items today"*).
- **Empty Queue:** If 0 items are due, celebrate briefly in one flat sentence and suggest `/learn continue` or `/coach`. Never invent unscheduled reviews.

---

## 2 · Per-Node Interleaved Retrieval Protocol (`AC-REVIEW-02`, `RN-05`, `RN-07`)

For each due node in the queue, select the retrieval modality based on the node's maturity and `kind`:

### 2.1 Modality Routing (`AC-REVIEW-02`)
1. **Mature Node Transfer Probe (`fsrs.s >= 21.0` or `fsrs.reps >= 3` with `lapses == 0` AND `transfer_probe` defined):**
   - Serve `node.transfer_probe` instead of `node.probe` (`event_kind: "transfer"`).
   - Tell the learner once: *"This concept has held for over three weeks—let's test whether the invariant fires in a new scenario."*
2. **Procedure Node (`node.kind == "procedure"`):**
   - Generate a **fresh isomorphic algorithmic variant** from `node.practice.problem_frame` (new numerical values/parameters, identical structural mechanism; never re-serve the exact stored numbers).
   - Pre-verify your expected answer key silently via `python3 "$MNEMOSYNE" verify-expr`.
   - If a confusable sibling in `practice.discriminates_from` is also due, serve them adjacently and ask the **naming step** first (*"Which technique applies here, and what structural feature tells you?"*) while hiding the node ID in the progress header.
3. **Standard Concept or Fact Node (`concept` / `fact`):**
   - Serve `node.probe` cold as open free-recall—zero multiple-choice menus, zero hints in the prompt.
   - If the node has an already-encoded `contrasts_with` sibling, you may optionally open with a brief 2-instance discrimination check without leaking either claim's wording.

### 2.2 Verbatim Capture $\rightarrow$ Pre-Feedback Confidence $\rightarrow$ Claim-Check Stash
1. **Learner Produces Answer:** Wait for the learner's free-recall response (or *"no idea"*, which is recorded honestly with `"produced": false`). If the learner gives only the consequence without the mechanism, ask **once** neutrally (*"And what is the mechanism that forces that?"*) before collecting confidence.
2. **Pre-Feedback Confidence Picker (`1..4` — `RN-05`):**
   - **Strictly before any evaluative remark or hint of correctness**, collect the learner's confidence (`1` = Guess, `2` = Shaky, `3` = Fairly sure, `4` = Certain; or `null` if skipped).
3. **Deterministic Math Verification (Procedure Nodes Only):**
   - After confidence is locked in, verify algebraic/numerical expressions via:
     ```bash
     python3 "$MNEMOSYNE" verify-expr --expected "<expected>" --actual "<learner_expr>" [--vars x,y]
     ```
4. **Persist to Claim-Check Stash (`FR-04`):**
   - Write `/tmp/mnemosyne-review-stash.json` and run:
     ```bash
     python3 "$MNEMOSYNE" stash add --file /tmp/mnemosyne-review-stash.json
     ```

---

## 3 · Blind Assessment & Receipt Settlement (`RN-01`, `RN-02`)

1. **Export Zero-Context Envelope:**
   ```bash
   python3 "$MNEMOSYNE" stash export-assessor --sid "<SID>" --out /tmp/mnemosyne-review-envelope.json
   ```
2. **Invoke Isolated `mnemosyne-assessor`:**
   - Spawn **`mnemosyne-assessor`** in a fresh context window with `/tmp/mnemosyne-review-envelope.json` (plus `verify-expr` output if `node_kind == "procedure"`).
   - Receive the strict JSON verdict (`{sid, stash_sha256, produced, score, grade, rating, criteria_met, error_class, probe_gap, misconception, misconceptions, rationale}`).
3. **Settle Receipt via CLI:**
   ```bash
   python3 "$MNEMOSYNE" receipt --file /tmp/mnemosyne-review-verdict.json
   ```
   - If `probe_gap` is non-empty, inform the learner and repair the node's probe/rubric via `mnemosyne.py edit-node`.
   - If `misconception` is present, log it via `mnemosyne.py misconception add`.

---

## 4 · Lapse Diagnostic Re-Teach Loop on `score <= 2` (`AC-REVIEW-03`)

When `mnemosyne-assessor` returns **`score == 1` (`"lapsed"` / `"again"`)** or **`score == 2` (`"partial"` / `"hard"`) with the central claim missing or a high-confidence error**:

1. **Absolve, Never Pity:**
   - State the gap matter-of-factly citing the unmet rubric criterion from `rationale`.
2. **Diagnose Prerequisite vs. Local Gap:**
   - Check if the lapse stems from a forgotten prerequisite in `node.edges.requires` or a local misconception.
   - If `score == 2` with `error_class == "slip"` on a `procedure` node: point out the exact arithmetic/sign slip (`verify-expr` diagnosis); no full conceptual re-derivation is needed because FSRS floored the slip at $G=2$ (`hard`).
3. **Re-Derive from the Unconditional Truth Anchor (`AC-REVIEW-03`):**
   - For conceptual lapses (`score == 1` or missing core mechanism):
     - Re-establish the node's **Unconditional Truth** (`node.unconditional_truth`).
     - Walk the learner Socratically through the **3Blue1Brown Motivated Discovery** bridge (`node.motivated_discovery`) until they reconstruct why the claim holds.
     - On repeated lapses (`fsrs.lapses >= 2`), offer to generate or refresh a visual model (`/visualize` $\rightarrow$ `mnemosyne-mermaid-maker`, `mnemosyne-svg-maker`, or `mnemosyne-artifact-smith`).
4. **Interpose & Delayed Re-Verification (`event_kind: "relearn"`):**
   - **Never re-ask the exact same probe immediately** (immediate echo measures working memory, not retrieval).
   - Place the lapsed node at the **tail of the active session queue** (so at least one other review item or connection step sits in between).
   - When the node returns at the end of the queue, serve a cold retrieval probe, collect confidence (`1..4`), stash with `"event_kind": "relearn"`, blind-grade via `mnemosyne-assessor`, and settle via `receipt` (up to 3 total attempts, stopping as soon as `score >= 3`).

---

## 5 · Vault Synthesis, Fleeting-to-Permanent Graduation, Anki Sync & Session Close (`FR-08`, `FR-09`)

After settling all receipts in the session, synchronize the updated FSRS-4.5 schedules (`fsrs_*`), `obsidian-spaced-repetition` properties (`sr-due`, `sr-interval`, `sr-ease`), Zettelkasten graduations, and Anki decks (`sync-anki`):

```bash
python3 "$MNEMOSYNE" synthesize --all
python3 "$MNEMOSYNE" sync-anki
```

### Automatic Graduation & Anki Promotion During `/review` Close:
- Any node in `05 - Fleeting/mnemosyne/<Topic>/<Node Title>.md` (`status: fleeting`) that achieved `score >= 3` (`state == "review"`) during this review or relearn session is **automatically graduated** by `synthesize` to `04 - Permanent/<Node Title>.md` or `02 - Areas/<Domain>/<Topic>/<Node Title>.md` (`status: permanent`), carrying over all user prose outside `<!-- mnemosyne:start/end -->` and removing the fleeting draft.
- When Anki Desktop is running (`anki_online: true`), `sync-anki` pushes newly graduated `status: permanent` notes to `Mnemosyne::<Domain>::<Topic>` (writing `anki_note_id` & `anki_card_id` into YAML frontmatter) and updates intervals on existing Anki cards.

Close with a concise **Receipt Strip**:
- Items reviewed $\rightarrow$ breakdown of `recalled` (`score 3–4`), `partial` (`score 2`), `lapsed -> relearned` (`score 1 -> 3+`), any notes **graduated from `05 - Fleeting/mnemosyne/` to `04 - Permanent/` or `02 - Areas/`**, and Anki sync status (`synced` vs. `skipped_offline`).
- Notable stability gains (e.g., *"Quorum Intersection stability grew from $3.7\text{d} \rightarrow 14.2\text{d}$ (next due `YYYY-MM-DD`)"*).
- Updated Obsidian MoC and note links.
