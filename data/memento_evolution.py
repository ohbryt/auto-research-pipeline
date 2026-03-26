"""
Memento-Inspired Self-Evolution for ARP v2
=============================================
Adapted from Memento-Teams/Memento-Skills (MIT License)

Core pattern: Read → Execute → Reflect → Write
- Skills/approaches that fail get reflected on and rewritten
- Utility scores track which approaches work
- The pipeline learns from its own failures

Usage:
    from data.memento_evolution import ReflectionEngine, SkillTracker

    # After each milestone
    engine = ReflectionEngine()
    decision = engine.reflect(
        plan=current_plan,
        step="M3: Allosteric screening",
        result="Docking returned 0 hits above threshold",
        remaining=["M4", "M5", "M6"]
    )
    # → ReflectionDecision.REPLAN with reason and next_step_hint

    # Track approach utility
    tracker = SkillTracker("otub2-activator")
    tracker.log("virtual_screening_zinc", success=False, reason="No hits > -6.0 kcal/mol")
    tracker.log("fragment_screen_enamine", success=True, reason="3 hits found")
    tracker.suggest_rewrite("virtual_screening_zinc")
    # → Returns rewrite suggestions based on failure patterns
"""

import os
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


# ─── Reflection Engine ───

class ReflectionDecision(str, Enum):
    CONTINUE = "continue"    # Step succeeded, proceed to next
    REPLAN = "replan"        # Step failed or revealed new info, revise plan
    FINALIZE = "finalize"    # All goals met, wrap up


@dataclass
class ReflectionResult:
    """Output of step-level reflection."""
    decision: ReflectionDecision
    reason: str
    next_step_hint: Optional[str] = None
    completed_step_id: Optional[str] = None
    replan_scope: Optional[str] = None  # "step" | "phase" | "full"
    confidence: float = 0.5  # 0-1


class ReflectionEngine:
    """
    Post-execution reflection: decide whether to continue, replan, or finalize.
    Inspired by Memento's Read-Execute-Reflect-Write loop.
    """

    REFLECT_PROMPT = """You are a research project manager reflecting on a completed step.

## Current Plan
{plan}

## Completed Step
{step}

## Step Result
{result}

## Remaining Steps
{remaining}

## Failed Approaches So Far
{failures}

Analyze the result and decide:

1. **CONTINUE** — Step succeeded. Proceed to next step as planned.
   - Use when: result meets expectations, no new information changes the plan

2. **REPLAN** — Step revealed something unexpected. Revise before continuing.
   - Use when: result contradicts assumptions, new approach needed, scope change
   - Specify: replan "step" (just next step), "phase" (current phase), or "full" (entire plan)

3. **FINALIZE** — All essential goals are met or further work has diminishing returns.
   - Use when: success criteria satisfied, or remaining steps are no longer valuable

Respond as JSON:
```json
{{
  "decision": "continue|replan|finalize",
  "reason": "why this decision",
  "next_step_hint": "what to do next (if replan)",
  "replan_scope": "step|phase|full (if replan)",
  "confidence": 0.0-1.0
}}
```
"""

    def build_reflect_prompt(
        self,
        plan: str,
        step: str,
        result: str,
        remaining: List[str],
        failures: Optional[List[str]] = None,
    ) -> str:
        """Build reflection prompt for LLM."""
        return self.REFLECT_PROMPT.format(
            plan=plan,
            step=step,
            result=result[:5000],
            remaining="\n".join(f"- {r}" for r in remaining) or "(none)",
            failures="\n".join(f"- {f}" for f in (failures or [])) or "(none)",
        )

    @staticmethod
    def parse_reflection(response: str) -> ReflectionResult:
        """Parse LLM reflection response."""
        import re
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return ReflectionResult(
                    decision=ReflectionDecision(data.get("decision", "continue")),
                    reason=data.get("reason", ""),
                    next_step_hint=data.get("next_step_hint"),
                    replan_scope=data.get("replan_scope"),
                    confidence=float(data.get("confidence", 0.5)),
                )
            except (json.JSONDecodeError, ValueError):
                pass
        return ReflectionResult(
            decision=ReflectionDecision.CONTINUE,
            reason="Could not parse reflection, defaulting to continue",
        )


# ─── Skill/Approach Utility Tracker ───

@dataclass
class ApproachRecord:
    """Record of an approach attempt."""
    name: str
    timestamp: str
    success: bool
    reason: str
    duration_minutes: Optional[float] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApproachProfile:
    """Accumulated profile of an approach."""
    name: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    utility_score: float = 0.5  # 0-1, starts neutral
    failure_reasons: List[str] = field(default_factory=list)
    success_reasons: List[str] = field(default_factory=list)
    last_used: str = ""
    status: str = "active"  # active | deprecated | rewritten

    @property
    def success_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.successes / self.attempts

    def update_utility(self):
        """Update utility score based on success/failure history."""
        if self.attempts == 0:
            self.utility_score = 0.5
            return
        # Weighted: recent attempts matter more
        base = self.success_rate
        # Penalty for repeated failures
        consecutive_fails = 0
        for r in reversed(self.failure_reasons):
            consecutive_fails += 1
            if consecutive_fails >= 3:
                break
        fail_penalty = min(0.3, consecutive_fails * 0.1)
        self.utility_score = max(0.0, min(1.0, base - fail_penalty))


