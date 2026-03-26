# Auto Research Pipeline (ARP) v2

> Autonomous research & project completion pipeline combining Long-running Claude, Karpathy's autoresearch, Vibe Physics, AI Scientist, and Feynman patterns.

## Overview

ARP v2 is a Claude Code skill that autonomously completes projects through:
1. **Interview Phase** — Targeted questions to deeply understand the project
2. **Planning Phase** — Structured plan with success criteria, task ledger, and verification log
3. **Execution Phase** — Long-running autonomous work with 4 specialized subagents
4. **Review Phase** — Multi-layer review (AI Scientist + Feynman Reviewer + cross-model)
5. **Optimization Loop** — Autoresearch-style keep/discard iterations
6. **Delivery Phase** — Cited, verified output with provenance tracking

## Subagent System (Feynman-inspired)

ARP v2 uses 4 specialized subagents dispatched via the Agent tool:

| Agent | Role | When to Use |
|---|---|---|
| **Researcher** | Gather evidence from papers, web, databases, repos | Wide evidence sweeps, multi-source gathering |
| **Reviewer** | Adversarial peer review with severity grading | Quality gates, claim verification |
| **Writer** | Structured drafts from research notes | Manuscript, report, patent generation |
| **Verifier** | Inline citations, source URL verification, dead link cleanup | Before delivery |

### Scale Decision (auto)

| Query type | Execution |
|---|---|
| Single fact or narrow question | Search directly, no subagents, 3-10 tool calls |
| Direct comparison (2-3 items) | 2 parallel Researcher subagents |
| Broad survey or multi-faceted topic | 3-4 parallel Researcher subagents |
| Complex multi-domain research | 4-6 parallel Researcher subagents |

Never spawn subagents for work doable in 5 tool calls.

### Integrity Commandments

All subagents (and the lead agent) MUST follow:
1. **Never fabricate a source.** Every named tool, project, paper, or dataset must have a verifiable URL.
2. **Never claim something exists without checking.** Search before citing.
3. **Never extrapolate details you haven't read.** Don't describe contents you haven't fetched.
4. **URL or it didn't happen.** No URL = not included in evidence.
5. **Read before you summarize.** Don't infer paper contents from title alone.
6. **Mark status honestly.** Distinguish: `verified`, `inferred`, `unverified`, `blocked`.

### File-Based Handoff

Subagents write outputs to files, NOT inline to parent context:
- Researcher → `<slug>-research-<dimension>.md`
- Reviewer → `<slug>-review.md`
- Writer → `<slug>-draft.md`
- Verifier → `<slug>-verified.md`

Parent reads files after subagent completes. This saves context window.

### Slug-Based Naming

Every workflow derives a short **slug** (lowercase, hyphens, ≤5 words):
- Plan: `outputs/.plans/<slug>.md`
- Research: `<slug>-research-*.md`
- Draft: `outputs/.drafts/<slug>-draft.md`
- Final: `outputs/<slug>.md` or `papers/<slug>.md`
- Provenance: `<slug>.provenance.md`

Never use generic names (`research.md`, `draft.md`). Concurrent runs must not collide.

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
   - **Task Ledger** (Feynman-style):
     ```
     | ID | Owner | Task | Status | Output |
     |---|---|---|---|---|
     | T1 | lead / researcher | ... | todo | ... |
     ```
   - **Verification Log**:
     ```
     | Item | Method | Status | Evidence |
     |---|---|---|---|
     | Critical claim | source cross-read / rerun | pending | path or URL |
     ```
   - **Decision Log** (updated as workflow progresses)

2. **`ARP_CHANGELOG.md`** — Lab notebook (not release notes):
   - Read before resuming any substantial work
   - Append after: meaningful progress, failed approaches, verification results, new blockers
   - Each entry: active slug/objective + what changed + next recommended step
   - Mark verification state honestly: `verified`, `unverified`, `blocked`, `inferred`

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

### AI Scientist Integration (Idea → Review → Paper)

