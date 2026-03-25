# Auto Research Pipeline (ARP)

> Autonomous project completion pipeline combining Long-running Claude, Karpathy's autoresearch, and Vibe Physics patterns.

## Overview

ARP is a Claude Code skill that autonomously completes projects through:
1. **Interview Phase** — Claude asks 10-20 targeted questions to deeply understand the project
2. **Planning Phase** — Creates structured plan with success criteria and test oracle
3. **Execution Phase** — Long-running autonomous work with persistent memory
4. **Review Phase** — Cross-model review via GPT/Codex for quality gates
5. **Optimization Loop** — Autoresearch-style keep/discard iterations
6. **Delivery Phase** — Final verification, documentation, and deployment

## Invocation

```
/auto-research-pipeline <project description>
```

Or simply describe your project and say "ARP로 진행해줘" or "autonomous pipeline으로 해줘".

## How It Works

### Phase 1: Interview (10-20 Questions)

When a project is given, Claude asks targeted questions across 5 categories:

**Vision & Goals (3-4 questions)**
- What is the end goal? What does "done" look like?
- Who is the target user/audience?
- What's the timeline/urgency?
- What's the success metric?

**Technical Scope (3-4 questions)**
- What tech stack/language preference?
- Any existing code/repo to build on?
- What are the hard constraints?
- Integration requirements?

**Domain Context (2-3 questions)**
- What domain expertise is needed?
- Reference projects or papers?
- Regulatory/compliance requirements?

**Resources & Constraints (2-3 questions)**
- Available APIs, databases, compute?
- Budget constraints?
- What should NOT be done?

**Quality & Delivery (2-3 questions)**
- How will you verify correctness?
- Deployment target?
- Documentation needs?

Claude presents all questions at once. User answers (can skip some). Claude adapts based on answers.

### Phase 2: Planning

Based on interview answers, Claude creates:

1. **`ARP_PLAN.md`** — Project plan with:
   - Objective & success criteria
   - Architecture decisions
   - Phase breakdown (milestones)
   - Risk analysis
   - Test oracle definition

2. **`ARP_CHANGELOG.md`** — Persistent memory file:
   - Progress log (what's done, what failed, why)
   - Failed approaches (prevents re-attempting dead ends)
   - Metrics at checkpoints
   - Decision rationale

3. **`ARP_PROGRAM.md`** — Agent instructions:
   - Execution rules
   - Quality gates
   - When to commit
   - Review triggers

### Phase 3: Execution (Autonomous)

Claude works autonomously following the plan:

```
LOOP until all milestones complete:
  1. Pick next milestone from ARP_PLAN.md
  2. Implement (code, research, design)
  3. Self-verify against test oracle
  4. Git commit if passing
  5. Update ARP_CHANGELOG.md
  6. Every N milestones → trigger Review Phase
  7. If stuck → try alternative approach, log failure
```

**Key behaviors:**
- **NEVER STOP** until manually interrupted or all milestones complete
- Commit after every meaningful unit of work
- Log failed approaches in CHANGELOG (prevents loops)
- Use subagents for parallelizable tasks
- Save raw data/intermediate results

### HuggingFace Dataset Integration (Optional)

ARP can leverage HuggingFace's ecosystem for large-scale data:

**hf-mount (Zero-Download Data Access):**
```bash
# Mount any HF dataset as local folder — no download needed
hf-mount start repo InstaDeepAI/multi_species_genomes /mnt/genomes
ls /mnt/genomes  # Browse like local files
```

**Dataset Streaming:**
```python
from data.hf_datasets import HFDatasetManager
hf = HFDatasetManager()

# Stream — processes data without downloading entire dataset
for batch in hf.stream_dataset("jglaser/binding_affinity"):
    process(batch)
```

**Result Upload:**
```python
# Save results directly to HuggingFace (skip local SSD)
hf.upload_results("./results/", "myuser/my-research-data")
```

**When to use:**
- Dataset > 1GB → use hf-mount or streaming
- Need to share results → upload to HF Hub
- Limited local storage → mount instead of download
- Reproducibility → reference HF dataset IDs in reports

### LigandForge Integration (Drug Discovery)

For peptide drug discovery pipelines, ARP integrates with LigandForge — a discrete diffusion model generating >700 peptide sequences/sec (10,000x BoltzGen, 1,000,000x BindCraft).

**When to use:**
- De novo peptide binder design against any receptor target
- Massive-scale candidate generation (100K+ in minutes)
- Difficult targets (TNF-α, PD-L1, KRAS — historically "undruggable")

```python
from data.ligandforge import LigandForgeManager
lf = LigandForgeManager()

# Estimate throughput
lf.estimate_throughput(100000, gpu="A100")  # → ~200 sec

# Get paper benchmarks
lf.get_paper_results("TNF-α")  # → sub-100nM binders found

# Suggest full pipeline for your targets
lf.suggest_pipeline(["SIRT3", "FSHR", "mTOR"], budget_gpu_hours=1.0)
```

Ref: Watson 2026, bioRxiv 10.64898/2026.03.14.711748

### Phase 4: Review (Cross-Model)

At review checkpoints, send work to GPT/Codex for independent assessment:

```
Review triggers:
- Every 3-5 milestones
- Before major architecture decisions
- When stuck on a problem
- Before final delivery

Review prompt → GPT/Codex:
  "Review this work against the plan. Check:
   1. Does it meet success criteria?
   2. Any bugs, edge cases, or design flaws?
   3. What would you do differently?
   4. Score 1-10 on completeness and quality."
```

If review score < 7: address feedback before continuing.
If review score >= 7: proceed to next phase.

### Phase 5: Optimization Loop (autoresearch-style)

For optimizable components (ML models, algorithms, UI, performance):

```
LOOP:
  1. Make a change (experiment)
  2. Measure against metric
  3. If improved → KEEP (git commit, advance)
  4. If equal/worse → DISCARD (git reset)
  5. Log result in ARP_CHANGELOG.md
  6. Repeat until diminishing returns
```

### Phase 6: Delivery

1. Final cross-model review
2. Documentation generation
3. Deployment (if configured)
4. Summary report to user

## Inspired By

- **[Long-running Claude](https://www.anthropic.com/research/long-running-Claude)** (Anthropic): Persistent memory, test oracle, autonomous sessions
- **[autoresearch](https://github.com/karpathy/autoresearch)** (Karpathy): Fixed-budget experiments, keep/discard loop, NEVER STOP
- **[Vibe Physics](https://www.anthropic.com/research/vibe-physics)** (Anthropic): Expert guides AI, 10x acceleration, structured supervision
