#!/usr/bin/env python3
"""
build_merged_dataset.py
=======================
Merges all three dataset components into one final training set:
  1. arapai_synthetic_20k.jsonl      — 20,000 synthetic Africa cases
  2. medqa_filtered.jsonl            — MedQA USMLE filtered
  3. medmcqa_filtered.jsonl          — MedMCQA filtered (capped 10k)

Mix ratio: 60% synthetic (Africa-specific) + 40% real MCQ data
Final target: ~30,000 samples

Also writes:
  arapai_final_train.jsonl           — shuffled merged training set
  arapai_final_eval.jsonl            — 10% held-out evaluation set
  dataset_manifest.json              — full statistics for paper
"""

import json, random, os
from pathlib import Path
from collections import Counter
from datetime import datetime

random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────
# On Colab: datasets saved to Drive during download pipeline
# On Mac Studio: use local arapai_output
DRIVE = Path("/content/drive/MyDrive/arapai_output")
LOCAL = Path.home() / "arapai_output"
BASE  = DRIVE if DRIVE.exists() else LOCAL

DATASET_DIR = BASE / "datasets"
OUTPUT_DIR  = BASE / "datasets"
DATASET_DIR.mkdir(parents=True, exist_ok=True)

SYNTHETIC_PATH  = DATASET_DIR / "arapai_synthetic_20k.jsonl"
MEDQA_PATH      = DATASET_DIR / "medqa_filtered.jsonl"
MEDMCQA_PATH    = DATASET_DIR / "medmcqa_filtered.jsonl"
TRAIN_OUT       = DATASET_DIR / "arapai_final_train.jsonl"
EVAL_OUT        = DATASET_DIR / "arapai_final_eval.jsonl"
MANIFEST_PATH   = DATASET_DIR / "dataset_manifest.json"

def load_jsonl(path):
    if not path.exists():
        print(f"  ⚠️  Not found: {path}")
        return []
    samples = []
    with open(path) as f:
        for line in f:
            try: samples.append(json.loads(line))
            except Exception: pass
    print(f"  Loaded {len(samples):,} from {path.name}")
    return samples

def token_estimate(text):
    """Rough token estimate: ~1.3 tokens per word"""
    return int(len(text.split()) * 1.3)

def print_stats(samples, label=""):
    if not samples: return
    print(f"\n  {label} ({len(samples):,} samples):")
    cats  = Counter(s.get("category","N/A")  for s in samples)
    sevs  = Counter(s.get("severity","N/A")  for s in samples)
    srcs  = Counter(s.get("source","synthetic") for s in samples)
    toks  = [token_estimate(s["text"]) for s in samples]
    print(f"    Sources     : {dict(srcs)}")
    print(f"    Categories  : {dict(sorted(cats.items(),key=lambda x:-x[1])[:5])}")
    print(f"    Severities  : {dict(sevs)}")
    print(f"    Token stats : mean={sum(toks)//len(toks)} min={min(toks)} max={max(toks)}")
    print(f"    Total tokens: {sum(toks):,}")

print("=" * 60)
print("  Arapai — Final Dataset Merge")
print("=" * 60)

# ── Load all components ───────────────────────────────────────────
print("\n── Loading datasets ─────────────────────────────────────────")
synthetic = load_jsonl(SYNTHETIC_PATH)
medqa     = load_jsonl(MEDQA_PATH)
medmcqa   = load_jsonl(MEDMCQA_PATH)

# Tag sources
for s in synthetic: s.setdefault("source", "Arapai-Synthetic")
for s in medqa:     s.setdefault("source", "MedQA-USMLE")
for s in medmcqa:   s.setdefault("source", "MedMCQA")

print(f"\n  Synthetic  : {len(synthetic):,}")
print(f"  MedQA      : {len(medqa):,}")
print(f"  MedMCQA    : {len(medmcqa):,}")
total_available = len(synthetic) + len(medqa) + len(medmcqa)
print(f"  Total      : {total_available:,}")

# ── Mix ratio: 60% synthetic, 20% MedQA, 20% MedMCQA ─────────────
print("\n── Applying mix ratio (60/20/20) ────────────────────────────")
TARGET_TOTAL  = 30000
TARGET_SYN    = int(TARGET_TOTAL * 0.60)   # 18,000
TARGET_MEDQA  = int(TARGET_TOTAL * 0.20)   # 6,000
TARGET_MEDMCQA= int(TARGET_TOTAL * 0.20)   # 6,000

def safe_sample(lst, n):
    if len(lst) >= n: return random.sample(lst, n)
    print(f"    ⚠️  Only {len(lst):,} available, using all")
    return lst[:]

syn_part    = safe_sample(synthetic,   TARGET_SYN)
medqa_part  = safe_sample(medqa,       TARGET_MEDQA)
medmcqa_part= safe_sample(medmcqa,     TARGET_MEDMCQA)

all_samples = syn_part + medqa_part + medmcqa_part
random.shuffle(all_samples)

print(f"  Synthetic   used : {len(syn_part):,}")
print(f"  MedQA       used : {len(medqa_part):,}")
print(f"  MedMCQA     used : {len(medmcqa_part):,}")
print(f"  Total merged     : {len(all_samples):,}")

# ── Train / eval split (90/10) ────────────────────────────────────
print("\n── Train / Eval split ───────────────────────────────────────")
split_idx = int(len(all_samples) * 0.90)
train_set = all_samples[:split_idx]
eval_set  = all_samples[split_idx:]

