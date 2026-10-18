# Mnemosyne Dialogue Grammar (`skills/_shared/dialogue-grammar.md`)

> Canonical companion to [`skills/_shared/pedagogy.md`](./pedagogy.md).
> Defines the 8-Beat Motivated Generation Grammar, Unconditional Truth anchoring (`RN-04`), Binary-Search Prerequisite Frontier Probing (`RN-03`), Pre-Feedback Confidence Integrity (`RN-05`), and the Anti-Sycophancy Oath (`RN-02`).

See [`skills/_shared/pedagogy.md`](./pedagogy.md) for the complete specification:
1. **Principle I — Unconditional Truths First (`RN-04`):** Caveat-free universal statements (`ALL X is done through {Y}`) and real generative definitions anchored before any derived structure.
2. **Principle II — 3Blue1Brown Motivated Discovery (`RN-04`):** Pain before pill, concrete special case before general abstraction, explicit concreteness fading, and learner-invented bridges.
3. **Binary-Search Prerequisite Frontier Probing (`RN-03`):** Bracket every prerequisite strand with a verified **floor** and **ceiling** in $\le \lceil \log_2 N \rceil + 2$ probes via `mnemosyne.py next --topic <T> --frontier-of <N>`.
4. **The 8-Beat Node Encoding Loop:**
   - **Beat 1:** Open a Gap (Pain before Pill)
   - **Beat 2:** Predict / Attempt (Contrast-First for concepts; Worked-Example Ladder L1–L4 for procedures)
   - **Beat 3:** Struggle within `hint_budget` (H1 Orient $\rightarrow$ H2 Activate $\rightarrow$ H3 Structure $\rightarrow$ H4 Worked Step)
   - **Beat 4:** Resolve from Learner's Attempt + Establish Unconditional Truth
   - **Beat 5:** Self-Explain the Mechanism
   - **Beat 6:** Connect (`requires`, `contrasts_with`, `analogous_to`)
   - **Beat 7:** Verify (Cold Probe $\rightarrow$ 4-Band Pre-Feedback Confidence Picker `1..4` $\rightarrow$ `mnemosyne.py stash add --file`)
   - **Beat 8:** Close the Loop (Curiosity hook for next node)
5. **In-Session Lapse Re-Derivation (`AC-REVIEW-03`):** Any node graded `lapsed` (`score == 1`, `rating: "again"`) or missing its central claim is re-derived from its Unconditional Truth anchor and re-queued with at least one intervening item before session close.
