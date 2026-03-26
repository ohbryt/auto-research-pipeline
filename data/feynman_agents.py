"""
Feynman-Inspired Research Agents for ARP v2
=============================================
Adapted from getcompanion-ai/feynman (MIT License)

4 specialized subagent prompts for file-based handoff:
1. Researcher — evidence gathering with integrity commandments
2. Reviewer — adversarial peer review with severity grading
3. Writer — structured manuscript drafts from research notes
4. Verifier — inline citations, URL verification, dead link cleanup

Usage:
    from data.feynman_agents import ResearchOrchestrator

    orch = ResearchOrchestrator(slug="otub2-steatosis")

    # Generate researcher prompt
    prompt = orch.researcher_prompt(
        objective="Find OTUB2 expression data in NAFLD liver biopsies",
        sources=["GEO", "PubMed", "Open Targets"],
        output_file="otub2-steatosis-research-geo.md"
    )
    # → dispatch as subagent, reads output file after completion

    # Scale decision
    n_agents = orch.scale_decision("Comprehensive analysis of OTUB2 in metabolic disease")
    # → returns 3-4 (broad survey)
"""

import os
import re
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime


# ─── Integrity Commandments ───

INTEGRITY_RULES = """
## Integrity Commandments (MANDATORY)
1. **Never fabricate a source.** Every named project, paper, or dataset must have a verifiable URL.
2. **Never claim something exists without checking.** Search before citing.
3. **Never extrapolate details you haven't read.** Don't describe contents you haven't fetched.
4. **URL or it didn't happen.** No URL = not included in evidence.
5. **Read before you summarize.** Don't infer paper contents from title alone.
6. **Mark status honestly.** Distinguish: `verified`, `inferred`, `unverified`, `blocked`.
"""


# ─── Researcher Agent ───

RESEARCHER_PROMPT = """You are ARP's evidence-gathering subagent.

{integrity}

## Objective
{objective}

## Search Strategy
1. **Start wide.** Begin with short, broad queries to map the landscape.
2. **Evaluate availability.** After first round, assess what source types exist and which are highest quality.
3. **Progressively narrow.** Drill into specifics using terminology discovered in initial results.
4. **Cross-source.** Use both web search and academic databases when topic spans both.

## Source Priority
- **Prefer:** academic papers, official documentation, primary datasets, verified benchmarks, government filings
- **Accept with caveats:** well-cited secondary sources, established trade publications
- **Deprioritize:** SEO listicles, undated blog posts, content aggregators
- **Reject:** sources with no author and no date, AI-generated content with no primary backing

## Source Types to Search
{sources}

## Output Format

Write to: `{output_file}`

### Evidence Table
| # | Source | URL | Key Claim | Type | Confidence |
|---|--------|-----|-----------|------|------------|
| 1 | ... | ... | ... | primary/secondary | high/medium/low |

### Findings
Write findings using inline source references: `[1]`, `[2]`, etc.
Every factual claim must cite at least one source by number.
Label inferences as inferences.

### Sources
Numbered list matching the evidence table:
1. Author/Title — URL

### Coverage Status
- What was checked directly
- What remains uncertain
- Tasks that could not be completed

## Context Hygiene
- Write findings to file progressively. Do not accumulate full pages in memory.
- Extract relevant quotes, discard the rest.
- Triage search results by title first. Only fetch full content for top candidates.
- Return a one-line summary to parent, not full findings.
"""


# ─── Reviewer Agent ───

REVIEWER_PROMPT = """You are ARP's research reviewer.

Act like a skeptical but fair peer reviewer. Be adversarial when verifying claims.

## Review Target
{target_file}

## Domain
{domain}

## Review Checklist
- Evaluate novelty, clarity, empirical rigor, reproducibility
- Look for:
  - Missing or weak baselines/controls
  - Evaluation mismatches
  - Unclear claims of novelty
  - Insufficient statistical evidence
  - Claims that outrun the experiments
  - "Verified" statements without showing the actual check
  - Single-source claims on critical findings
- Distinguish between FATAL, MAJOR, and MINOR issues
- Keep looking after finding the first problem

## Output Format

Write to: `{output_file}`

### Part 1: Structured Review
```
## Summary
1-2 paragraph summary.

## Strengths
- [S1] ...

## Weaknesses
- [W1] **FATAL:** ...
- [W2] **MAJOR:** ...
- [W3] **MINOR:** ...

## Questions for Authors
- [Q1] ...

## Verdict
Overall assessment. Score 1-10.

## Revision Plan
Prioritized steps to address each weakness.
```

### Part 2: Inline Annotations
Quote specific passages and annotate:
```
> "We achieve state-of-the-art results"
**[W1] FATAL:** This claim is unsupported — Table 3 shows...
```

## Rules
- Every weakness must reference a specific passage or section.
- Inline annotations must quote exact text.
- End with a Sources section for anything additionally inspected.
"""


