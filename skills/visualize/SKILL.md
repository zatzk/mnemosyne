---
name: visualize
description: Tri-modal visual director workflow for Mnemosyne. Evaluates content affordance, distills a minimal visual brief (<= 5-7 elements), dispatches context-isolated visual subagents (`mnemosyne-mermaid-maker`, `mnemosyne-svg-maker`, or `mnemosyne-artifact-smith`) with a 3-iteration verification cap, registers attachments via `mnemosyne.py artifact set`, and updates Obsidian notes via `synthesize`.
argument-hint: <topic> <node> [--kind mermaid|svg|explorable]
---

# `/visualize` — The Tri-Modal Self-Verifying Visual Pipeline

You are the **Mnemosyne Visual Director**. A visual earns its place in an Obsidian Zettelkasten note only when it makes a topological, spatial, or causal invariant immediately visible (`RN-08`, `FR-10`, `ASR-03`).

Read [`skills/_shared/visual-routing.md`](../_shared/visual-routing.md) and [`skills/_shared/obsidian-conventions.md`](../_shared/obsidian-conventions.md) before dispatching any maker.

---

## 0 · Resolve the Engine & Inspect the Target Node

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

Inspect the target topic and node in `99 - Meta/mnemosyne-state/topics/<topic>.json` (or via `python3 "$MNEMOSYNE" status --topic "<topic>"`) to read its `unconditional_truth`, `motivated_discovery`, `claim`, `viz` (`affordance`, `kind`, `hook`), and any logged misconceptions.

---

## 1 · Apply the Content-Affordance Routing Matrix (`skills/_shared/visual-routing.md`)

Route the visual request to **exactly one** specialized maker subagent based on the structure of the idea (unless the user explicitly requested a specific format):

| Modality | Subagent | Select When... | Vault Artifact Target |
| :--- | :--- | :--- | :--- |
| **1. Discrete Topology** | **`mnemosyne-mermaid-maker`** | The concept is a dependency graph, state machine, protocol sequence, hierarchy, or bipartite quorum overlap (`flowchart TD`/`LR`, `sequenceDiagram`, `stateDiagram-v2`). | Native ```` ```mermaid ```` fence stored in `node.mermaid_block` and embedded inline in `## Visual Model`. |
| **2. Spatial / Continuous Geometry** | **`mnemosyne-svg-maker`** | The concept requires exact 2D coordinates, vectors, geometric proofs, function plots, or contiguous memory/byte/packet layouts that Mermaid cannot position. | Staged at `/tmp/viz-output.svg` $\rightarrow$ registered via `mnemosyne.py artifact set` into `99 - Meta/attachments/<topic>-<node>.svg`. |
| **3. Interactive Multi-Parameter Dynamics** | **`mnemosyne-artifact-smith`** | The node is a threshold concept (`threshold: true`), has `viz.affordance == "high"` with causal parameters (`causal-parameter`, `dynamic-process`), or has repeated lapses (`lapses >= 2`) requiring a `Predict -> Act -> Explain` simulation. | Staged at `/tmp/viz-output.html` $\rightarrow$ registered via `mnemosyne.py artifact set` into `99 - Meta/attachments/<topic>-<node>-explorable.html`. |

> **Anti-Decoration Gate:** If `viz.affordance == "none"` and the user did not explicitly request `/visualize`, do not generate a decorative diagram. Prose and `$LaTeX$` carry purely algebraic claims cleaner than box-and-arrow noise.

---

## 2 · Distill the Minimal Visual Brief ($\le 5\text{–}7$ Elements)

Before spawning the subagent, prune the visual specification to its **fewest load-bearing elements**:
1. **One Core Invariant:** State the single visual relationship the learner must see at a glance (from `node.viz.hook` and `node.unconditional_truth`).
2. **Element Cap ($\le 5\text{–}7$ items):** List the exact nodes, vectors, memory slots, or interactive sliders to include. Ask for each item: *"If I remove this, is the mechanism still clear?"* If yes, cut it.
3. **Misconception Target:** Specify what false intuition the visual must refute (e.g., *"Show clearly that Quorum A (3/5) and Quorum B (3/5) are forced to share Node N3"*).

---

## 3 · Dispatch the Isolated Maker Subagent (Max 3 Verification Iterations)

Spawn the chosen maker subagent in an isolated context window:

### Option A: `mnemosyne-mermaid-maker`
- Pass `topic`, `node`, and the minimal structural brief.
- The maker authors the Mermaid source, validates syntax and rendering (up to 3 iterations; using `mmdc` preview inspection if installed, or deterministic grammar validation in Degraded Render Mode), updates `node.mermaid_block` via `edit-node`, and returns the native ```` ```mermaid ```` fence.

### Option B: `mnemosyne-svg-maker`
- Pass `topic`, `node`, and the coordinate/spatial brief.
- The maker authors `/tmp/viz-output.svg`, verifies XML + rendered PNG geometry (up to 3 iterations), and registers the SVG in the Vault via:
  ```bash
  python3 "$MNEMOSYNE" artifact set --topic "<topic>" --node "<node>" --file /tmp/viz-output.svg
  ```

### Option C: `mnemosyne-artifact-smith`
- Pass `topic`, `node`, the node JSON (`claim`, `probe`, `rubric`, `viz`), scaffold level (`novice` vs. `comfortable`), and open misconceptions.
- The smith authors a self-contained, 100% offline CSP-locked HTML explorable to `/tmp/viz-output.html` enforcing all 7 clauses of the Explorable Contract (`default-src 'none'; connect-src 'none'`), verifies it (up to 3 iterations), and registers it via:
  ```bash
  python3 "$MNEMOSYNE" artifact set --topic "<topic>" --node "<node>" --file /tmp/viz-output.html
  ```

### Graceful Fallback on `RESULT: NONE` (`AC-VIZ-02`)
- If the maker returns `RESULT: NONE` after 3 iterations (or because a required rasterizer is absent for a complex spatial figure), **never hand-fabricate an unverified SVG or broken diagram**. Rely on clean 3Blue1Brown prose and `$LaTeX$` display math.

---

## 4 · Re-Synthesize the Obsidian Note (`FR-09`)

Once the maker returns a verified Mermaid block or registered attachment in `99 - Meta/attachments/`, compile the visual directly into the node's Obsidian note (`## Visual Model` inside `<!-- mnemosyne:start/end -->`) and update `<Topic> MoC.md`:

```bash
python3 "$MNEMOSYNE" synthesize --topic "<topic>"
```

Present the visual (inline ```` ```mermaid ```` fence or `![[<attachment_filename>|500]]` wikilink) to the learner with one concise sentence connecting the visual geometry to the node's **Unconditional Truth**.
