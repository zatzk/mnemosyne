# Mnemosyne Assessment Rubrics & Blind Grading Contract (`skills/_shared/rubrics.md`)

> **Binding Grading Contract for `mnemosyne-assessor`, `mnemosyne-curriculum-architect`, `/learn`, and `/review`.**
> Enforces `RN-01` (Receipts or It Didn't Happen), `RN-02` (Strict Separation of Powers), `RN-06` (Probe-Rubric Co-Authoring & `probe_gap`), `RN-07` (Knowledge-Kind Routing), and `NFR-05` (Zero Upward Grade Inflation Ceiling).

---

## 1. Separation of Powers & Zero-Context Blindness (`RN-02`, `ASR-02`)

1. **The Tutor Never Grades for the Schedule:**
   - The conversational tutor (`/learn`, `/review`) helps the learner struggle and derive, which inherently biases it toward rooting for the learner. Therefore, the tutor is strictly forbidden from assigning FSRS-driving grades.
2. **Cryptographic Claim-Check Stash (`stash.jsonl` $\rightarrow$ `export-assessor`):**
   - Every verbatim learner production is immediately persisted via `python3 scripts/mnemosyne.py stash add --file <path>`, which mints a unique transaction ID (`sid`) and computes:
     $$\text{stash\_sha256} = \text{SHA256}\left(\text{UTF8}\left(\text{json.dumps}(\{\text{"claim"}: c, \text{"probe"}: p, \text{"production"}: \text{prod}, \text{"rubric"}: r\}, \text{sort\_keys}=\text{True}, \text{separators}=(\text{","}, \text{":"}), \text{ensure\_ascii}=\text{False})\right)\right)$$
   - `python3 scripts/mnemosyne.py stash export-assessor --sid <SID>` strips all conversational history, FSRS state, stability numbers, and tutor comments, emitting **only** the zero-context assessment envelope.
3. **Skeptic-First Stance (`NFR-05`):**
   - The Blind Assessor evaluates **only** what is explicitly written in `production` against `rubric`.
   - Before crediting any criterion, list what is **missing, vague, or mechanistically wrong**.
   - When torn between two scores, **always round down**. An inflated grade corrupts the FSRS-4.5 stability curve and schedules a false sense of mastery.

---

## 2. The 1–4 FSRS Grading Scale & Bijective Score Mapping

Mnemosyne unifies the numerical FSRS-4.5 rating $G \in \{1, 2, 3, 4\}$ (`score`) with semantic grades (`grade` and `rating`):

| `score` ($G$) | `rating` | `grade` | Core Criteria & Retrieval Standard | FSRS-4.5 Impact |
| :---: | :---: | :---: | :--- | :--- |
| **`1`** | `"again"` | `"lapsed"` | **Core Absent or Mechanistically Wrong:**<br>• Zero rubric criteria met, OR<br>• The central defining mechanism/claim of the node is wrong or missing (even if peripheral scaffolding criteria were met), OR<br>• Empty / *"I don't know"* production, OR<br>• Wrong method yielding a wrong answer on a `procedure` node. | Stability resets via lapse equation $S_f$; `lapses += 1`; sets `relearn_step` dose caps; triggers in-session re-derivation. |
| **`2`** | `"hard"` | `"partial"` | **Core Present, Incomplete Criteria, Execution Slip, or `produced: false` Cap:**<br>• Central mechanism is present and sound, but $\ge 1$ secondary rubric criterion is missing or imprecise, OR<br>• `procedure` node has the right method/setup with a pure arithmetic/transcription `"slip"`, OR<br>• Learner required heavy scaffolding (`hint_used >= 2`) or had **`produced: false`** (hard ceiling at `score <= 2`). | Stability grows with `hard_penalty` ($W[15]$); difficulty $D$ increases. |
| **`3`** | `"good"` | `"recalled"` | **Complete & Accurate Recall (`produced: true` Required):**<br>• **All** rubric criteria are explicitly satisfied (by meaning/mechanism, not rote keyword matching), AND<br>• `produced: true` (independent generation without answer leakage), AND<br>• Effortful recall or pre-feedback `confidence <= 3` (or `null`). | Standard FSRS-4.5 exponential stability growth ($S_{\text{next}}$); difficulty mean-reverts toward $D_0(3)$. |
| **`4`** | `"easy"` | `"recalled"` | **Effortless, Precise & High-Confidence Mastery (`produced: true` Required):**<br>• **All** rubric criteria are met with zero ambiguity, complete mechanistic precision, zero hints (`hint_used == 0`), AND<br>• `produced: true`, AND<br>• Pre-feedback `confidence == 4` (or `>= 70` on 100-point scale). | Stability grows with `easy_bonus` ($W[16]$); difficulty $D$ decreases. |

---

## 3. Non-Negotiable Ceiling & Floor Invariants

### 3.1 The `produced: false` Hard Cap (`score <= 2`)
> **INVARIANT (`RN-02`):** If the learner did not independently produce the answer before seeing/hearing the resolution (`produced: false`, e.g., autonomy override *"just tell me"*, tutor leaked the answer before capture, or learner merely echoed a worked step), the score is **strictly capped at `score <= 2` (`rating: "hard"`, `grade: "partial"`)**.
- If `produced: false` and the learner's post-reveal restatement captures the core mechanism $\rightarrow$ `score: 2` (`"hard"` / `"partial"`).
- If `produced: false` and the learner still fails or omits the core mechanism $\rightarrow$ `score: 1` (`"again"` / `"lapsed"`).
- **Never** award `score: 3` or `score: 4` when `produced: false`.

### 3.2 "Cap at X" Is a Ceiling, Never a Floor
- A cap rule (such as *"cap at `2` (`partial`) when `produced: false`"* or *"cap at `2` (`partial`) when the `why` is omitted"*) means **no higher than `2`**.
- **Zero rubric criteria met is ALWAYS `score: 1` (`"lapsed"` / `"again"`).** A ceiling rule can never lift a zero-criteria or wrong-core production up to `2`.

### 3.3 Counting Peripheral Criteria Never Overrides a Wrong Core
- If a rubric has 3 criteria—e.g., `[1] defines setup variables, [2] applies the core invariant/sign, [3] simplifies result`—and the learner satisfies `[1]` but gets `[2]` (the central claim of the node) backward, the grade is **`score: 1` (`"lapsed"` / `"again"`)**. Scaffolding never buys partial credit when the core claim fails.

---

## 4. Rubric Matrix by `node_kind` $\times$ `event_kind`

### 4.1 By Node Kind (`concept`, `procedure`, `fact`)

| `node_kind` | Rubric Structure (2–4 Criteria) | Grading Rules & Error Classification (`error_class`) |
| :--- | :--- | :--- |
| **`concept`** | 1. **Core Mechanism / Invariant:** What holds and why.<br>2. **Causal / Epistemic Link:** How it derives from `requires` or prevents the motivating failure mode.<br>3. **Boundary / Precision:** Necessary condition or distinction from confusable neighbor. | • Paraphrase that preserves the exact causal mechanism counts as met.<br>• Stating *only* the consequence ("what") when the rubric requires the derivation ("why") caps at `score: 2` (`partial`) if the core claim is right, or `score: 1` (`lapsed`) if zero criteria are met.<br>• `error_class` must be `null` (or omitted). |
| **`procedure`** | **Step-Shaped Exam Rubric:**<br>1. `setup`: Identifies state/inputs and applicable preconditions.<br>2. `method`: Selects and states the governing transformation/algorithm.<br>3. `execution`: Applies steps to the fresh instance.<br>4. `verification`: Arrives at the verified result / checks boundary. | • **Verify by Deterministic Execution:** Always run `python3 scripts/mnemosyne.py verify-expr --expected "<E>" --actual "<A>"` for mathematical/algebraic procedures before judging steps.<br>• **`error_class: "slip"`:** Correct setup and method, single arithmetic/sign/transcription slip $\rightarrow$ **`score: 2` (`"hard"` / `"partial"`)**. FSRS engine floors `slip` at $G=2$ so execution slips do not wipe out concept stability.<br>• **`error_class: "conceptual"`:** Wrong method or broken invariant $\rightarrow$ **`score: 1` (`"again"` / `"lapsed"`)** (or at best `score: 2` if final answer is right *and* $\ge 1$ core criterion was genuinely met).<br>• When torn between `slip` and `conceptual`, always choose `"conceptual"`. |
| **`fact`** (`arbitrary: true`) | 1. **Exact Target Fact / Convention / Definition:** Unambiguous recall of the symbol, constant, API contract, or definition.<br>2. **Scope / Disambiguation:** Distinguishes from adjacent terms. | • Graded strictly on factual accuracy without demanding artificial "derivation theater".<br>• Missing or inverted fact $\rightarrow$ `score: 1` (`"lapsed"`). Minor imprecision with core fact intact $\rightarrow$ `score: 2` (`"partial"`). Exact recall $\rightarrow$ `score: 3` or `4`. |

### 4.2 By Event Kind (`learn`/`encode`, `review`, `relearn`, `pretest`, `transfer`)

| `event_kind` (`kind`) | Context & Scheduling Semantics | Assessor Grading Standard |
| :--- | :--- | :--- |
| **`learn` / `encode`** | First-time acquisition after the 8-Beat Motivated Generation loop. | Full rubric enforcement. Checks `produced` flag strictly (`hint_used >= 2` or tutor-told $\rightarrow$ `produced: false` $\rightarrow$ `score <= 2`). |
| **`review`** | Spaced retrieval from `due` queue (cold free-recall or fresh procedure variant). | Cold exam standard. Zero conversational charity. High confidence (`3–4`) + `score: 1` flags a high-priority misconception for hypercorrection. |
| **`relearn`** | In-session delayed retrieval pass after a lapse (`score <= 2`) and re-derivation from Unconditional Truth. | **Identical rubric bar** (`score: 3` or `4` required to clear the in-session relearn criterion). Engine logs the `relearn` receipt and updates post-lapse dose-capped schedule cleanly. |
| **`pretest`** | Cold diagnostic frontier probe during Phase 1 (`Probe`) before any teaching on that strand. | Graded strictly against the rubric. `score >= 3` credits the node as already known; `score <= 2` marks the prerequisite ceiling without penalty shame. |
| **`transfer`** | Far-transfer application probe (`transfer_probe`) served when node is mature (`fsrs.s >= 21.0` or `reps >= 3`) or on a Capstone node. | Evaluates whether the underlying invariant fires in novel clothing. A failed transfer probe (`score == 1`) is recorded honestly in transfer telemetry without demolishing the base concept's memory stability. |

---

## 5. Co-Authoring Probes & Rubrics + The `probe_gap` Indictment (`RN-06`)

### 5.1 The Probe and Rubric Are One Object
Because `score >= 3` (`recalled`) requires **every** rubric criterion to be met, any rubric criterion that a competent learner would not *necessarily* include when answering `probe` acts as an artificial ceiling that forces false `partial` grades.

**Mandatory 3-Step Self-Check for `mnemosyne-curriculum-architect`:**
1. Read `probe` in complete isolation (ignore `claim` and `motivated_discovery`).
2. Write the concise, complete answer a domain expert would give to *that exact question*.
3. Grade that answer against `rubric`:
   - **Unasked Trailing Criterion Defect:** If `rubric` has a trailing criterion like *"relates this to X"* or *"states the downstream consequence Y"* that `probe` never asked for, either **widen `probe`** to explicitly ask for it or **delete the criterion**.
   - **Stem-Mirroring Defect:** Never write a rubric criterion whose content is already given away in the `probe` stem (enforced deterministically by `mnemosyne.py validate-dag` / `add-topic`).

### 5.2 Emitting `probe_gap` in the Blind Assessor
- Read `probe` alone. If any rubric criterion (1-based index $k \in \{1, \dots, M\}$) would **not necessarily** appear in a fully competent answer to `probe` (or mirrors the stem), include $k$ in `"probe_gap": [k]`.
- **Judge `probe_gap` from `probe` and `rubric` alone—never from `production`.**
- **`probe_gap` NEVER softens or raises the learner's `score`.** Grade `production` strictly against the written `rubric` first, and emit `probe_gap` so the tutor can immediately repair the broken node via `mnemosyne.py edit-node`.

---

## 6. Required JSON Assessment Schemas

### 6.1 Input Envelope (`mnemosyne.py stash export-assessor --sid <SID>`)
```json
{
  "sid": "st-20261018T141205Z-a9f3c1",
  "stash_sha256": "8f4b2c9d1e7a6f5b3c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
  "topic": "consensus-raft",
  "node": "split-brain-impossibility",
  "kind": "encode",
  "event_kind": "encode",
  "node_kind": "concept",
  "claim": "Quorum intersection ensures at most one leader can be elected per term and guarantees read/write overlap across majorities.",
  "probe": "Why does requiring a strict majority (> N/2) of votes prevent two isolated network partitions from simultaneously electing two valid leaders in the same term?",
  "rubric": [
    "States that two disjoint subsets cannot both contain strictly more than N/2 elements (pigeonhole principle / quorum intersection).",
    "Concludes that any two candidate quorums must overlap in at least one node, which can vote for at most one candidate per term."
  ],
  "production": "Because if both partitions needed > N/2 nodes, the sum of nodes would be > N, which is impossible by the pigeonhole principle. So any two majorities share at least one node, and since each node only votes once per term, two leaders cannot both get a majority.",
  "produced": true,
  "production_clipped": false,
  "confidence": 4,
  "hint_used": 0
}
```

### 6.2 Output Receipt Payload (`mnemosyne-assessor` $\rightarrow$ `mnemosyne.py receipt --file`)
`mnemosyne-assessor` MUST output **strict JSON only** (no markdown prose outside JSON, no commentary). To guarantee 100% compatibility across all CLI subcommands and audit harnesses, include both the canonical numeric fields (`produced`, `score`, `misconception`, `rationale`) and the FSRS semantic fields (`grade`, `rating`, `criteria_met`, `error_class`, `probe_gap`, `misconceptions`):

```json
{
  "sid": "st-20261018T141205Z-a9f3c1",
  "stash_sha256": "8f4b2c9d1e7a6f5b3c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
  "topic": "consensus-raft",
  "node": "split-brain-impossibility",
  "kind": "encode",
  "node_kind": "concept",
  "produced": true,
  "score": 4,
  "grade": "recalled",
  "rating": "easy",
  "confidence": 4,
  "criteria_met": [true, true],
  "error_class": null,
  "probe_gap": [],
  "misconception": null,
  "misconceptions": [],
  "rationale": "Criterion 1 met: explicitly invokes the pigeonhole bound (>N/2 + >N/2 > N). Criterion 2 met: identifies that the overlapping node votes at most once per term, preventing dual leaders."
}
```

> **Batch Mode Note:** When grading a JSON array `[{"sid": ...}, ...]` (e.g., multi-item session settle or `assessor-audit`), return a JSON array of the exact object schema above, preserving every `sid` and `stash_sha256` verbatim.