class SkillTracker:
    """
    Track utility of different approaches/skills over time.
    Inspired by Memento's skill utility scoring.
    """

    def __init__(self, project_slug: str, tracker_dir: str = "outputs/.tracker"):
        self.project_slug = project_slug
        self.tracker_dir = tracker_dir
        self.tracker_file = os.path.join(tracker_dir, f"{project_slug}-tracker.json")
        os.makedirs(tracker_dir, exist_ok=True)
        self.profiles: Dict[str, ApproachProfile] = {}
        self.history: List[ApproachRecord] = []
        self._load()

    def _load(self):
        if os.path.exists(self.tracker_file):
            with open(self.tracker_file) as f:
                data = json.load(f)
                for name, profile_data in data.get("profiles", {}).items():
                    self.profiles[name] = ApproachProfile(**profile_data)
                for record_data in data.get("history", []):
                    self.history.append(ApproachRecord(**record_data))

    def _save(self):
        data = {
            "project": self.project_slug,
            "updated": datetime.now().isoformat(),
            "profiles": {k: asdict(v) for k, v in self.profiles.items()},
            "history": [asdict(r) for r in self.history[-100:]],  # Keep last 100
        }
        with open(self.tracker_file, "w") as f:
            json.dump(data, f, indent=2)

    def log(self, approach: str, success: bool, reason: str = "",
            duration_minutes: float = None, metrics: Dict = None):
        """Log an approach attempt."""
        # Record
        record = ApproachRecord(
            name=approach,
            timestamp=datetime.now().isoformat(),
            success=success,
            reason=reason,
            duration_minutes=duration_minutes,
            metrics=metrics or {},
        )
        self.history.append(record)

        # Update profile
        if approach not in self.profiles:
            self.profiles[approach] = ApproachProfile(name=approach)

        profile = self.profiles[approach]
        profile.attempts += 1
        profile.last_used = record.timestamp
        if success:
            profile.successes += 1
            if reason:
                profile.success_reasons.append(reason)
        else:
            profile.failures += 1
            if reason:
                profile.failure_reasons.append(reason)
        profile.update_utility()

        self._save()
        return profile

    def get_utility(self, approach: str) -> float:
        """Get current utility score for an approach."""
        if approach in self.profiles:
            return self.profiles[approach].utility_score
        return 0.5  # Unknown

    def rank_approaches(self) -> List[ApproachProfile]:
        """Rank all approaches by utility score."""
        return sorted(self.profiles.values(), key=lambda x: x.utility_score, reverse=True)

    def suggest_rewrite(self, approach: str) -> Dict:
        """Suggest how to rewrite a failing approach."""
        if approach not in self.profiles:
            return {"suggestion": "No data available for this approach"}

        profile = self.profiles[approach]
        if profile.utility_score >= 0.6:
            return {"suggestion": "Approach is performing well, no rewrite needed"}

        # Analyze failure patterns
        failure_analysis = {
            "approach": approach,
            "utility_score": profile.utility_score,
            "success_rate": f"{profile.success_rate:.0%}",
            "total_attempts": profile.attempts,
            "failure_reasons": profile.failure_reasons[-5:],  # Last 5
            "suggestions": [],
        }

        # Generate suggestions based on failure patterns
        reasons = " ".join(profile.failure_reasons).lower()

        if "no hits" in reasons or "0 results" in reasons:
            failure_analysis["suggestions"].append(
                "Expand search space: use broader query terms, larger compound library, or relaxed thresholds"
            )
        if "timeout" in reasons or "too slow" in reasons:
            failure_analysis["suggestions"].append(
                "Reduce computation: use faster method, smaller dataset, or pre-filter candidates"
            )
        if "false positive" in reasons or "not selective" in reasons:
            failure_analysis["suggestions"].append(
                "Add counter-screens or selectivity filters before advancing hits"
            )
        if "poor binding" in reasons or "weak affinity" in reasons:
            failure_analysis["suggestions"].append(
                "Try different binding site, use fragment-based approach, or consider covalent strategy"
            )
        if not failure_analysis["suggestions"]:
            failure_analysis["suggestions"].append(
                f"Review failure reasons and consider alternative approach. "
                f"Most common failure: {profile.failure_reasons[-1] if profile.failure_reasons else 'unknown'}"
            )

        # Mark as deprecated if utility too low
        if profile.utility_score < 0.2 and profile.attempts >= 3:
            profile.status = "deprecated"
            failure_analysis["action"] = "DEPRECATE — approach consistently fails. Try fundamentally different strategy."
        else:
            failure_analysis["action"] = "REWRITE — modify parameters and retry"

        self._save()
        return failure_analysis

    def should_try(self, approach: str) -> bool:
        """Should we try this approach or skip it?"""
        if approach not in self.profiles:
            return True  # Unknown, try it
        profile = self.profiles[approach]
        if profile.status == "deprecated":
            return False
        if profile.utility_score < 0.2 and profile.attempts >= 3:
            return False
        return True

    def summary(self) -> str:
        """Human-readable summary of all approach utilities."""
        lines = [f"# Approach Tracker: {self.project_slug}\n"]
        lines.append(f"Total approaches: {len(self.profiles)}")
        lines.append(f"Total attempts: {sum(p.attempts for p in self.profiles.values())}\n")

        ranked = self.rank_approaches()
        lines.append("| Approach | Utility | Attempts | Success Rate | Status |")
        lines.append("|---|---|---|---|---|")
        for p in ranked:
            lines.append(
                f"| {p.name} | {p.utility_score:.2f} | {p.attempts} | "
                f"{p.success_rate:.0%} | {p.status} |"
            )

        deprecated = [p for p in ranked if p.status == "deprecated"]
        if deprecated:
            lines.append(f"\nDeprecated approaches ({len(deprecated)}):")
            for p in deprecated:
                lines.append(f"  - {p.name}: {', '.join(p.failure_reasons[-2:])}")

        return "\n".join(lines)


