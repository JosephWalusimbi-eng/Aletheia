#!/usr/bin/env python3
"""
build_medqa_pipeline.py
=======================
Downloads MedQA (USMLE) and MedMCQA (Indian PG entrance),
filters for clinically relevant questions matching Arapai's
50 conditions, and reformats to the Arapai instruction template.

Run this on Colab:
    python build_medqa_pipeline.py

Outputs:
    medqa_filtered.jsonl      — MedQA questions reformatted
    medmcqa_filtered.jsonl    — MedMCQA questions reformatted
    (merged file created by build_merged_dataset.py)
"""

import json, os, re, random, urllib.request, zipfile, gzip, csv
from pathlib import Path
from collections import Counter

random.seed(42)

OUTPUT_DIR = Path("/content/drive/MyDrive/arapai_output/datasets")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Keyword filter — topics relevant to Arapai's 50 conditions ────
RELEVANT_KEYWORDS = [
    # Infectious / Tropical
    "malaria","plasmodium","falciparum","cerebral malaria","antimalarial",
    "tuberculosis","tb","mycobacterium","rifampicin","isoniazid","pyrazinamide",
    "hiv","aids","antiretroviral","art","cd4","viral load","opportunistic",
    "meningitis","meningococcal","lumbar puncture","csf","bacterial meningitis",
    "typhoid","salmonella typhi","widal","enteric fever",
    "cholera","vibrio","oral rehydration","rehydration",
    "hepatitis","hbsag","hbeag","hbv","hcv","jaundice","cirrhosis","portal",
    "schistosomiasis","bilharzia","praziquantel","haematuria",
    "leishmaniasis","kala-azar","leishmania","splenomegaly",
    "brucellosis","brucella","undulant fever",
    "leprosy","mycobacterium leprae","dapsone","multibacillary",
    "buruli ulcer","mycobacterium ulcerans",
    "sepsis","bacteraemia","blood culture","antibiotic","antibiotics",
    # Respiratory
    "pneumonia","consolidation","lobar","community-acquired",
    "pleural effusion","empyema","exudate","transudate","lights criteria",
    "asthma","wheeze","bronchospasm","salbutamol","nebuliser",
    "respiratory failure","oxygen saturation","pulse oximetry",
    # Cardiovascular
    "myocardial infarction","stemi","nstemi","troponin","ecg","st elevation",
    "hypertension","hypertensive emergency","labetalol","hydralazine",
    "heart failure","cardiac failure","ejection fraction","echo",
    "rheumatic fever","rheumatic heart disease","mitral stenosis","atrial fibrillation",
    "aortic dissection","pulmonary embolism","deep vein thrombosis",
    # Obstetric
    "eclampsia","pre-eclampsia","magnesium sulphate","magnesium sulfate",
    "postpartum haemorrhage","pph","oxytocin","ergometrine","uterine atony",
    "ectopic pregnancy","salpingectomy","beta hcg","ectopic",
    "puerperal sepsis","endometritis","postpartum","maternal sepsis",
    "obstetric","antenatal","prenatal","maternal","gravida","parity",
    # Paediatric
    "malnutrition","kwashiorkor","marasmus","rutf","f-75","f-100","muac",
    "neonatal sepsis","neonatal","neonate","ampicillin gentamicin",
    "paediatric pneumonia","fast breathing","chest indrawing","imci",
    "sickle cell","haemoglobin s","sickling","vaso-occlusive","acute chest syndrome",
    "paediatric","childhood","infant","child","vaccination","immunisation",
    # Neurological
    "epilepsy","seizure","status epilepticus","diazepam","phenytoin",
    "stroke","ischaemic stroke","haemorrhagic","thrombolysis","tpa",
    "neurocysticercosis","cysticercus","taenia",
    # Renal
    "acute kidney injury","aki","renal failure","creatinine","hyperkalaemia",
    "nephrotic syndrome","proteinuria","nephrotic","albumin oedema",
    "urinary tract infection","pyelonephritis","dysuria","nitrofurantoin",
    # Endocrine
    "diabetic ketoacidosis","dka","insulin","hypoglycaemia","hypoglycemia",
    "diabetes","glucose","ketones","kussmaul",
    # Surgical / Trauma
    "snake bite","envenomation","antivenom","viper","cobra","mamba",
    "burns","burn","parkland","inhalation injury","tbsa",
    "trauma","polytrauma","atls","fast scan","tension pneumothorax",
    "appendicitis","appendix","alvarado",
    "peptic ulcer","perforation","peritonitis","laparotomy",
    # Sexual Health
    "gonorrhoea","gonococcal","chlamydia","sexually transmitted","sti",
    "syphilis","treponema","rpr","treponemal",
    "pelvic inflammatory disease","pid",
    # Dermatology / Tropical
    "kaposi sarcoma","kaposi","ks","violaceous",
    "trachoma","chlamydia trachomatis","trichiasis",
    # Mental Health
    "psychosis","schizophrenia","antipsychotic","haloperidol",
    "alcohol withdrawal","delirium tremens","thiamine","wernicke",
    # Musculoskeletal
    "septic arthritis","joint aspiration","synovial fluid",
    "osteomyelitis","staphylococcus aureus bone",
    # ENT
    "mastoiditis","otitis media","peritonsillar","quinsy","ludwig angina",
    # Africa-specific
    "sub-saharan africa","tropical","endemic","east africa","uganda","kenya",
    "nigeria","ghana","resource-limited","low-income","developing",
    "district hospital","health centre","primary care",
]