print(f"  Train : {len(train_set):,}")
print(f"  Eval  : {len(eval_set):,}")

# ── Quality filter — remove too-short samples ────────────────────
MIN_TOKENS = 50
train_set = [s for s in train_set if token_estimate(s["text"]) >= MIN_TOKENS]
eval_set  = [s for s in eval_set  if token_estimate(s["text"]) >= MIN_TOKENS]
print(f"  After quality filter (min {MIN_TOKENS} tokens):")
print(f"    Train : {len(train_set):,}")
print(f"    Eval  : {len(eval_set):,}")

# ── Save ──────────────────────────────────────────────────────────
print("\n── Saving ───────────────────────────────────────────────────")
with open(TRAIN_OUT, "w") as f:
    for s in train_set:
        f.write(json.dumps({"text": s["text"],
                             "source": s.get("source","N/A"),
                             "category": s.get("category","N/A"),
                             "severity": s.get("severity","N/A")}) + "\n")

with open(EVAL_OUT, "w") as f:
    for s in eval_set:
        f.write(json.dumps({"text": s["text"],
                             "source": s.get("source","N/A"),
                             "category": s.get("category","N/A"),
                             "severity": s.get("severity","N/A")}) + "\n")

train_mb = os.path.getsize(TRAIN_OUT)/1e6
eval_mb  = os.path.getsize(EVAL_OUT)/1e6
print(f"  {TRAIN_OUT.name}  ({train_mb:.1f} MB)")
print(f"  {EVAL_OUT.name}   ({eval_mb:.1f} MB)")

# ── Manifest ──────────────────────────────────────────────────────
print("\n── Generating dataset manifest ──────────────────────────────")
all_toks    = [token_estimate(s["text"]) for s in train_set + eval_set]
src_counts  = Counter(s.get("source","N/A") for s in train_set + eval_set)
cat_counts  = Counter(s.get("category","N/A") for s in train_set + eval_set)
sev_counts  = Counter(s.get("severity","N/A") for s in train_set + eval_set)

manifest = {
    "generated_at": datetime.now().isoformat(),
    "version": "2.0",
    "description": "Arapai Diagnostic AI training dataset — 50 clinical conditions, Africa-weighted",
    "total_samples": len(train_set) + len(eval_set),
    "train_samples": len(train_set),
    "eval_samples":  len(eval_set),
    "train_file": str(TRAIN_OUT),
    "eval_file":  str(EVAL_OUT),
    "mix_ratio": {
        "Arapai-Synthetic": f"{100*len(syn_part)/(len(syn_part)+len(medqa_part)+len(medmcqa_part)):.0f}%",
        "MedQA-USMLE":      f"{100*len(medqa_part)/(len(syn_part)+len(medqa_part)+len(medmcqa_part)):.0f}%",
        "MedMCQA":          f"{100*len(medmcqa_part)/(len(syn_part)+len(medqa_part)+len(medmcqa_part)):.0f}%",
    },
    "token_stats": {
        "total_tokens":    sum(all_toks),
        "mean_per_sample": sum(all_toks)//len(all_toks),
        "min":             min(all_toks),
        "max":             max(all_toks),
        "p95":             sorted(all_toks)[int(len(all_toks)*0.95)],
    },
    "source_distribution":   dict(src_counts),
    "category_distribution": dict(cat_counts),
    "severity_distribution": dict(sev_counts),
    "conditions_covered": 50,
    "reasoning_types": [
        "initial_differential","test_recommendation","evidence_update",
        "rationale_explanation","follow_up_questions","severity_assessment",
        "treatment_hint","red_flag_identification","mcq_clinical_reasoning",
    ],
    "geographic_focus": "East Africa (Uganda, Kenya, Tanzania, Ethiopia, Rwanda)",
    "adtc_compatible": True,
    "paper_citation_note": (
        "Dataset includes: (1) 18,000 Africa-weighted synthetic clinical "
        "reasoning samples across 50 conditions; (2) up to 6,000 MedQA-USMLE "
        "filtered questions; (3) up to 6,000 MedMCQA filtered questions. "
        "All real-world MCQ data is publicly available under open licenses."
    ),
}

with open(MANIFEST_PATH, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  {MANIFEST_PATH.name}")

# ── Final summary ─────────────────────────────────────────────────
print_stats(train_set, "Training set")
print_stats(eval_set,  "Evaluation set")

print("\n" + "="*60)
print("  DATASET MERGE COMPLETE")
print("="*60)
print(f"""
  Files:
    {TRAIN_OUT.name:<40} ({train_mb:.1f} MB)
    {EVAL_OUT.name:<40} ({eval_mb:.1f} MB)
    dataset_manifest.json

  Summary:
    Total samples  : {manifest['total_samples']:,}
    Train / Eval   : {manifest['train_samples']:,} / {manifest['eval_samples']:,}
    Total tokens   : {manifest['token_stats']['total_tokens']:,}
    Conditions     : {manifest['conditions_covered']}
    Reasoning types: {len(manifest['reasoning_types'])}
    Sources        : Arapai-Synthetic + MedQA + MedMCQA

  Use these paths in your training script:
    TRAIN_DATA = "{TRAIN_OUT}"
    EVAL_DATA  = "{EVAL_OUT}"
""")