# ─── Self-Evolution Integration ───

class ARPEvolution:
    """
    Integrates reflection and skill tracking into ARP pipeline.

    Usage in ARP execution loop:
        evo = ARPEvolution("otub2-activator")

        # After each milestone:
        result = evo.post_milestone(
            milestone="M3",
            outcome="Found 3 allosteric hits",
            success=True,
            approach="virtual_screening_zinc"
        )

        if result["decision"] == "replan":
            # Revise plan based on reflection
            ...
    """

    def __init__(self, project_slug: str):
        self.slug = project_slug
        self.reflector = ReflectionEngine()
        self.tracker = SkillTracker(project_slug)

    def post_milestone(
        self,
        milestone: str,
        outcome: str,
        success: bool,
        approach: str = "",
        plan: str = "",
        remaining: List[str] = None,
    ) -> Dict:
        """Call after each milestone. Returns decision + updated utility."""

        # 1. Log approach
        if approach:
            profile = self.tracker.log(approach, success, reason=outcome)
        else:
            profile = None

        # 2. Build reflection prompt
        reflect_prompt = self.reflector.build_reflect_prompt(
            plan=plan,
            step=milestone,
            result=outcome,
            remaining=remaining or [],
            failures=[
                f"{p.name}: {p.failure_reasons[-1]}"
                for p in self.tracker.profiles.values()
                if p.failures > 0 and p.failure_reasons
            ],
        )

        # 3. Auto-decide if obvious
        if success and (remaining is None or len(remaining or []) > 0):
            decision = ReflectionDecision.CONTINUE
            reason = "Step succeeded, proceeding"
        elif not success and profile and profile.utility_score < 0.2:
            decision = ReflectionDecision.REPLAN
            reason = f"Approach '{approach}' has low utility ({profile.utility_score:.2f}). Consider alternative."
        elif remaining is not None and len(remaining) == 0:
            decision = ReflectionDecision.FINALIZE
            reason = "All steps completed"
        else:
            # Need LLM reflection for ambiguous cases
            decision = ReflectionDecision.CONTINUE
            reason = "Default to continue — use reflect_prompt for LLM-guided decision"

        # 4. Check if rewrite suggested
        rewrite = None
        if not success and approach:
            rewrite = self.tracker.suggest_rewrite(approach)

        return {
            "decision": decision.value,
            "reason": reason,
            "reflect_prompt": reflect_prompt,
            "approach_utility": profile.utility_score if profile else None,
            "should_retry": self.tracker.should_try(approach) if approach else True,
            "rewrite_suggestion": rewrite,
            "tracker_summary": self.tracker.summary(),
        }

    def get_best_approach(self, candidates: List[str]) -> Optional[str]:
        """Pick the best approach from candidates based on utility history."""
        viable = [(c, self.tracker.get_utility(c))
                  for c in candidates if self.tracker.should_try(c)]
        if not viable:
            return None
        # Sort by utility, highest first
        viable.sort(key=lambda x: x[1], reverse=True)
        return viable[0][0]

    def changelog_entry(self, milestone: str, outcome: str, decision: str) -> str:
        """Generate a CHANGELOG entry."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"\n## {now} — {milestone}\n- Outcome: {outcome}\n- Decision: {decision}\n- Approach utilities:\n{self.tracker.summary()}\n"
