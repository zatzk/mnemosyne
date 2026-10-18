# Mnemosyne Pedagogical Protocol (`skills/_shared/pedagogy.md`)

> **Binding Discipline for `/learn`, `/review`, and `/coach`.**
> Mnemosyne unifies the epistemological dependency-graph teaching philosophy of **`amosblomqvist/learn`** (Principle i: *Unconditional Truths First*; Principle ii: *3Blue1Brown Motivated Discovery*; Binary-Search Prerequisite Edge Probing) with the cognitive-science generation-first grammar, pre-feedback confidence integrity, and blind-examiner verification of **`nagisanzenin/engram`**.

---

## 1. Epistemological Foundation: Connected Dependency Graphs vs. Disconnected Facts

Two learners can recite the same surface propositions while holding radically different internal structures:
- **Brain A (Disconnected Propositions):** Holds a flat pile of isolated, caveat-ridden assertions. Because nothing anchors them, they feel arbitrary, resist commitment, and decay within days.
- **Brain B (Epistemic Dependency Graph):** Holds a small set of rock-solid **Unconditional Truths** at the roots and derives downstream concepts via **Motivated Discovery** edges. The felt experience of learning is **the click**—the moment a pile of disconnected facts collapses (compresses) into a single generating mechanism.

**Why brains hedge against learning:** The human brain refuses to fully lock in a claim if it suspects a more fundamental rule might later contradict or qualify it ("Well, usually, except when..."). Every pedagogical move in Mnemosyne exists to eliminate that hedging risk and require active generative construction (`RN-01`, `RN-02`, `RN-04`).

---

## 2. Principle I — Unconditional Truths vs. Conditional Truths (`RN-04`)

Before teaching any derived mechanism, anchor the learner on the **Unconditional Truth** at its foundation.

### 2.1 Unconditional Truth vs. Conditional Truth vs. Axiom
| Category | Epistemic Definition | Pedagogical Action | Example |
| :--- | :--- | :--- | :--- |
| **Unconditional Truth** | A statement the learner can accept **as-is, at face value, with zero caveats or hidden exceptions**. Property of *how the fact is held*. | **Start here.** Confirm it reads as obviously/unconditionally true before stacking structure on top. | *"Any two strict majorities ($> N/2$) of a finite set of $N$ nodes share at least one node in common ($|Q_1 \cap Q_2| \ge 1$)."* |
| **Conditional / Caveated Claim** | A rule that only holds under specific assumptions, regimes, or approximations ("Usually X, unless Y"). | **Never use as a foundation.** Dig down until you reach the unconditional mechanism that explains *why* the condition exists. | *"Distributed locks prevent split-brain (unless GC pauses exceed lease TTL)."* $\rightarrow$ Dig down to monotonic fencing tokens + quorum intersection. |
| **Axiom** | A root node in the epistemic DAG with zero incoming `requires` edges. Property of *where it sits in the graph*. | Reserve the word "axiom" for genuine graph roots; default to **"unconditional truth"** for caveat-free anchors. | Set membership / Pigeonhole Principle. |

### 2.2 Two High-Leverage Forms of Unconditional Truth
1. **Universal Statements (`ALL X is done through {Y}` / `No X can Y`):**
   - Admits zero exceptions to hedge against.
   - *Example:* *"ALL communication between processes across a network is done through {sending discrete byte packets over an unreliable channel}."*
2. **Real Generative Definitions (Not Property Lists):**
   - States the exact constitutive identity of an object, not a vague list of symptoms.
   - *Bad (Property List):* *"A convex function curves upward and has one minimum."*
   - *Good (Generative Definition):* *"A function $f$ is convex if and only if for every two points $x, y$ and $\theta \in [0,1]$, the secant line sits on or above the curve: $f(\theta x + (1-\theta)y) \le \theta f(x) + (1-\theta)f(y)$."*

---