KEYWORD_SET = set(kw.lower() for kw in RELEVANT_KEYWORDS)

def is_relevant(text):
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORD_SET)

def clean_text(t):
    if not t: return ""
    t = re.sub(r'\s+', ' ', t).strip()
    return t

# ══════════════════════════════════════════════════════════════════
#  PART 1 — MedQA (USMLE 4-option questions)
# ══════════════════════════════════════════════════════════════════

def download_medqa():
    """
    MedQA is available from HuggingFace datasets.
    We download the parquet files directly.
    """
    print("\n── Downloading MedQA (USMLE) ────────────────────────────────")

    try:
        # Try HuggingFace datasets library first
        from datasets import load_dataset
        print("  Loading via HuggingFace datasets library...")
        ds = load_dataset("GBaker/MedQA-USMLE-4-options", split="train")
        print(f"  Loaded {len(ds):,} training questions")
        return [{"question": r["question"], "options": r["options"],
                 "answer": r["answer_idx"], "answer_text": r["answer"]}
                for r in ds]
    except Exception as e:
        print(f"  HuggingFace load failed ({e}), trying direct download...")

    try:
        # Direct download from GitHub
        url = "https://raw.githubusercontent.com/jind11/MedQA/master/data/questions/US/train.jsonl"
        local = "/tmp/medqa_train.jsonl"
        urllib.request.urlretrieve(url, local)
        items = []
        with open(local) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    options = r.get("options", {})
                    answer = r.get("answer_idx", r.get("answer", "A"))
                    items.append({"question": r["question"], "options": options,
                                  "answer": answer,
                                  "answer_text": options.get(answer, "")})
                except Exception:
                    pass
        print(f"  Loaded {len(items):,} questions via direct download")
        return items
    except Exception as e:
        print(f"  Direct download failed: {e}")
        return []

def reformat_medqa(items):
    """
    Reformat MedQA MCQs to Arapai instruction format.
    Filter for clinically relevant questions only.
    """
    samples = []
    skipped = 0

    for item in items:
        q = clean_text(item.get("question", ""))
        options = item.get("options", {})
        answer = item.get("answer", "A")
        answer_text = item.get("answer_text", "")

        if not q or not answer_text:
            skipped += 1
            continue

        # Filter: only keep relevant questions
        option_text = " ".join(str(v) for v in options.values())
        if not is_relevant(q + " " + option_text):
            skipped += 1
            continue

        # Format options
        if isinstance(options, dict):
            opts_str = "\n".join(f"  {k}: {v}" for k, v in sorted(options.items()))
        else:
            opts_str = str(options)

        # Build instruction
        instruction = (
            "You are a clinical reasoning assistant trained for East African "
            "healthcare settings. Answer the following clinical question, "
            "explaining your reasoning step by step."
        )
        inp = f"Question: {q}\n\nOptions:\n{opts_str}"
        out = json.dumps({
            "correct_answer": answer,
            "answer_text": answer_text,
            "reasoning": f"The correct answer is {answer}: {answer_text}. "
                         f"This is a clinical MCQ from medical education examining "
                         f"knowledge relevant to clinical practice.",
        }, indent=2)

        samples.append({
            "text": f"### Instruction:\n{instruction}\n\n### Input:\n{inp}\n\n### Response:\n{out}",
            "source": "MedQA-USMLE",
            "category": "MCQ",
            "severity": "N/A",
        })

    print(f"  Reformatted: {len(samples):,} relevant  |  Skipped: {skipped:,}")
    return samples

# ══════════════════════════════════════════════════════════════════
#  PART 2 — MedMCQA (Indian PG entrance — large dataset)
# ══════════════════════════════════════════════════════════════════