# ─── Writer Agent ───

WRITER_PROMPT = """You are ARP's manuscript writer.

## Task
Write a structured {format} from the research files provided.

## Title
{title}

## Research Files to Synthesize
{research_files}

## Format: {format_name}
Sections:
{sections}

## Requirements
- Use precise scientific language
- Include specific numbers, metrics, and data from research files
- Cite sources using inline references [1], [2] from research files
- Be thorough but concise — every sentence earns its place
- Include limitations and future work
- Before finalizing, do a claim sweep:
  - Map each critical claim to its supporting source
  - Downgrade anything that cannot be grounded
  - Label inferences as inferences

## Output
Write to: `{output_file}`
"""


# ─── Verifier Agent ───

VERIFIER_PROMPT = """You are ARP's citation verifier.

## Task
Add inline citations to the draft and verify every source URL.

## Draft to Verify
{draft_file}

## Research Files (source material)
{research_files}

## Process
1. Read the draft and all research files
2. For each factual claim in the draft:
   - Find the supporting source in research files
   - Add inline citation [N] with source number
   - If no source supports the claim, flag it as `[UNSOURCED]`
3. For each URL in sources:
   - Verify it is accessible (not a dead link)
   - Flag dead links as `[DEAD LINK]`
4. Build the numbered Sources section at the end
5. Do NOT rewrite the report — only add citations and verify

## Output
Write verified version to: `{output_file}`

Include a verification summary:
- Total claims checked
- Claims with sources
- Unsourced claims
- Dead links found
- Verification status: PASS / PASS WITH NOTES / FAIL
"""


# ─── Orchestrator ───

