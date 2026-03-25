"""
LigandForge Integration for Auto Research Pipeline (ARP)

Based on: "Single-Pass Discrete Diffusion Predicts High-Affinity Peptide Binders
at >1,000 Sequences per Second across 150 Receptor Targets"
(Watson, 2026 - bioRxiv 10.64898/2026.03.14.711748)

LigandForge: Discrete diffusion model for de novo peptide design
- >700 seq/sec on single GPU (peak >1,000)
- 10,000x faster than BoltzGen, 1,000,000x faster than BindCraft
- No structure prediction needed at inference
- Sub-100nM binders for 73% of targets

DeltaForge: Rust-based thermodynamic scoring engine
- Pearson r = 0.83 on PPB-Affinity peptide benchmark
- Predicts binding free energy (ΔG) and Kd
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional

# LigandForge API (Ligandal, Inc.)
LIGANDAI_URL = "https://ligandai.com"

# Comparison benchmarks from the paper
BENCHMARKS = {
    "LigandForge": {"speed": ">700 seq/sec", "method": "discrete diffusion", "structure_free": True},
    "BoltzGen": {"speed": "~0.07 seq/sec", "method": "Boltzmann generator", "structure_free": False},
    "BindCraft": {"speed": "~0.0007 seq/sec", "method": "backbone sampling", "structure_free": False},
}

# Paper's validated targets with results
PAPER_TARGETS = {
    "TNF-α": {"best_dG": -11.97, "sub100nM": 3, "note": "AlphaProteo failed"},
    "PD-L1": {"best_dG": -9.84, "sub100nM": 2, "note": "BindCraft 0% peptide"},
    "VEGF-A": {"best_dG": None, "sub100nM": None, "note": "Cystine-knot homodimer"},
    "IL-7Rα": {"best_dG": -10.84, "sub100nM": 13, "note": "CD127"},
    "HER2": {"best_dG": -10.15, "sub100nM": 2, "note": "BindCraft 0 trajectories"},
    "GRIN1": {"best_dG": -11.2, "sub100nM": 32, "best_Kd_nM": 6.3},
    "CD8AB": {"best_dG": -15.0, "sub100nM": 127, "note": "Heterodimer, 19.5% dual-chain"},
    "FURIN": {"best_dG": -13.3, "sub100nM": 31, "best_Kd_nM": 0.18},
    "CD8A": {"best_dG": -13.7, "sub100nM": 52, "best_Kd_nM": 0.09},
    "CD3D/CD3E": {"best_dG": None, "sub100nM": None, "best_Kd_nM": 0.2},
}

# Structural diversity from paper (DSSP analysis)
STRUCTURAL_DIVERSITY = {
    "LigandForge": {"helical": 69, "beta_sheet": 9, "mixed": 4, "multi_domain": 8, "coil": 10},
    "BoltzGen": {"helical": 77, "other": 23},
    "BindCraft": {"helical": 93, "other": 7},
}


class LigandForgeManager:
    """
    Interface to LigandForge peptide design capabilities.

    For ARP drug discovery pipelines:
    1. Define receptor target (PDB structure or AlphaFold model)
    2. Generate candidate peptides (hundreds of thousands in minutes)
    3. Score with DeltaForge thermodynamics
    4. Filter by Kd threshold
    5. Validate top hits with Boltz-2 structure prediction
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("LIGANDAI_API_KEY")
        self.results_dir = Path("data/ligandforge_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def design_peptides_local(self, target_pdb: str, n_candidates: int = 1000,
                               kd_threshold_nM: float = 100.0) -> dict:
        """
        Design peptide binders using local LigandForge installation.

        Args:
            target_pdb: Path to receptor PDB file or PDB ID
            n_candidates: Number of candidates to generate
            kd_threshold_nM: Kd threshold for filtering (nM)

        Returns:
            dict with designed peptides and scores

        Note: Requires local LigandForge installation (proprietary).
        For access, contact: https://ligandai.com
        """
        return {
            "status": "requires_ligandforge_installation",
            "target": target_pdb,
            "n_requested": n_candidates,
            "estimated_time_sec": n_candidates / 700,  # ~700 seq/sec
            "contact": LIGANDAI_URL,
            "note": "LigandForge is proprietary (Ligandal, Inc.). "
                    "Contact for API access or local installation."
        }

    def estimate_throughput(self, n_candidates: int, gpu: str = "B200") -> dict:
        """Estimate generation time based on paper benchmarks."""
        speeds = {"B200": 732, "A100": 500, "H100": 600, "V100": 300}  # estimated
        speed = speeds.get(gpu, 500)
        time_sec = n_candidates / speed
        return {
            "n_candidates": n_candidates,
            "gpu": gpu,
            "speed_seq_per_sec": speed,
            "estimated_time_sec": round(time_sec, 1),
            "estimated_time_min": round(time_sec / 60, 1),
            "comparison": {
                "BoltzGen_time_sec": round(n_candidates / 0.07, 0),
                "BindCraft_time_sec": round(n_candidates / 0.0007, 0),
            }
        }

    def score_peptide_deltaforge(self, peptide_seq: str, target_pdb: str) -> dict:
        """
        Score peptide binding using DeltaForge thermodynamic engine.

        Note: Requires DeltaForge installation (proprietary Rust binary).
        Returns placeholder with scoring methodology description.
        """
        return {
            "status": "requires_deltaforge_installation",
            "peptide": peptide_seq,
            "target": target_pdb,
            "scoring_method": "Thermodynamic free energy (ΔG)",
            "benchmark_correlation": "Pearson r = 0.83 (PPB-Affinity)",
            "metrics": ["ΔG (kcal/mol)", "predicted Kd (nM)", "iPSAE confidence"],
            "contact": LIGANDAI_URL,
        }

    def get_paper_results(self, target: Optional[str] = None) -> dict:
        """Get published results from the LigandForge paper."""
        if target:
            return PAPER_TARGETS.get(target, {"error": f"Target {target} not in paper"})
        return PAPER_TARGETS

    def suggest_pipeline(self, targets: list, budget_gpu_hours: float = 1.0) -> dict:
        """
        Suggest a LigandForge pipeline for given targets.

        Args:
            targets: List of target names/PDB IDs
            budget_gpu_hours: Available GPU compute budget

        Returns:
            Recommended pipeline with candidate counts per target
        """
        total_gpu_sec = budget_gpu_hours * 3600
        seq_per_sec = 700  # conservative estimate
        total_candidates = int(total_gpu_sec * seq_per_sec)
        per_target = total_candidates // max(len(targets), 1)

        pipeline = {
            "targets": targets,
            "n_targets": len(targets),
            "gpu_hours": budget_gpu_hours,
            "total_candidates": total_candidates,
            "per_target": per_target,
            "pipeline_steps": [
                {
                    "step": 1,
                    "name": "Generate candidates",
                    "tool": "LigandForge",
                    "output": f"{per_target} peptides/target",
                    "time": f"~{per_target/700:.0f}s/target",
                },
                {
                    "step": 2,
                    "name": "Structure prediction",
                    "tool": "Boltz-2",
                    "input": "Top 10% by sequence score",
                    "output": "3D structures",
                },
                {
                    "step": 3,
                    "name": "Thermodynamic scoring",
                    "tool": "DeltaForge",
                    "output": "ΔG, predicted Kd",
                },
                {
                    "step": 4,
                    "name": "Filter hits",
                    "criteria": "Kd < 100 nM, iPSAE > 0.5",
                    "expected_hits": f"~{int(per_target * 0.05)}/target (5% hit rate)",
                },
                {
                    "step": 5,
                    "name": "Experimental validation",
                    "tool": "SPR/BLI binding assay",
                    "input": "Top 3-5 per target",
                },
            ],
            "expected_hit_rate": "73% of targets with sub-100nM binder (paper benchmark)",
            "note": "Requires LigandForge + DeltaForge installation. Contact ligandai.com"
        }
        return pipeline

    def compare_with_arp_peptides(self, arp_peptides: list) -> dict:
        """
        Compare ARP-designed peptides with LigandForge capabilities.

        Shows what LigandForge could add to existing ARP pipeline.
        """
        n_arp = len(arp_peptides)
        return {
            "arp_peptides": n_arp,
            "arp_method": "Computational design (manual/rule-based)",
            "arp_speed": f"~{n_arp} peptides in hours",
            "ligandforge_advantage": {
                "speed": f"Could generate {n_arp * 10000} candidates in same time",
                "coverage": "Explores 10,000x more sequence space",
                "diversity": "69% helical + 9% β-sheet + 4% mixed + 8% multi-domain",
                "scoring": "DeltaForge ΔG (r=0.83 vs experimental)",
                "difficult_targets": "Can hit TNF-α, PD-L1, KRAS (historically undruggable)",
            },
            "recommendation": (
                "Use ARP pipeline for target identification (Stage 1-2), "
                "then LigandForge for massive-scale peptide generation (Stage 3+). "
                "DeltaForge replaces manual binding prediction."
            ),
        }


def get_ligandforge_info():
    """Quick reference for LigandForge capabilities."""
    return {
        "name": "LigandForge",
        "paper": "Watson, 2026. bioRxiv 10.64898/2026.03.14.711748",
        "url": LIGANDAI_URL,
        "type": "Discrete diffusion model for de novo peptide design",
        "speed": ">700 seq/sec (peak >1,000) on single GPU",
        "advantage": "10,000x BoltzGen, 1,000,000x BindCraft",
        "key_feature": "Structure-free inference — no 3D prediction needed",
        "validation": "490,691 peptides, 150 targets, 73% with sub-100nM binders",
        "scoring": "DeltaForge (Rust, r=0.83 vs experimental binding data)",
        "diversity": STRUCTURAL_DIVERSITY["LigandForge"],
        "company": "Ligandal, Inc.",
        "status": "Proprietary — contact for access",
    }
