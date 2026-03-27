"""
NotebookLM Bridge for ARP v2
==============================
Pattern: Large document corpus → NotebookLM (free, 300 docs, no hallucination)
         Claude Code → generates questions → queries NotebookLM → saves answers locally

This saves massive token costs by keeping document reading in NotebookLM
while Claude Code handles orchestration and question generation only.

Usage:
    from data.notebooklm_bridge import NotebookLMBridge

    bridge = NotebookLMBridge(slug="otub2-literature")

    # Step 1: Generate research questions
    questions = bridge.generate_questions(
        topic="OTUB2 role in hepatic steatosis",
        depth="comprehensive",  # quick(5), standard(15), comprehensive(30)
        categories=["mechanism", "clinical", "therapeutic"]
    )

    # Step 2: Questions saved as markdown for NotebookLM query
    bridge.save_questions("otub2-questions.md")

    # Step 3: After getting answers from NotebookLM, save them
    bridge.save_answers("otub2-answers.md", answers_text)

    # Step 4: Synthesize into structured research notes
    bridge.synthesize("otub2-synthesis.md")
"""

import os
import json
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime


# ─── Question Templates by Domain ───

QUESTION_TEMPLATES = {
    "drug_discovery": {
        "mechanism": [
            "What is the molecular mechanism of {target} in {disease}?",
            "What are the known substrates of {target}?",
            "What signaling pathways does {target} regulate?",
            "How does {target} interact with the ubiquitin-proteasome system?",
            "What post-translational modifications regulate {target} activity?",
            "What is the tissue-specific expression pattern of {target}?",
            "What are the known binding partners of {target}?",
        ],
        "clinical": [
            "What clinical evidence links {target} to {disease}?",
            "How does {target} expression change in patient samples?",
            "Are there any biomarker studies involving {target}?",
            "What are the clinical outcomes associated with {target} dysregulation?",
            "Are there any genetic variants in {target} associated with disease risk?",
        ],
        "therapeutic": [
            "Are there any existing drugs or compounds targeting {target}?",
            "What drug modality is most suitable for {target} (small molecule, antibody, gene therapy)?",
            "What are the safety concerns of modulating {target}?",
            "Are there any ongoing clinical trials involving {target}?",
            "What is the competitive landscape for {target}-directed therapies?",
        ],
        "structural": [
            "What crystal structures are available for {target}?",
            "What are the druggable binding sites on {target}?",
            "How does the structure of {target} compare to related proteins?",
            "What conformational changes occur upon substrate binding?",
        ],
        "preclinical": [
            "What animal models exist for studying {target} in {disease}?",
            "What phenotype results from {target} knockout in mice?",
            "What in vitro assays are used to measure {target} activity?",
            "What are the key readouts for {target} modulation in cell models?",
        ],
    },
    "genomics": {
        "expression": [
            "What are the expression patterns of {target} across tissues?",
            "How does {target} expression change with age?",
            "What transcription factors regulate {target}?",
            "Are there alternative splice variants of {target}?",
        ],
        "regulation": [
            "What epigenetic marks are associated with {target} promoter?",
            "Are there known enhancers or silencers for {target}?",
            "What miRNAs target {target} mRNA?",
            "How is {target} regulated at the post-transcriptional level?",
        ],
        "network": [
            "What gene networks include {target}?",
            "What are the co-expressed genes with {target}?",
            "What pathway enrichment is associated with {target} perturbation?",
        ],
    },
    "general": {
        "overview": [
            "What is {target} and what is its primary function?",
            "What is the current state of research on {target}?",
            "What are the major unanswered questions about {target}?",
            "What controversies exist in the {target} field?",
            "What recent breakthroughs have been made regarding {target}?",
        ],
        "connections": [
            "How does {target} relate to {disease}?",
            "What interdisciplinary approaches are being used to study {target}?",
            "What technological advances have enabled new insights into {target}?",
        ],
    },
}


@dataclass
class ResearchQuestion:
    """A structured research question."""
    id: int
    category: str
    question: str
    priority: str = "standard"  # critical, standard, exploratory
    answer: str = ""
    source: str = ""
    status: str = "pending"  # pending, answered, blocked, skipped


