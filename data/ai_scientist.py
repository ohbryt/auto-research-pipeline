"""
AI Scientist Integration for ARP
=================================
Adapted from SakanaAI/AI-Scientist (Nature 2026, doi:10.1038/s41586-026-10265-5)

Three core modules:
1. IdeaGenerator — Structured research idea generation with scoring
2. PeerReviewer — Automated peer review with structured feedback
3. WriteupGenerator — Scientific manuscript/report generation

Usage:
    from data.ai_scientist import IdeaGenerator, PeerReviewer, WriteupGenerator

    # Generate research ideas
    gen = IdeaGenerator()
    ideas = gen.generate(
        task="Design peptide inhibitors for SIRT3",
        context="Anti-aging mitochondrial target",
        existing_ideas=["SIRT3-CPP1", "SIRT3-AMP2"],
        num_ideas=5,
        num_reflections=3
    )

    # Review a report/paper
    reviewer = PeerReviewer()
    review = reviewer.review("path/to/report.md", domain="drug_discovery")

    # Generate writeup from results
    writer = WriteupGenerator()
    paper = writer.generate(
        title="Novel Peptide Inhibitors for SIRT3",
        results_dir="./results/",
        format="imrad"  # or "report", "brief"
    )
"""

import json
import os
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


# ─── Data Classes ───

@dataclass
class ResearchIdea:
    """Structured research idea with scoring."""
    name: str
    title: str
    experiment: str
    interestingness: int  # 1-10
    feasibility: int      # 1-10
    novelty: int          # 1-10
    rationale: str = ""
    status: str = "proposed"  # proposed → approved → running → done → discarded

    @property
    def composite_score(self) -> float:
        """Weighted composite: feasibility(0.4) + novelty(0.3) + interestingness(0.3)"""
        return self.feasibility * 0.4 + self.novelty * 0.3 + self.interestingness * 0.3

    def to_dict(self) -> dict:
        d = asdict(self)
        d["composite_score"] = round(self.composite_score, 1)
        return d


@dataclass
class PeerReview:
    """Structured peer review output."""
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    originality: int      # 1-4
    quality: int           # 1-4
    clarity: int           # 1-4
    significance: int      # 1-4
    soundness: int         # 1-4
    questions: List[str]
    limitations: List[str]
    overall: int           # 1-10
    confidence: int        # 1-5
    decision: str          # Accept / Revise / Reject
    suggestions: List[str] = field(default_factory=list)

    @property
    def is_passing(self) -> bool:
        return self.overall >= 6 and self.decision != "Reject"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_passing"] = self.is_passing
        return d


# ─── Idea Generator ───