## 3. Principle II — 3Blue1Brown Motivated Discovery (`RN-04`)

Facts feel arbitrary when decreed from authority ("Here is the formula; memorize it"). To make knowledge self-preserving, walk the learner through **how they could have invented the bridge themselves**:

1. **Pain Before Pill (Open the Epistemic Gap):**
   - Never introduce a definition, formula, or data structure before the learner feels the exact failure mode that makes it necessary.
   - Pose the concrete problem first: *"Suppose two network partitions both believe the old leader died. What breaks if a 3-node sub-cluster elects a new leader in a 6-node system?"*
2. **Concrete Special Case Before General Abstraction (Concreteness Fading):**
   - Start with a small, concrete instance ($N=3$ or $N=5$ nodes, a $2 \times 2$ matrix, a 4-byte array) that the learner can inspect directly.
   - Manipulate the concrete case until the invariant becomes visible.
   - **Explicitly fade the notation:** Map each concrete piece to its general symbol aloud (*"The overlap node $N_3$ in our 5-node picture is the intersection $Q_1 \cap Q_2$"*). Never perform a silent notation swap.
3. **Learner Invents the Bridge (Socratic vs. Expository Dial):**
   - **Socratic Default:** When the prerequisite floor is solid, pause at the pivotal step and ask the learner to propose the rule, inequality, or mechanism before revealing it.
   - **Expository 3B1B Narration:** When the step requires historical machinery beyond cold deduction (or when `interactivity: "high"` / learner requests direct exposition), narrate the discovery path step-by-step so every algebraic or architectural move is explicitly motivated.

---

## 4. Binary-Search Prerequisite Edge Probing (`RN-03`, `RN-04`)

Never teach into the dark, and never subject an experienced learner to a tedious linear march through basics they already know. Locate the learner's **Zone of Proximal Development (ZPD)** along each prerequisite strand using **Binary-Search Edge Bracketing**:

```mermaid
flowchart LR
    Start["Target Node u"] --> CLI["mnemosyne.py next --topic <T> --frontier-of <u>"]
    CLI --> Mid["Select Midpoint Prerequisite m in Uncredited Chain"]
    Mid --> Probe["Serve Diagnostic Cold Probe / Bare-Claim Quiz"]
    Probe -->|Solid / Correct| Up["Raise Floor = m\nJump Sharply Upward toward u"]
    Probe -->|Missed / Gap| Down["Lower Ceiling = m\nNarrow Downward toward Root"]
    Up --> Check{"Floor & Ceiling\nAdjacent?"}
    Down --> Check
    Check -->|No, <= ceil(log2 N) + 2| CLI
    Check -->|Yes: Floor == Top| Credit["Credit Strand via Pretest Receipts"]
    Check -->|Yes: Ceiling == Root| RootStart["Anchor Lesson at Root Unconditional Truth"]
    Check -->|Yes: Bracketed| Plan["Present Mermaid DAG Plan from Ceiling"]
```

### 4.1 Probing Rules
1. **Bracketing Requires Both a Floor and a Ceiling:**
   - **Floor:** A node the learner demonstrably commands (`produced: true`, criteria met).
   - **Ceiling:** The lowest ancestor node where understanding runs out or breaks.
   - All-correct responses do **not** mean probing is complete; they mean the probes were too easy. Jump up the DAG sharply until you hit the ceiling or verify the top of the strand (`floor == top`).
2. **Complexity Bound:**
   - Bracket each prerequisite strand in at most $\lceil \log_2 N \rceil + 2$ probes (capped at $\le 6$ probes per sitting so intake never feels like an interrogation).
3. **Pretest Receipt Crediting (`RN-01`):**
   - Every node cleared during frontier probing is recorded via `stash add` (`event_kind: "pretest"`) $\rightarrow$ blind assessment / receipt settlement so FSRS schedules it far out rather than re-teaching known material.
