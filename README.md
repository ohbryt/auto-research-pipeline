# Auto Research Pipeline (ARP)

![ARP](https://img.shields.io/badge/Claude_Code-Skill-blueviolet) ![License](https://img.shields.io/badge/license-MIT-green)

**Autonomous project completion pipeline for Claude Code.**

Give Claude a project → it asks smart questions → then autonomously builds it with cross-model review and optimization loops.

Inspired by:
- [Long-running Claude](https://www.anthropic.com/research/long-running-Claude) (Anthropic) — persistent memory, test oracles, autonomous sessions
- [autoresearch](https://github.com/karpathy/autoresearch) (Karpathy) — keep/discard experiment loops, NEVER STOP
- [Vibe Physics](https://www.anthropic.com/research/vibe-physics) (Anthropic) — AI as grad student, expert-guided 10x acceleration

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                  AUTO RESEARCH PIPELINE                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ① INTERVIEW    User describes project                  │
│     ↓           Claude asks 10-20 targeted questions    │
│     ↓           User answers → Claude understands       │
│                                                         │
│  ② PLAN         ARP_PLAN.md (milestones + test oracle)  │
│     ↓           ARP_CHANGELOG.md (persistent memory)    │
│     ↓           ARP_PROGRAM.md (agent rules)            │
│                                                         │
│  ③ EXECUTE      Autonomous work on milestones           │
│     ↓           Git commit after each unit              │
│     ↓           Log progress + failed approaches        │
│                                                         │
│  ④ REVIEW       Send to GPT/Codex for quality gate      │
│     ↓           Score < 7 → fix, Score >= 7 → proceed  │
│     ↓           Every 3-5 milestones                    │
│                                                         │
│  ⑤ OPTIMIZE     autoresearch-style keep/discard loop    │
│     ↓           Change → Measure → Keep or Revert       │
│     ↓           Until diminishing returns               │
│                                                         │
│  ⑥ DELIVER      Final review + docs + deploy            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install as Claude Code Skill

```bash
# Clone into your Claude skills directory
cd ~/.claude/skills
git clone https://github.com/ohbryt/auto-research-pipeline.git arp
```

### 2. Use It

In Claude Code, just say:

```
ARP로 진행해줘: [your project description]
```

Or:

```
/auto-research-pipeline Build a real-time stock analysis dashboard with ML predictions
```

### 3. Answer Questions

Claude will ask 10-20 questions about your project. Answer them (you can skip some). Then Claude works autonomously.

## The 6 Phases

### Phase 1: Interview (10-20 Questions)

Claude asks questions across 5 categories:

| Category | Questions | Examples |
|----------|-----------|---------|
| Vision & Goals | 3-4 | What does "done" look like? Success metric? |
| Technical Scope | 3-4 | Tech stack? Existing code? Constraints? |
| Domain Context | 2-3 | Domain expertise needed? Reference papers? |
| Resources | 2-3 | APIs available? Budget? What NOT to do? |
| Quality | 2-3 | How to verify? Deploy target? |

### Phase 2: Planning

Creates three files in your project:

- **`ARP_PLAN.md`** — Milestones, architecture, success criteria, test oracle
- **`ARP_CHANGELOG.md`** — Persistent memory (progress, failures, decisions)
- **`ARP_PROGRAM.md`** — Execution rules for the agent

### Phase 3: Autonomous Execution

```
LOOP until all milestones complete:
  1. Pick next milestone
  2. Implement
  3. Self-verify against test oracle
  4. Git commit if passing
  5. Update CHANGELOG
  6. Every N milestones → Review
  7. If stuck → try alternative, log failure
```

**NEVER STOP** — runs until complete or manually interrupted.

### Phase 4: Cross-Model Review

Sends work to GPT/Codex for independent quality assessment:

- Checks against success criteria
- Finds bugs, edge cases, design flaws
- Scores 1-10 on completeness and quality
- Score < 7 → address feedback before continuing

### Phase 5: Optimization Loop

For optimizable components (inspired by Karpathy's autoresearch):

```
LOOP:
  1. Make a change
  2. Measure against metric
  3. If improved → KEEP (commit)
  4. If worse → DISCARD (reset)
  5. Log result
  6. Repeat
```

### Phase 6: Delivery

- Final cross-model review
- Auto-generate documentation
- Deploy if configured
- Summary report

## HuggingFace Integration

ARP integrates with HuggingFace for large-scale scientific data:

### Zero-Download Data Access
```bash
# Install hf-mount
curl -fsSL https://raw.githubusercontent.com/huggingface/hf-mount/main/install.sh | sh

# Mount datasets as local folders
hf-mount start repo jglaser/binding_affinity /tmp/data
python3 analyze.py --input /tmp/data  # No download needed!
```

### Curated Scientific Datasets
| Dataset | Description | Size |
|---------|-------------|------|
| InstaDeepAI/multi_species_genomes | Multi-species genome sequences | Large |
| jglaser/binding_affinity | Protein-ligand binding data | Medium |
| katielink/clinvar | ClinVar genetic variants | Medium |
| bloyal/ProteinGLUE | Protein function benchmarks | Medium |
| financial_phrasebank | Financial news sentiment | Small |

### Upload Results
```python
from data.hf_datasets import HFDatasetManager
hf = HFDatasetManager(hf_token="your_token")
hf.upload_results("./results/", "youruser/project-data")
```

## Project Files

```
your-project/
├── ARP_PLAN.md          # Project plan & milestones
├── ARP_CHANGELOG.md     # Persistent memory & progress log
├── ARP_PROGRAM.md       # Agent execution rules
├── ARP_REVIEW_LOG.md    # Cross-model review history
└── ... (your project files)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ARP_REVIEW_MODEL` | codex | Review backend (codex, gemini, self) |
| `ARP_REVIEW_INTERVAL` | 3 | Milestones between reviews |
| `ARP_OPTIMIZATION_ROUNDS` | 20 | Max optimization iterations |
| `ARP_AUTO_COMMIT` | true | Auto git commit on progress |
| `ARP_LANGUAGE` | auto | Interview language (ko, en, auto) |

## Examples

### Scientific Research
```
ARP: Build an anti-aging protein discovery pipeline using public databases
→ Interview (15 questions about targets, databases, methods)
→ Plan (4 stages: discovery → structural → design → validation)
→ Execute (query GenAge, UniProt, AlphaFold, ChEMBL)
→ Review (GPT validates methodology)
→ Optimize (iterate peptide designs)
→ Deliver (full report + data + code)
```

### Web Application
```
ARP: Build a fitness tracking app with AI coaching
→ Interview (12 questions about features, stack, users)
→ Plan (Next.js + Tailwind, 5 milestones)
→ Execute (build pages, components, API)
→ Review (GPT checks UX, accessibility)
→ Optimize (Lighthouse scores, bundle size)
→ Deliver (deployed on Vercel + docs)
```

### Data Analysis
```
ARP: Analyze fertility/infertility biomarkers from GEO datasets
→ Interview (18 questions about data, methods, hypotheses)
→ Plan (data collection → DEG → pathway → ML model)
→ Execute (download GEO, run DESeq2, GSEA)
→ Review (GPT validates statistical methods)
→ Optimize (model hyperparameters)
→ Deliver (paper-ready figures + report)
```

## Philosophy

> *"Most scientists currently using AI agents work in a conversational loop, managing each step of the process on a tight leash. As models have become significantly better at long-horizon tasks, a new way of working emerged: rather than getting involved with every detail, we can specify the high-level objective and set a team of agents loose to work autonomously."*
> — Anthropic, Long-running Claude

> *"The idea: give an AI agent a small but real setup and let it experiment autonomously overnight. It modifies the code, trains, checks if the result improved, keeps or discards, and repeats. You wake up in the morning to a log of experiments and (hopefully) a better result."*
> — Karpathy, autoresearch

> *"Current LLMs are at the G2 (second-year graduate student) level — they cannot yet do original research autonomously, but they can vastly accelerate research done by experts."*
> — Anthropic, Vibe Physics

ARP combines all three: **autonomous execution** + **experiment loops** + **expert supervision**.

## License

MIT

## Author

Brown Biotech Inc. (CEO: Chang-Myung Oh)