class IdeaGenerator:
    """
    Generate structured research ideas with reflection loops.
    Adapted from AI Scientist's generate_ideas.py
    """

    IDEA_PROMPT = """You are a creative research scientist.

TASK: {task_description}

CONTEXT: {context}

EXISTING IDEAS (avoid duplicating these):
{prev_ideas_string}

Generate the next impactful and creative research idea.
The idea must be:
- Feasible with available computational tools and public databases
- Novel compared to existing ideas
- Scientifically grounded with clear methodology

Respond in this format:

THOUGHT:
<your reasoning, intuitions, and high-level plan>

IDEA JSON:
```json
{{
  "Name": "lowercase_with_underscores",
  "Title": "Full Title of the Idea",
  "Experiment": "Step-by-step outline of what to do",
  "Interestingness": <1-10>,
  "Feasibility": <1-10>,
  "Novelty": <1-10>,
  "Rationale": "Why this matters and what we expect to find"
}}
```
"""

    REFLECTION_PROMPT = """Round {current_round}/{num_reflections}.

Review the idea you just created. Consider:
1. Is it truly novel vs. existing work?
2. Can it be executed with available tools?
3. Will the results be meaningful?
4. Is the scope appropriate (not too broad, not too narrow)?

Refine and improve. Respond in the same format:

THOUGHT:
<your refined reasoning>

IDEA JSON:
```json
<refined JSON>
```

If no changes needed, repeat the JSON and add "I am done" in THOUGHT.
"""

    def generate(
        self,
        task: str,
        context: str = "",
        existing_ideas: Optional[List[str]] = None,
        num_ideas: int = 5,
        num_reflections: int = 2,
    ) -> List[ResearchIdea]:
        """
        Generate research ideas with reflection.

        Returns list of ResearchIdea sorted by composite score.
        This method generates the PROMPTS — actual LLM calls
        are handled by the ARP execution engine (Claude).
        """
        ideas = []
        prev_ideas = existing_ideas or []

        for i in range(num_ideas):
            # Build generation prompt
            prompt = self.IDEA_PROMPT.format(
                task_description=task,
                context=context,
                prev_ideas_string="\n".join(f"- {idea}" for idea in prev_ideas) or "None yet.",
            )

            # Build reflection prompts
            reflections = []
            for r in range(num_reflections):
                reflections.append(
                    self.REFLECTION_PROMPT.format(
                        current_round=r + 1,
                        num_reflections=num_reflections,
                    )
                )

            ideas.append({
                "generation_prompt": prompt,
                "reflection_prompts": reflections,
                "idea_index": i + 1,
            })

            prev_ideas.append(f"Idea {i + 1} (pending)")

        return ideas

    @staticmethod
    def parse_idea_response(response: str) -> Optional[ResearchIdea]:
        """Parse LLM response into ResearchIdea."""
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group(1))
            return ResearchIdea(
                name=data.get("Name", "unnamed"),
                title=data.get("Title", "Untitled"),
                experiment=data.get("Experiment", ""),
                interestingness=int(data.get("Interestingness", 5)),
                feasibility=int(data.get("Feasibility", 5)),
                novelty=int(data.get("Novelty", 5)),
                rationale=data.get("Rationale", ""),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    @staticmethod
    def rank_ideas(ideas: List[ResearchIdea]) -> List[ResearchIdea]:
        """Sort ideas by composite score (descending)."""
        return sorted(ideas, key=lambda x: x.composite_score, reverse=True)

    @staticmethod
    def filter_feasible(ideas: List[ResearchIdea], min_feasibility: int = 6) -> List[ResearchIdea]:
        """Filter to only feasible ideas."""
        return [i for i in ideas if i.feasibility >= min_feasibility]


# ─── Peer Reviewer ───

class PeerReviewer:
    """
    Automated peer review system.
    Adapted from AI Scientist's perform_review.py
    """

    DOMAIN_CONTEXTS = {
        "drug_discovery": "computational drug discovery, medicinal chemistry, and pharmacology",
        "genomics": "genomics, transcriptomics, and bioinformatics",
        "ml": "machine learning and artificial intelligence",
        "biotech": "biotechnology and bioengineering",
        "general": "scientific research",
    }

    REVIEW_PROMPT = """You are a rigorous scientific reviewer evaluating research in {domain}.

MANUSCRIPT/REPORT:
{content}

Provide a thorough, structured peer review. Be critical but constructive.
Focus on scientific rigor, methodology, and practical impact.

Respond in this format:

THOUGHT:
<your detailed evaluation reasoning — be specific to this work>

REVIEW JSON:
```json
{{
  "Summary": "Brief summary of the work and its contributions",
  "Strengths": ["strength 1", "strength 2", ...],
  "Weaknesses": ["weakness 1", "weakness 2", ...],
  "Originality": <1-4>,
  "Quality": <1-4>,
  "Clarity": <1-4>,
  "Significance": <1-4>,
  "Soundness": <1-4>,
  "Questions": ["question for authors 1", ...],
  "Limitations": ["limitation 1", ...],
  "Suggestions": ["actionable suggestion 1", ...],
  "Overall": <1-10>,
  "Confidence": <1-5>,
  "Decision": "Accept/Revise/Reject"
}}
```

Rating scales:
- Originality/Quality/Clarity/Significance/Soundness: 1=poor, 2=fair, 3=good, 4=excellent
- Overall: 1=strong reject, 4=borderline reject, 6=borderline accept, 8=strong accept, 10=award quality
- Confidence: 1=low, 3=medium, 5=absolute
"""

    def build_review_prompt(
        self,
        content: str,
        domain: str = "general",
    ) -> str:
        """Build the review prompt for a given manuscript/report."""
        domain_desc = self.DOMAIN_CONTEXTS.get(domain, self.DOMAIN_CONTEXTS["general"])
        return self.REVIEW_PROMPT.format(
            domain=domain_desc,
            content=content[:50000],  # Cap context
        )

    def review_file(self, filepath: str, domain: str = "general") -> str:
        """Build review prompt from a file."""
        with open(filepath, "r") as f:
            content = f.read()
        return self.build_review_prompt(content, domain)

    @staticmethod
    def parse_review_response(response: str) -> Optional[PeerReview]:
        """Parse LLM response into PeerReview."""
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group(1))
            return PeerReview(
                summary=data.get("Summary", ""),
                strengths=data.get("Strengths", []),
                weaknesses=data.get("Weaknesses", []),
                originality=int(data.get("Originality", 2)),
                quality=int(data.get("Quality", 2)),
                clarity=int(data.get("Clarity", 2)),
                significance=int(data.get("Significance", 2)),
                soundness=int(data.get("Soundness", 2)),
                questions=data.get("Questions", []),
                limitations=data.get("Limitations", []),
                overall=int(data.get("Overall", 5)),
                confidence=int(data.get("Confidence", 3)),
                decision=data.get("Decision", "Revise"),
                suggestions=data.get("Suggestions", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    @staticmethod
    def format_review_markdown(review: PeerReview) -> str:
        """Format review as readable markdown."""
        lines = [
            f"# Peer Review",
            f"",
            f"**Decision: {review.decision}** | Overall: {review.overall}/10 | Confidence: {review.confidence}/5",
            f"",
            f"## Summary",
            review.summary,
            f"",
            f"## Scores",
            f"| Metric | Score |",
            f"|--------|-------|",
            f"| Originality | {review.originality}/4 |",
            f"| Quality | {review.quality}/4 |",
            f"| Clarity | {review.clarity}/4 |",
            f"| Significance | {review.significance}/4 |",
            f"| Soundness | {review.soundness}/4 |",
            f"",
            f"## Strengths",
        ]
        for s in review.strengths:
            lines.append(f"- {s}")

        lines.extend([f"", f"## Weaknesses"])
        for w in review.weaknesses:
            lines.append(f"- {w}")

        if review.suggestions:
            lines.extend([f"", f"## Suggestions"])
            for s in review.suggestions:
                lines.append(f"- {s}")

        if review.questions:
            lines.extend([f"", f"## Questions for Authors"])
            for q in review.questions:
                lines.append(f"- {q}")

        if review.limitations:
            lines.extend([f"", f"## Limitations"])
            for l in review.limitations:
                lines.append(f"- {l}")

        return "\n".join(lines)


# ─── Writeup Generator ───

class WriteupGenerator:
    """
    Generate scientific manuscripts/reports from experimental results.
    Adapted from AI Scientist's perform_writeup.py
    """

    FORMATS = {
        "imrad": {
            "name": "IMRAD (Introduction, Methods, Results, Discussion)",
            "sections": [
                "Abstract",
                "1. Introduction",
                "2. Methods",
                "3. Results",
                "4. Discussion",
                "5. Conclusion",
                "References",
            ],
        },
        "report": {
            "name": "Technical Report",
            "sections": [
                "Executive Summary",
                "1. Background & Motivation",
                "2. Approach",
                "3. Results & Analysis",
                "4. Key Findings",
                "5. Recommendations",
                "6. Next Steps",
                "References",
            ],
        },
        "brief": {
            "name": "Research Brief (2-3 pages)",
            "sections": [
                "Summary",
                "Key Findings",
                "Methods",
                "Implications",
                "References",
            ],
        },
        "patent": {
            "name": "Patent Draft",
            "sections": [
                "Title",
                "Abstract",
                "Field of Invention",
                "Background",
                "Summary of Invention",
                "Detailed Description",
                "Claims",
            ],
        },
    }

    WRITEUP_PROMPT = """You are a scientific writer creating a {format_name}.

TITLE: {title}

EXPERIMENTAL RESULTS & DATA:
{results}

ADDITIONAL CONTEXT:
{context}

Write a complete, well-structured {format_name} with these sections:
{sections}

Requirements:
- Use precise scientific language
- Include specific numbers, metrics, and data from results
- Cite relevant literature where appropriate
- Be thorough but concise — every sentence should add value
- Include limitations and future work
- Format in clean Markdown

Begin writing:
"""

    def build_writeup_prompt(
        self,
        title: str,
        results: str,
        format: str = "imrad",
        context: str = "",
    ) -> str:
        """Build the writeup prompt."""
        fmt = self.FORMATS.get(format, self.FORMATS["imrad"])
        sections = "\n".join(f"- {s}" for s in fmt["sections"])

        return self.WRITEUP_PROMPT.format(
            format_name=fmt["name"],
            title=title,
            results=results[:50000],
            context=context,
            sections=sections,
        )

    def build_writeup_from_dir(
        self,
        title: str,
        results_dir: str,
        format: str = "imrad",
        context: str = "",
    ) -> str:
        """Build writeup prompt by reading all results from a directory."""
        results_parts = []
        if os.path.isdir(results_dir):
            for fname in sorted(os.listdir(results_dir)):
                fpath = os.path.join(results_dir, fname)
                if os.path.isfile(fpath) and fname.endswith((".md", ".txt", ".json", ".csv")):
                    with open(fpath, "r") as f:
                        content = f.read()
                    results_parts.append(f"### {fname}\n{content[:10000]}")

        results = "\n\n".join(results_parts) if results_parts else "No results files found."
        return self.build_writeup_prompt(title, results, format, context)

    @staticmethod
    def extract_references(text: str) -> List[str]:
        """Extract reference citations from text."""
        refs = re.findall(r"\[(\d+)\]", text)
        return sorted(set(refs), key=int)


# ─── Integration Helpers ───

class ARPScientist:
    """
    Main integration class connecting AI Scientist modules with ARP pipeline.

    Maps to ARP phases:
    - Phase 1 (Interview) → IdeaGenerator for structured brainstorming
    - Phase 4 (Review) → PeerReviewer for quality gates
    - Phase 5 (Optimization) → IdeaGenerator.rank_ideas for idea selection
    - Phase 6 (Delivery) → WriteupGenerator for final manuscripts
    """

    def __init__(self):
        self.idea_gen = IdeaGenerator()
        self.reviewer = PeerReviewer()
        self.writer = WriteupGenerator()
        self.ideas_log: List[ResearchIdea] = []
        self.reviews_log: List[PeerReview] = []

    def brainstorm(
        self,
        task: str,
        context: str = "",
        num_ideas: int = 5,
    ) -> List[dict]:
        """Phase 1 enhancement: Generate structured research ideas."""
        existing = [i.title for i in self.ideas_log]
        return self.idea_gen.generate(
            task=task,
            context=context,
            existing_ideas=existing,
            num_ideas=num_ideas,
        )

    def review_milestone(
        self,
        report_path: str,
        domain: str = "general",
    ) -> str:
        """Phase 4 enhancement: Review a milestone report."""
        return self.reviewer.review_file(report_path, domain)

    def quality_gate(self, review: PeerReview, min_score: int = 6) -> dict:
        """Check if work passes quality gate."""
        return {
            "passes": review.overall >= min_score and review.decision != "Reject",
            "score": review.overall,
            "decision": review.decision,
            "action_items": review.suggestions + [
                f"Address weakness: {w}" for w in review.weaknesses[:3]
            ],
        }

    def write_deliverable(
        self,
        title: str,
        results_dir: str,
        format: str = "imrad",
        context: str = "",
    ) -> str:
        """Phase 6 enhancement: Generate final manuscript/report."""
        return self.writer.build_writeup_from_dir(title, results_dir, format, context)

    def full_pipeline_prompts(
        self,
        task: str,
        results_dir: str,
        domain: str = "general",
        format: str = "imrad",
    ) -> dict:
        """
        Get all prompts for a full AI Scientist cycle:
        1. Brainstorm → 2. Execute (external) → 3. Review → 4. Write
        """
        return {
            "1_brainstorm": self.brainstorm(task, num_ideas=5),
            "2_execute": "→ ARP Phase 3 handles execution",
            "3_review": {
                "instruction": "After execution, run review on results",
                "domain": domain,
            },
            "4_writeup": {
                "instruction": "After review passes, generate writeup",
                "results_dir": results_dir,
                "format": format,
            },
        }

    def save_session(self, output_dir: str):
        """Save all ideas and reviews to files."""
        os.makedirs(output_dir, exist_ok=True)

        if self.ideas_log:
            ideas_data = [i.to_dict() for i in self.ideas_log]
            with open(os.path.join(output_dir, "ideas_log.json"), "w") as f:
                json.dump(ideas_data, f, indent=2)

        if self.reviews_log:
            reviews_data = [r.to_dict() for r in self.reviews_log]
            with open(os.path.join(output_dir, "reviews_log.json"), "w") as f:
                json.dump(reviews_data, f, indent=2)


# ─── Convenience Functions ───

def quick_idea(task: str, num: int = 3) -> List[dict]:
    """Quick way to generate idea prompts."""
    gen = IdeaGenerator()
    return gen.generate(task, num_ideas=num, num_reflections=1)


def quick_review(filepath: str, domain: str = "general") -> str:
    """Quick way to build a review prompt."""
    rev = PeerReviewer()
    return rev.review_file(filepath, domain)


def quick_writeup(title: str, results_dir: str, format: str = "imrad") -> str:
    """Quick way to build a writeup prompt."""
    wr = WriteupGenerator()
    return wr.build_writeup_from_dir(title, results_dir, format)