class NotebookLMBridge:
    """
    Bridge between Claude Code and NotebookLM for cost-effective literature research.

    Workflow:
    1. Claude Code generates targeted questions (cheap - prompt only)
    2. User uploads documents to NotebookLM (free - up to 300 docs)
    3. Questions are asked in NotebookLM (free - grounded answers, no hallucination)
    4. Answers saved locally as markdown (free)
    5. Claude Code synthesizes answers into research output (cheap - structured input)

    Cost comparison:
    - Direct Claude reading of 100 papers: ~$50-200 in tokens
    - NotebookLM bridge approach: ~$2-5 (question generation + synthesis only)
    """

    def __init__(self, slug: str, output_dir: str = "outputs/.notebooklm"):
        self.slug = slug
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.questions: List[ResearchQuestion] = []

    # ── Question Generation ──

    def generate_questions(
        self,
        topic: str,
        target: str = "",
        disease: str = "",
        domain: str = "drug_discovery",
        depth: str = "standard",
        categories: Optional[List[str]] = None,
        custom_questions: Optional[List[str]] = None,
    ) -> List[ResearchQuestion]:
        """
        Generate research questions for NotebookLM querying.

        Args:
            topic: Research topic
            target: Target gene/protein (e.g., "OTUB2")
            disease: Disease context (e.g., "MASLD")
            domain: Question domain template to use
            depth: "quick" (5-8), "standard" (15-20), "comprehensive" (25-35)
            categories: Specific categories to include
            custom_questions: Additional custom questions
        """
        if not target:
            target = topic.split()[0]  # Rough extraction
        if not disease:
            disease = "the disease context"

        templates = QUESTION_TEMPLATES.get(domain, QUESTION_TEMPLATES["general"])

        # Select categories
        if categories:
            selected_cats = {k: v for k, v in templates.items() if k in categories}
        else:
            selected_cats = templates

        # Depth limits
        depth_limits = {"quick": 8, "standard": 20, "comprehensive": 35}
        max_q = depth_limits.get(depth, 20)

        # Generate questions
        questions = []
        q_id = 1

        for category, template_list in selected_cats.items():
            for template in template_list:
                if len(questions) >= max_q:
                    break
                q_text = template.format(target=target, disease=disease)
                priority = "critical" if category in ["mechanism", "clinical", "overview"] else "standard"
                questions.append(ResearchQuestion(
                    id=q_id,
                    category=category,
                    question=q_text,
                    priority=priority,
                ))
                q_id += 1

        # Add custom questions
        if custom_questions:
            for cq in custom_questions:
                questions.append(ResearchQuestion(
                    id=q_id,
                    category="custom",
                    question=cq,
                    priority="critical",
                ))
                q_id += 1

        self.questions = questions
        return questions

    # ── Question Generation Prompt (for LLM) ──

    QUESTION_GEN_PROMPT = """You are generating research questions for a literature review.

TOPIC: {topic}
TARGET: {target}
DISEASE: {disease}
DOMAIN: {domain}
DEPTH: {depth} ({max_q} questions)

Generate {max_q} targeted, specific research questions organized by category.
Questions should be:
- Answerable from published literature
- Specific enough to get useful answers (not "tell me about X")
- Ordered by priority (most critical first)
- Cover different angles: mechanism, clinical evidence, therapeutic potential, structural, preclinical

Format each question as:
[CATEGORY] Q<number>. (priority) Question text

Categories: mechanism, clinical, therapeutic, structural, preclinical, safety, competitive
Priorities: critical, standard, exploratory
"""

    def build_question_gen_prompt(
        self,
        topic: str,
        target: str,
        disease: str,
        domain: str = "drug_discovery",
        depth: str = "standard",
    ) -> str:
        """Build prompt for LLM-generated questions (more creative than templates)."""
        depth_limits = {"quick": 8, "standard": 20, "comprehensive": 35}
        return self.QUESTION_GEN_PROMPT.format(
            topic=topic,
            target=target,
            disease=disease,
            domain=domain,
            depth=depth,
            max_q=depth_limits.get(depth, 20),
        )

    # ── Save/Load ──

    def save_questions(self, filename: Optional[str] = None) -> str:
        """Save questions as markdown for NotebookLM querying."""
        if filename is None:
            filename = f"{self.slug}-questions.md"
        path = os.path.join(self.output_dir, filename)

        lines = [
            f"# Research Questions: {self.slug}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Total: {len(self.questions)} questions",
            "",
            "---",
            "",
            "**Instructions:** Copy each question into NotebookLM and paste the answer below it.",
            "",
        ]

        current_cat = ""
        for q in self.questions:
            if q.category != current_cat:
                current_cat = q.category
                lines.append(f"## {current_cat.title()}")
                lines.append("")

            priority_marker = "🔴" if q.priority == "critical" else "🟡" if q.priority == "standard" else "🟢"
            lines.append(f"### Q{q.id}. {priority_marker} {q.question}")
            lines.append("")
            lines.append("**Answer:**")
            lines.append("")
            lines.append("_(paste NotebookLM answer here)_")
            lines.append("")
            lines.append("---")
            lines.append("")

        with open(path, "w") as f:
            f.write("\n".join(lines))

        return path

    def save_answers(self, filename: Optional[str] = None, answers_text: str = "") -> str:
        """Save answered questions."""
        if filename is None:
            filename = f"{self.slug}-answers.md"
        path = os.path.join(self.output_dir, filename)

        with open(path, "w") as f:
            f.write(answers_text)
        return path

    def load_answers(self, filepath: str) -> List[ResearchQuestion]:
        """Parse answered questions from markdown."""
        with open(filepath) as f:
            content = f.read()

        # Simple parsing: find Q{n} headers and their answers
        import re
        blocks = re.split(r"### Q(\d+)\.", content)

        for i in range(1, len(blocks), 2):
            q_id = int(blocks[i])
            text = blocks[i + 1] if i + 1 < len(blocks) else ""

            # Extract answer
            answer_match = re.search(r"\*\*Answer:\*\*\s*(.*?)(?=---|\Z)", text, re.DOTALL)
            if answer_match:
                answer = answer_match.group(1).strip()
                if answer and answer != "_(paste NotebookLM answer here)_":
                    for q in self.questions:
                        if q.id == q_id:
                            q.answer = answer
                            q.status = "answered"
                            break

        return self.questions

    # ── Synthesis ──

    SYNTHESIS_PROMPT = """You are synthesizing research findings from a literature review.

TOPIC: {topic}

The following questions were asked and answered using NotebookLM (grounded in uploaded papers, no hallucination):

{qa_pairs}

Synthesize these into a structured research summary:

1. **Key Findings** — What are the most important discoveries?
2. **Consensus** — What do sources agree on?
3. **Disagreements** — Where do sources conflict?
4. **Gaps** — What questions remain unanswered?
5. **Implications** — What do these findings mean for {target}?
6. **Recommended Next Steps** — What should be investigated next?

Be specific. Cite question numbers [Q1], [Q2] etc. when referencing findings.
"""

    def build_synthesis_prompt(self, topic: str, target: str = "") -> str:
        """Build synthesis prompt from answered questions."""
        qa_pairs = []
        for q in self.questions:
            if q.status == "answered" and q.answer:
                qa_pairs.append(f"**Q{q.id} [{q.category}]:** {q.question}\n**A:** {q.answer}\n")

        if not qa_pairs:
            return "No answered questions available for synthesis."

        return self.SYNTHESIS_PROMPT.format(
            topic=topic,
            target=target or topic,
            qa_pairs="\n".join(qa_pairs),
        )

    # ── Document Preparation Guide ──

    @staticmethod
    def document_prep_guide(topic: str, target: str = "") -> str:
        """Generate a guide for what documents to upload to NotebookLM."""
        return f"""# NotebookLM Document Preparation Guide

## Topic: {topic}

### Step 1: Collect Documents (aim for 50-300)

**Priority sources:**
- PubMed search: "{target}" AND relevant disease terms → download PDFs
- Review articles on {target} (last 3 years)
- Key primary research papers cited in reviews
- Preprints from bioRxiv/medRxiv

**Database exports:**
- GeneCards page for {target} → save as PDF
- UniProt entry for {target} → save as PDF
- Open Targets page → save as PDF
- STRING interaction network → save as PDF

**Patent literature:**
- Google Patents search for {target} → save relevant patents as PDF

### Step 2: Convert to Markdown (if needed)
- PDFs: upload directly to NotebookLM (supported natively)
- Web pages: use Obsidian Web Clipper → markdown
- YouTube lectures: use YouTube-to-NotebookLM extension

### Step 3: Upload to NotebookLM
1. Go to notebooklm.google.com
2. Create new notebook: "{topic}"
3. Upload all collected documents (max 300)
4. Wait for processing

### Step 4: Query with Generated Questions
- Copy questions from {target}-questions.md
- Paste each into NotebookLM chat
- Copy answers back to {target}-answers.md

### Step 5: Return to Claude Code
- Claude Code synthesizes all answers into structured research output
- Total token cost: ~$2-5 (vs $50-200 for direct document reading)
"""

    # ── Stats ──

    def stats(self) -> Dict:
        """Get question/answer statistics."""
        total = len(self.questions)
        answered = sum(1 for q in self.questions if q.status == "answered")
        critical = sum(1 for q in self.questions if q.priority == "critical")
        critical_answered = sum(1 for q in self.questions
                               if q.priority == "critical" and q.status == "answered")

        return {
            "total_questions": total,
            "answered": answered,
            "pending": total - answered,
            "completion": f"{answered/total:.0%}" if total > 0 else "0%",
            "critical_total": critical,
            "critical_answered": critical_answered,
            "categories": list(set(q.category for q in self.questions)),
        }


# ─── Convenience Functions ───

def quick_questions(topic: str, target: str, disease: str = "", depth: str = "standard") -> str:
    """Quick way to generate questions and save them."""
    bridge = NotebookLMBridge(slug=target.lower())
    bridge.generate_questions(topic, target, disease, depth=depth)
    path = bridge.save_questions()
    return path


def prep_guide(topic: str, target: str = "") -> str:
    """Get the document preparation guide."""
    return NotebookLMBridge.document_prep_guide(topic, target)