@dataclass
class ResearchOrchestrator:
    """
    Orchestrate 4-agent research pipeline with file-based handoff.
    """
    slug: str
    output_dir: str = "outputs"
    plans_dir: str = "outputs/.plans"
    drafts_dir: str = "outputs/.drafts"

    def __post_init__(self):
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.plans_dir, exist_ok=True)
        os.makedirs(self.drafts_dir, exist_ok=True)

    # ── Scale Decision ──

    @staticmethod
    def scale_decision(query: str) -> int:
        """Determine number of researcher agents based on query complexity."""
        words = len(query.split())
        complexity_keywords = ['comprehensive', 'survey', 'compare', 'all', 'multi',
                              'landscape', 'systematic', 'broad', 'across', 'review']
        has_complex = any(k in query.lower() for k in complexity_keywords)

        if words < 10 and not has_complex:
            return 0  # Direct search, no subagents
        elif words < 20 and not has_complex:
            return 2  # Narrow comparison
        elif has_complex or words >= 30:
            return 4  # Broad survey
        else:
            return 3  # Standard multi-faceted

    # ── Researcher ──

    def researcher_prompt(
        self,
        objective: str,
        sources: Optional[List[str]] = None,
        output_file: Optional[str] = None,
    ) -> str:
        if sources is None:
            sources = ["PubMed", "Web search", "GEO", "ChEMBL", "Open Targets"]
        if output_file is None:
            output_file = f"{self.slug}-research.md"

        return RESEARCHER_PROMPT.format(
            integrity=INTEGRITY_RULES,
            objective=objective,
            sources="\n".join(f"- {s}" for s in sources),
            output_file=output_file,
        )

    # ── Reviewer ──

    def reviewer_prompt(
        self,
        target_file: str,
        domain: str = "general",
        output_file: Optional[str] = None,
    ) -> str:
        if output_file is None:
            output_file = f"{self.slug}-review.md"

        return REVIEWER_PROMPT.format(
            target_file=target_file,
            domain=domain,
            output_file=output_file,
        )

    # ── Writer ──

    def writer_prompt(
        self,
        title: str,
        research_files: List[str],
        format: str = "imrad",
        output_file: Optional[str] = None,
    ) -> str:
        if output_file is None:
            output_file = f"{self.drafts_dir}/{self.slug}-draft.md"

        formats = {
            "imrad": {
                "name": "IMRAD Scientific Paper",
                "sections": ["Abstract", "1. Introduction", "2. Methods",
                            "3. Results", "4. Discussion", "5. Conclusion", "References"]
            },
            "report": {
                "name": "Technical Report",
                "sections": ["Executive Summary", "1. Background", "2. Approach",
                            "3. Results", "4. Key Findings", "5. Recommendations", "References"]
            },
            "brief": {
                "name": "Research Brief",
                "sections": ["Summary", "Key Findings", "Methods", "Implications", "References"]
            },
            "patent": {
                "name": "Patent Draft",
                "sections": ["Title", "Abstract", "Field", "Background",
                            "Summary of Invention", "Detailed Description", "Claims"]
            },
        }

        fmt = formats.get(format, formats["imrad"])

        return WRITER_PROMPT.format(
            format=format,
            title=title,
            research_files="\n".join(f"- {f}" for f in research_files),
            format_name=fmt["name"],
            sections="\n".join(f"- {s}" for s in fmt["sections"]),
            output_file=output_file,
        )

    # ── Verifier ──

    def verifier_prompt(
        self,
        draft_file: str,
        research_files: List[str],
        output_file: Optional[str] = None,
    ) -> str:
        if output_file is None:
            output_file = f"{self.slug}-verified.md"

        return VERIFIER_PROMPT.format(
            draft_file=draft_file,
            research_files="\n".join(f"- {f}" for f in research_files),
            output_file=output_file,
        )

    # ── Provenance ──

    def provenance_record(
        self,
        topic: str,
        rounds: int,
        sources_consulted: int,
        sources_accepted: int,
        sources_rejected: int,
        verification_status: str,
        research_files: List[str],
    ) -> str:
        return f"""# Provenance: {topic}

- **Date:** {datetime.now().strftime('%Y-%m-%d')}
- **Slug:** {self.slug}
- **Rounds:** {rounds}
- **Sources consulted:** {sources_consulted}
- **Sources accepted:** {sources_accepted}
- **Sources rejected:** {sources_rejected}
- **Verification:** {verification_status}
- **Plan:** {self.plans_dir}/{self.slug}.md
- **Research files:** {', '.join(research_files)}
"""

    # ── Full Pipeline ──

    def full_pipeline(self, topic: str, domain: str = "general") -> Dict:
        """
        Generate all prompts for a full Feynman-style research pipeline.
        Returns dict of prompts to dispatch as subagents.
        """
        n_researchers = self.scale_decision(topic)

        pipeline = {
            "slug": self.slug,
            "scale": n_researchers,
            "steps": []
        }

        # Step 1: Plan
        pipeline["steps"].append({
            "step": 1,
            "name": "Plan",
            "agent": "lead",
            "action": f"Create research plan at {self.plans_dir}/{self.slug}.md",
        })

        # Step 2: Research
        if n_researchers == 0:
            pipeline["steps"].append({
                "step": 2,
                "name": "Direct Research",
                "agent": "lead",
                "action": "Search directly, no subagents needed",
            })
        else:
            for i in range(n_researchers):
                pipeline["steps"].append({
                    "step": 2,
                    "name": f"Researcher {i+1}",
                    "agent": "researcher",
                    "output": f"{self.slug}-research-{i+1}.md",
                    "parallel": True,
                })

        # Step 3: Write
        research_files = [f"{self.slug}-research-{i+1}.md" for i in range(max(1, n_researchers))]
        pipeline["steps"].append({
            "step": 3,
            "name": "Write Draft",
            "agent": "writer",
            "prompt": self.writer_prompt(topic, research_files),
            "output": f"{self.drafts_dir}/{self.slug}-draft.md",
        })

        # Step 4: Verify
        pipeline["steps"].append({
            "step": 4,
            "name": "Verify Citations",
            "agent": "verifier",
            "output": f"{self.slug}-verified.md",
        })

        # Step 5: Review
        pipeline["steps"].append({
            "step": 5,
            "name": "Adversarial Review",
            "agent": "reviewer",
            "prompt": self.reviewer_prompt(f"{self.slug}-verified.md", domain),
            "output": f"{self.slug}-review.md",
        })

        # Step 6: Deliver
        pipeline["steps"].append({
            "step": 6,
            "name": "Deliver",
            "agent": "lead",
            "action": f"Fix FATAL issues, write provenance, save to {self.output_dir}/{self.slug}.md",
        })

        return pipeline


# ─── Convenience Functions ───

def quick_research(topic: str, slug: Optional[str] = None) -> Dict:
    """Quick way to set up a research pipeline."""
    if slug is None:
        slug = re.sub(r'[^a-z0-9]+', '-', topic.lower().strip())[:40].strip('-')
    orch = ResearchOrchestrator(slug=slug)
    return orch.full_pipeline(topic)


def make_slug(topic: str) -> str:
    """Generate a slug from a topic string."""
    words = re.sub(r'[^a-z0-9\s]', '', topic.lower()).split()
    # Remove filler words
    filler = {'the', 'a', 'an', 'of', 'in', 'on', 'for', 'and', 'or', 'to', 'with', 'by', 'is', 'are', 'was', 'were'}
    meaningful = [w for w in words if w not in filler]
    return '-'.join(meaningful[:5])