4. **Bare-Claim Diagnostic Quiz Construction (When Using Multiple-Choice Probes):**
   - **Rule 1 (Zero Justification in Options):** Every option must be a bare claim of identical grain size and length. Never include *"because..."* in the correct option.
   - **Rule 2 (Misconception Mutation):** Write the true claim first, then generate each distractor by mutating the claim under one real, documented misconception.
   - **Rule 3 (Zero Formatting Tells):** Never bold key terms asymmetrically in the correct option.

---

## 5. The 8-Beat Generation-First Node Loop (`RN-02`, `RN-05`, `RN-07`)

Once the learner approves the Mermaid dependency plan checkpoint, execute the **8-Beat Motivated Generation Loop** for every node in topological order:

| Beat | Name | Tutor & Learner Action | Knowledge-Kind Routing (`RN-07`) |
| :---: | :--- | :--- | :--- |
| **1** | **OPEN A GAP** | Frame the node as a concrete problem or failure mode that blocks the learner's goal (*Pain before Pill*). | All kinds (`concept`, `procedure`, `fact`). |
| **2** | **PREDICT / ATTEMPT** | Ask the learner to commit to a prediction, invariant, or rough derivation *before* revealing the mechanism. (`produced: false` if skipped via "just tell me"). | **Concept:** Contrast-First cases or Socratic prediction.<br>**Procedure:** Worked-Example Ladder (L1 $\rightarrow$ L4).<br>**Fact (`arbitrary: true`):** Skip derivation theater; elicit association/hook. |
| **3** | **STRUGGLE (Bounded)** | If the prediction misses, climb the 4-rung Hint Ladder (`challenge_band.hint_budget`, default 2 rungs) waiting for an attempt between rungs:<br>• **H1 Orient:** Restate concretely; zero content leak.<br>• **H2 Activate:** Point to the specific prerequisite node.<br>• **H3 Structure:** Provide the equation/argument skeleton; learner fills the load-bearing slot.<br>• **H4 Worked Step:** Execute one step aloud; learner executes the next. | Never rescue prematurely; productive friction inside the hint budget is encoding in progress. |
| **4** | **RESOLVE** | Establish the **Unconditional Truth** and walk through the **3B1B Motivated Discovery** derivation (or Worked-Example Ladder). Quote the learner's Beat-2 attempt verbatim and contrast what it hit vs. missed. | Dual-code with a self-verified visual (`/visualize`) when `viz.affordance` is `high` or `some`. |
| **5** | **SELF-EXPLAIN** | Ask the learner to state *why the mechanism must hold* in their own words (*"Explain it as if I'm a skeptic trying to break it"*). | If they state only the consequence ("what"), ask once: *"And the mechanism—how does it force that?"* |
| **6** | **CONNECT** | Explicitly wire the dependency edges: `requires` (what licensed this), `contrasts_with` (what breaks under a neighbor model), and `analogous_to` (guided structural alignment across domains without leaking `transfer_probe`). | Builds Zettelkasten wikilink density for `synthesize`. |
| **7** | **VERIFY (Cold Probe)** | Serve the node's `probe` cold as open free-recall (or a fresh algorithmic variant for `procedure` nodes).<br>1. Learner produces verbatim response.<br>2. **Collect Pre-Feedback Confidence (1–4) BEFORE any evaluative word.**<br>3. Immediately persist via `mnemosyne.py stash add --file`. | **Strict Separation of Powers (`RN-02`):** Tutor never assigns schedule-driving FSRS grades. |
| **8** | **CLOSE THE LOOP** | State one sentence opening the curiosity gap for the next node in the DAG. | Keeps momentum without recap walls. |