def download_medmcqa():
    """MedMCQA — 194k PG entrance questions, many tropical medicine."""
    print("\n── Downloading MedMCQA ──────────────────────────────────────")

    try:
        from datasets import load_dataset
        print("  Loading via HuggingFace datasets library...")
        ds = load_dataset("openlifescienceai/medmcqa", split="train")
        print(f"  Loaded {len(ds):,} training questions")
        items = []
        for r in ds:
            opts = {
                "A": r.get("opa", ""),
                "B": r.get("opb", ""),
                "C": r.get("opc", ""),
                "D": r.get("opd", ""),
            }
            cop_map = {0: "A", 1: "B", 2: "C", 3: "D"}
            cop = cop_map.get(r.get("cop", 0), "A")
            items.append({
                "question": r.get("question", ""),
                "options": opts,
                "answer": cop,
                "answer_text": opts.get(cop, ""),
                "subject": r.get("subject_name", ""),
                "topic": r.get("topic_name", ""),
                "explanation": r.get("exp", ""),
            })
        return items
    except Exception as e:
        print(f"  HuggingFace load failed ({e})")
        return []

def reformat_medmcqa(items):
    samples = []
    skipped = 0

    # High-value subjects for Arapai
    PRIORITY_SUBJECTS = {
        "medicine","surgery","obs & gynae","obstetrics and gynaecology",
        "paediatrics","pharmacology","microbiology","pathology",
        "forensic medicine","tropical medicine","community medicine",
        "preventive medicine","ophthalmology","ent",
    }

    for item in items:
        q           = clean_text(item.get("question", ""))
        options     = item.get("options", {})
        answer      = item.get("answer", "A")
        answer_text = clean_text(item.get("answer_text", ""))
        explanation = clean_text(item.get("explanation") or "")
        subject = (item.get("subject") or "").lower()
        topic   = (item.get("topic")   or "").lower()

        if not q or not answer_text:
            skipped += 1
            continue

        # Priority filter: relevant subject OR relevant keyword
        option_text = " ".join(str(v) for v in options.values())
        full_text   = " ".join([q, option_text, explanation, subject, topic])
        subject_ok  = any(s in subject for s in PRIORITY_SUBJECTS)
        keyword_ok  = is_relevant(full_text)

        if not (subject_ok or keyword_ok):
            skipped += 1
            continue

        # Format options
        if isinstance(options, dict):
            opts_str = "\n".join(f"  {k}: {v}" for k, v in sorted(options.items()))
        else:
            opts_str = str(options)

        instruction = (
            "You are a clinical reasoning assistant trained for East African "
            "healthcare settings. Answer the following clinical question and "
            "explain the reasoning."
        )
        inp = f"Question: {q}\n\nOptions:\n{opts_str}"

        reasoning = explanation if explanation and len(explanation) > 20 else (
            f"The correct answer is {answer}: {answer_text}."
        )

        out = json.dumps({
            "correct_answer": answer,
            "answer_text": answer_text,
            "reasoning": reasoning,
            "subject": subject,
        }, indent=2)

        samples.append({
            "text": f"### Instruction:\n{instruction}\n\n### Input:\n{inp}\n\n### Response:\n{out}",
            "source": "MedMCQA",
            "category": subject,
            "severity": "N/A",
        })

    print(f"  Reformatted: {len(samples):,} relevant  |  Skipped: {skipped:,}")
    return samples

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  Arapai — MedQA + MedMCQA Download & Reformat Pipeline")
    print("=" * 60)

    # MedQA
    medqa_raw     = download_medqa()
    medqa_samples = reformat_medqa(medqa_raw) if medqa_raw else []

    medqa_path = OUTPUT_DIR / "medqa_filtered.jsonl"
    with open(medqa_path, "w") as f:
        for s in medqa_samples:
            f.write(json.dumps(s) + "\n")
    print(f"\n  MedQA filtered → {medqa_path}")
    print(f"  Samples: {len(medqa_samples):,}")

    # MedMCQA
    medmcqa_raw     = download_medmcqa()
    medmcqa_samples = reformat_medmcqa(medmcqa_raw) if medmcqa_raw else []

    # Cap MedMCQA at 10,000 — enough to enrich without dominating
    if len(medmcqa_samples) > 10000:
        medmcqa_samples = random.sample(medmcqa_samples, 10000)
        print(f"  MedMCQA capped at 10,000 samples (random sample)")

    medmcqa_path = OUTPUT_DIR / "medmcqa_filtered.jsonl"
    with open(medmcqa_path, "w") as f:
        for s in medmcqa_samples:
            f.write(json.dumps(s) + "\n")
    print(f"\n  MedMCQA filtered → {medmcqa_path}")
    print(f"  Samples: {len(medmcqa_samples):,}")

    print("\n  Run build_merged_dataset.py next to create the final training set.")

if __name__ == "__main__":
    main()
