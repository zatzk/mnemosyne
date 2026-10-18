# Mnemosyne Explorable HTML & Visual Contract (`skills/_shared/explorable-contract.md`)

> Canonical companion to [`skills/_shared/visual-routing.md`](./visual-routing.md).
> Defines the 7-Clause Explorable HTML Contract, strict offline Content-Security-Policy (`ASR-03`, `NFR-02`), Mayer's multimedia principles, and 3-iteration visual verification (`RN-08`).

See [`skills/_shared/visual-routing.md`](./visual-routing.md) for the complete specification:
1. **Strict Offline CSP Header:**
   ```html
   <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none';">
   ```
2. **The 7 Binding Clauses:**
   - **Clause 1 (Prediction Gate):** Reader must commit to a prediction before unlocking the simulation.
   - **Clause 2 (Guided Manipulable Model):** `Predict -> Act -> Explain` micro-cycle; worked drive first for novice scaffold.
   - **Clause 3 (Embedded Retrieval):** $\ge 2$ inline free-recall prompts with hidden reveal checks.
   - **Clause 4 (Mayer-Minimal Coherence):** Zero decorative clutter; text never runs concurrently over motion.
   - **Clause 5 (Self-Contained Dual-Theme):** 100% offline (`file://`), light/dark CSS custom properties, $< 120\text{ KB}$.
   - **Clause 6 (Blank-Page Ending):** Final reconstruction prompt from memory.
   - **Clause 7 (Versioned & Registered):** Written to `/tmp/viz-output.html` and registered via `python3 scripts/mnemosyne.py artifact set --topic <T> --node <N> --file /tmp/viz-output.html` into `99 - Meta/attachments/`.