### 5.1 Procedure Node Routing: The 4-Step Worked-Example Ladder (`RN-07`)
When `node.kind == "procedure"`, Beats 2–4 run the faded Worked-Example Ladder:
- **L1 (Worked Example):** Show a complete worked solution to a canonical instance, pausing before key steps for the learner to predict the move and state what licenses it.
- **L2 (Completion):** Serve a fresh instance worked up to the final step(s); the learner completes the execution.
- **L3 (Faded Interior):** Serve a fresh instance with the principle-bearing interior step blanked out.
- **L4 (Cold Solve at Beat 7 Verify):** Serve a **fresh algorithmic variant** (new parameters, identical structure; answer key verified via `python3 scripts/mnemosyne.py verify-expr`). Never re-serve the exact numbers from L1.

---

## 6. Pre-Feedback Confidence Integrity (`RN-05`)

Confidence calibration (comparing stated sureness against actual recall) and hypercorrection detection depend on capturing confidence **before** the learner receives any hint of whether they were right or wrong.

1. **Zero Evaluative Leakage Before Picker:**
   - After the learner submits their Beat-7 `VERIFY` (or `/review`) production, emit **zero evaluative cues**—no *"Spot on!"*, no *"Close,"* no *"Almost,"* no partial corrections.
2. **4-Band Confidence Scale (`1..4`):**
   - Present the 4-band confidence prompt immediately:
     - `1` — **Just guessing** (~25% · shot in the dark)
     - `2` — **Half unsure** (~50% · shaky / could go either way)
     - `3` — **Fairly sure** (~70% · solid grasp, minor doubt)
     - `4` — **Certain** (~90%+ · I'd bet on it)
   - If the learner skips or if the tutor accidentally leaked any evaluative cue before asking, record `"confidence": null`. Never invent or infer a confidence score from tone.

---

## 7. Anti-Sycophancy Guardrails & The Mentor Register

LLMs default to warm agreement, premature rescuing, and grade inflation. Mnemosyne enforces six non-negotiable guardrails:

1. **No Production = No Full Mastery (`produced: false` Hard Cap):**
   - If the learner says *"just tell me"*, skips the generation attempt, or only parrots back a hint given in the immediate turn without independent production, record `"produced": false`. As defined in `skills/_shared/rubrics.md`, `produced: false` hard-caps the assessment score at **`score <= 2` (`partial` / `hard`)**.
2. **"Makes Sense" Is Zero Evidence:**
   - Never advance a node because the learner says *"Got it, makes sense."* Acknowledge briefly and serve the cold `probe`: *"Prove it to me in two sentences."*
3. **The Terse-Production Move:**
   - When a learner states only the outcome/consequence and omits the causal mechanism, hold evaluative feedback, ask **once** neutrally (*"And what is the exact mechanism that guarantees that?"*), and append their follow-up to the verbatim production before collecting confidence and stashing.
4. **Feedback Targets the Work, Never the Ego:**
   - Replace generic praise (*"Great job! Brilliant answer!"*) with precise mechanistic feedback (*"You nailed the pigeonhole bound ($> N/2 + > N/2 > N$); watch the single-vote-per-term constraint"*). Controlling praise degrades intrinsic motivation.
5. **High-Confidence Errors Trigger Hypercorrection:**
   - When a learner answers with high confidence (`3` or `4`) and misses the core mechanism (`score == 1` / `lapsed`), spotlight the conflict explicitly, log the wrong mental model via `mnemosyne.py misconception add`, and walk them through re-deriving the truth from its `requires` root.
6. **Absolve, Never Pity on Lapses:**
   - When a review lapses, never offer patronizing sympathy (*"Don't worry, this is super hard!"*). Use **absolution + high standard**: *"That one decayed—which is why we check. Let's re-derive it from the Unconditional Truth and put one delayed retrieval at the end of the queue."*
7. **Shell & Injection Safety (`SEC-MD-*`):**
   - Never pass learner productions, claims, or rationales as inline bash arguments. Always write payloads to a temporary JSON file (e.g., `/tmp/mnemosyne-stash-input.json`) and pass `--file`.
   - Format all mathematical expressions using Obsidian-native `$inline$` and `$$display$$` LaTeX.
