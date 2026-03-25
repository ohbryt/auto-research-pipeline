"""
HuggingFace Dataset Integration for Auto Research Pipeline (ARP)
- Mount large datasets without local download via hf-mount
- Stream datasets via HuggingFace datasets library
- Upload results to HF Hub
"""
import os
import subprocess
import json
from pathlib import Path

# ─── Configuration ───
HF_CACHE_DIR = os.path.expanduser("~/.cache/huggingface")
HF_MOUNT_BIN = os.path.expanduser("~/.local/bin/hf-mount")

# ─── Key Scientific Datasets on HuggingFace ───
SCIENTIFIC_DATASETS = {
    # Genomics & Bioinformatics
    "InstaDeepAI/multi_species_genomes": "Multi-species genome sequences",
    "InstaDeepAI/nucleotide_transformer_downstream_tasks": "Nucleotide classification tasks",
    "katielink/clinvar": "ClinVar genetic variants",
    "bigbio/pubmed_qa": "PubMed QA dataset",

    # Protein & Drug Discovery
    "bloyal/ProteinGLUE": "Protein function prediction benchmarks",
    "jglaser/binding_affinity": "Protein-ligand binding affinity",
    "sagawa/ogbg-molhiv": "Molecular HIV inhibition",

    # Medical & Clinical
    "bigbio/med_qa": "Medical QA",
    "GBaker/MedQA-USMLE-4-options": "Medical exam QA",
    "pubmed_qa": "PubMed biomedical QA",

    # Finance & Trading
    "yiyanghkust/finbert-tone": "Financial sentiment",
    "financial_phrasebank": "Financial news sentiment",
    "zeroshot/twitter-financial-news-sentiment": "Twitter finance sentiment",
}

class HFDatasetManager:
    """Manage HuggingFace datasets for ARP pipelines"""

    def __init__(self, hf_token=None):
        self.token = hf_token or os.environ.get("HF_TOKEN")

    def mount_repo(self, repo_id, mount_path, repo_type="dataset"):
        """Mount a HF repo as local filesystem via hf-mount (no download)"""
        mount_path = Path(mount_path)
        mount_path.mkdir(parents=True, exist_ok=True)

        cmd = [HF_MOUNT_BIN, "start", "repo", repo_id, str(mount_path)]
        if self.token:
            cmd.extend(["--hf-token", self.token])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[HF] Mounted {repo_id} → {mount_path}")
            return mount_path
        else:
            print(f"[HF] Mount failed: {result.stderr}")
            return None

    def unmount(self, mount_path):
        """Unmount a previously mounted repo"""
        cmd = [HF_MOUNT_BIN, "stop", str(mount_path)]
        subprocess.run(cmd, capture_output=True)
        print(f"[HF] Unmounted {mount_path}")

    def stream_dataset(self, dataset_id, split="train", columns=None):
        """Stream dataset without downloading (uses HF datasets library)"""
        from datasets import load_dataset
        ds = load_dataset(dataset_id, split=split, streaming=True)
        if columns:
            ds = ds.select_columns(columns)
        return ds

    def load_dataset(self, dataset_id, split=None, **kwargs):
        """Load full dataset into memory"""
        from datasets import load_dataset
        return load_dataset(dataset_id, split=split, **kwargs)

    def upload_results(self, local_path, repo_id, repo_type="dataset"):
        """Upload analysis results to HF Hub"""
        from huggingface_hub import HfApi
        api = HfApi(token=self.token)

        # Create repo if not exists
        try:
            api.create_repo(repo_id, repo_type=repo_type, exist_ok=True)
        except Exception as e:
            print(f"[HF] Repo creation note: {e}")

        # Upload
        if os.path.isdir(local_path):
            api.upload_folder(folder_path=local_path, repo_id=repo_id, repo_type=repo_type)
        else:
            api.upload_file(path_or_fileobj=local_path, path_in_repo=os.path.basename(local_path),
                          repo_id=repo_id, repo_type=repo_type)

        print(f"[HF] Uploaded {local_path} → {repo_id}")
        return f"https://huggingface.co/datasets/{repo_id}"

    def list_scientific_datasets(self):
        """List curated scientific datasets"""
        for ds_id, desc in SCIENTIFIC_DATASETS.items():
            print(f"  {ds_id}: {desc}")
        return SCIENTIFIC_DATASETS

    def search_datasets(self, query, limit=10):
        """Search HF Hub for datasets"""
        from huggingface_hub import HfApi
        api = HfApi(token=self.token)
        results = api.list_datasets(search=query, limit=limit, sort="downloads", direction=-1)
        datasets = []
        for ds in results:
            datasets.append({"id": ds.id, "downloads": ds.downloads, "tags": ds.tags[:5] if ds.tags else []})
            print(f"  {ds.id} (downloads: {ds.downloads})")
        return datasets