ARP integrates the AI Scientist pipeline (SakanaAI, Nature 2026) for end-to-end research automation: structured idea generation, automated peer review, and scientific manuscript generation.

Ref: Sakana AI, "Towards end-to-end automation of AI research", Nature 651, 914–919 (2026). doi:10.1038/s41586-026-10265-5

**Module 1: Idea Generation (Phase 1 enhancement)**

Generate scored research ideas with reflection loops:

```python
from data.ai_scientist import IdeaGenerator

gen = IdeaGenerator()
ideas = gen.generate(
    task="Design peptide inhibitors for SIRT3",
    context="Anti-aging mitochondrial target",
    existing_ideas=["SIRT3-CPP1"],
    num_ideas=5,
    num_reflections=3
)
# Each idea scored on: Interestingness, Feasibility, Novelty (1-10)
# Composite score = feasibility*0.4 + novelty*0.3 + interestingness*0.3
```

**Module 2: Automated Peer Review (Phase 4 enhancement)**

Structured review with domain-specific evaluation:

```python
from data.ai_scientist import PeerReviewer

reviewer = PeerReviewer()
prompt = reviewer.review_file("results/FULL_REPORT.md", domain="drug_discovery")
# Returns structured JSON: Summary, Strengths, Weaknesses, Scores (1-4), Overall (1-10), Decision
# Domains: drug_discovery, genomics, ml, biotech, general
# Quality gate: overall >= 6 AND decision != "Reject" → PASS
```

**Module 3: Writeup Generation (Phase 6 enhancement)**

Generate manuscripts from results in multiple formats:

```python
from data.ai_scientist import WriteupGenerator

writer = WriteupGenerator()
prompt = writer.build_writeup_from_dir(
    title="Novel Peptide Inhibitors for SIRT3",
    results_dir="./results/",
    format="imrad"  # or "report", "brief", "patent"
)
```

**Full Pipeline (convenience):**

```python
from data.ai_scientist import ARPScientist

sci = ARPScientist()
pipeline = sci.full_pipeline_prompts(
    task="Discover ovarian aging therapeutics",
    results_dir="./ovarian-aging-discovery/results/",
    domain="drug_discovery",
    format="imrad"
)
# Returns prompts for: brainstorm → execute → review → writeup
```

**When to use:**
- Starting new research → IdeaGenerator for structured brainstorming
- Milestone checkpoint → PeerReviewer as quality gate (replaces ad-hoc review)
- Final delivery → WriteupGenerator for IMRAD papers, technical reports, or patent drafts
- Full cycle → ARPScientist.full_pipeline_prompts() orchestrates all three

### Phase 4: Review (Cross-Model + AI Scientist)

At review checkpoints, use both cross-model review AND AI Scientist's structured peer review:

```
Review triggers:
- Every 3-5 milestones
- Before major architecture decisions
- When stuck on a problem
- Before final delivery

Step 1: AI Scientist peer review (structured scores + actionable feedback)
Step 2: Cross-model review via GPT/Codex (independent sanity check)
Step 3: Quality gate — both must pass (overall >= 6)
```

If review score < 6: address weaknesses and suggestions before continuing.
If review score >= 6: proceed to next phase.

### Phase 5: Optimization Loop (autoresearch + Memento self-evolution)

For optimizable components (ML models, algorithms, UI, performance):

```
LOOP:
  1. Make a change (experiment)
  2. Measure against metric
  3. If improved → KEEP (git commit, advance)
  4. If equal/worse → DISCARD (git reset)
  5. Log result in ARP_CHANGELOG.md
  6. Reflect → continue / replan / finalize (Memento)
  7. Track approach utility score (Memento)
  8. If approach utility < 0.2 after 3 attempts → DEPRECATE, try different strategy
  9. Repeat until diminishing returns
```

### Self-Evolution (Memento-inspired)

ARP v2 learns from its own failures via a Read → Execute → Reflect → Write loop:

**Reflection after each milestone:**
```python
from data.memento_evolution import ARPEvolution

evo = ARPEvolution("otub2-activator")
result = evo.post_milestone(
    milestone="M3: Allosteric screening",
    outcome="0 hits above threshold",
    success=False,
    approach="virtual_screening_zinc",
    remaining=["M4", "M5", "M6"]
)
# → decision: "replan", reason: "Low utility (0.15), try fragment screening instead"
```

**Approach utility tracking:**
- Every approach gets a utility score (0-1) based on success/failure history
- Consistently failing approaches (utility < 0.2, ≥3 attempts) are **deprecated**
- System suggests rewrites: broader search, different binding site, alternative method
- `evo.get_best_approach(["zinc_screen", "enamine_fragments", "chembl_repurposing"])` picks highest-utility option

**Self-rewrite suggestions:**
- When an approach fails, the system analyzes failure patterns and suggests specific fixes
- "No hits" → expand search space / relax thresholds
- "Timeout" → reduce computation / pre-filter
- "False positives" → add counter-screens
- "Weak binding" → try different site / covalent strategy

### Phase 6: Delivery (Feynman + AI Scientist)

1. **Writer** subagent generates manuscript draft from research files
2. **Verifier** subagent adds inline citations, verifies every source URL
3. **Reviewer** subagent runs adversarial verification pass:
   - FATAL issues → fix before delivery
   - MAJOR issues → note in Open Questions
   - MINOR issues → accept
   - If FATAL found and fixed → run one more verification pass
4. AI Scientist peer review (structured scores as final quality gate)
5. **Provenance record** (`<slug>.provenance.md`):
   ```markdown
   # Provenance: [topic]
   - **Date:** [date]
   - **Rounds:** [number of researcher rounds]
   - **Sources consulted:** [total]
   - **Sources accepted:** [survived verification]
   - **Sources rejected:** [dead links, unverifiable]
   - **Verification:** [PASS / PASS WITH NOTES]
   - **Plan:** outputs/.plans/<slug>.md
   - **Research files:** [list]
   ```
6. Final output → `outputs/<slug>.md` or `papers/<slug>.md`
7. Summary report to user

### Additional Workflows (Feynman-inspired)

**Deep Research** (`/arp deepresearch <topic>`):
Multi-agent investigation with parallel researchers → synthesis → verification → cited brief

**Literature Review** (`/arp lit <topic>`):
Paper-first review with consensus/disagreements/open questions + provenance

**Paper Audit** (`/arp audit <paper>`):
Compare paper claims against public codebase — catch mismatches, missing code, reproduction risks

**Replication** (`/arp replicate <paper>`):
Plan and execute experiment replication on local/Docker/Modal/RunPod

**Source Comparison** (`/arp compare <items>`):
Side-by-side comparison matrix with cited evidence

## Inspired By

- **[Long-running Claude](https://www.anthropic.com/research/long-running-Claude)** (Anthropic): Persistent memory, test oracle, autonomous sessions
- **[autoresearch](https://github.com/karpathy/autoresearch)** (Karpathy): Fixed-budget experiments, keep/discard loop, NEVER STOP
- **[Vibe Physics](https://www.anthropic.com/research/vibe-physics)** (Anthropic): Expert guides AI, 10x acceleration, structured supervision
- **[AI Scientist](https://github.com/SakanaAI/AI-Scientist)** (SakanaAI): End-to-end research automation, structured idea generation, automated peer review, manuscript generation (Nature 2026)
- **[Feynman](https://github.com/getcompanion-ai/feynman)** (Companion AI): 4-agent research system (Researcher/Reviewer/Writer/Verifier), provenance tracking, integrity commandments, file-based handoff, scale-aware agent dispatch
- **[Memento-Skills](https://github.com/Memento-Teams/Memento-Skills)** (Memento Teams): Self-evolving skill system, Read-Execute-Reflect-Write loop, utility scoring, approach deprecation, failure-driven rewriting
