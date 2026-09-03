"""
recall.py
=========
Saved cases, and the lookup that lets a repeat presentation skip the model.

A stage costs 40-60 s of CPU on the target laptop, and district practice is
repetitive: the same presentation arrives at the same clinic several times in a
season. Re-deriving an answer the clinician has already read and accepted spends
the scarcest resource on the machine to arrive back where it started. So a
finished stage can be kept, and a later stage with the same inputs can be
answered from the record instead of from llama.cpp.

What is stored is a presentation, not a person. Aletheia has no field in which a
patient identity could be recorded — the inputs are a symptom list, a duration, an
age *band* and sex — so a saved case has the same shape as a textbook vignette.
The identifiers are not protected here; they are never collected. The one channel
left open is the free-text boxes, so `identifier_warning()` looks for the obvious
markers before a save is written and lets the caller warn.

Four rules hold everywhere this module is used, and each stops a specific
failure:

  * A recalled result is labelled as recalled, with its date and whether a
    clinician edited it. A cached recommendation shown as a fresh one invites a
    reader to see corroboration in what is only repetition.
  * A fresh run is always available. `lookup()` returns an offer; nothing here
    decides on the clinician's behalf.
  * The safety screen runs before recall. Callers screen the incoming text
    first, so a paediatric dosing question is refused on a matched case exactly
    as it is on a cold run. Recall is not a route around a guardrail.
  * Saved cases age. `stale` is set past `stale_after_days` so the clinician can
    see that they are reading year-old reasoning and decide whether it holds.

The store is one JSON file. It is never synced or transmitted — the offline
guarantee covers saved cases as completely as it covers inference — and the
system runs normally when it is missing, unreadable or empty.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

# Sits beside the model weights: both are large-ish local state that belongs to
# the machine rather than to the checkout, and a clinician looking for "the
# things Aletheia keeps on my laptop" finds one directory rather than two.
DEFAULT_STORE_NAME = "aletheia_cases.json"

# A year, past which clinical guidance may simply have moved on. Configurable
# because a district that revises its protocols quarterly should say so.
DEFAULT_STALE_AFTER_DAYS = 365


def store_path() -> Path:
    """Where saved cases live.

    ALETHEIA_CASE_STORE wins if set; otherwise the file sits beside the model
    weights, falling back to the repository when the model path is unusable.
    """
    override = os.environ.get("ALETHEIA_CASE_STORE")
    if override:
        return Path(override).expanduser()
    try:
        from inference.aletheia import load_config
    except ImportError:  # executed directly, not as a package
        from aletheia import load_config  # type: ignore[no-redef]
    try:
        model = Path(load_config()["model_path"]).expanduser()
        if model.parent.exists():
            return model.parent / DEFAULT_STORE_NAME
    except Exception:
        pass
    return Path(__file__).resolve().parent.parent / DEFAULT_STORE_NAME


def stale_after_days() -> int:
    try:
        from inference.aletheia import load_config
    except ImportError:
        from aletheia import load_config  # type: ignore[no-redef]
    try:
        return int(load_config().get("stale_after_days", DEFAULT_STALE_AFTER_DAYS))
    except Exception:
        return DEFAULT_STALE_AFTER_DAYS


# ---------------------------------------------------------------------------
# The case key — what counts as "the same situation"
# ---------------------------------------------------------------------------

# Duration is banded rather than exact. A cough of two days and a cough of three
# is not a different clinical situation, and keying on the exact integer would
# mean a store that almost never matches. The bands are the ones clinicians
# already reason in.
_DURATION_BANDS = ((1, "0-1"), (3, "2-3"), (7, "4-7"),
                   (14, "8-14"), (30, "15-30"))


def duration_band(days: int) -> str:
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 0
    for ceiling, label in _DURATION_BANDS:
        if days <= ceiling:
            return label
    return "31+"


def normalise_symptoms(symptoms) -> list[str]:
    """Lower-case, de-duplicate and sort, so word order never splits a match.

    "fever, headache" and "Headache, fever" are one presentation, and a store
    that treated them as two would miss most of the repeats it exists to catch.
    """
    if isinstance(symptoms, str):
        symptoms = symptoms.split(",")
    cleaned = {re.sub(r"\s+", " ", s).strip().lower() for s in symptoms}
    return sorted(s for s in cleaned if s)


def normalise_text(text: str) -> str:
    """Fold whitespace and case in a free-text answer.

    Deliberately conservative: the follow-up answers and the investigation
    results are the clinical content of Stages 2 and 3, so anything short of the
    same answers is a different case and goes to the model. This means Stage 1
    matches often and the later stages match rarely, which is the correct bias —
    a recalled Stage 3 advisory on results that differ would be wrong in the
    most dangerous place.
    """
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def case_key(symptoms, duration_days: int, age_group: str, sex: str,
             stage: str, extra: str = "") -> str:
    """A stable digest of the inputs that define the situation."""
    payload = json.dumps({
        "v": SCHEMA_VERSION,
        "symptoms": normalise_symptoms(symptoms),
        "duration_band": duration_band(duration_days),
        "age_group": (age_group or "unknown").strip().lower(),
        "sex": (sex or "unknown").strip().lower(),
        "stage": stage,
        "extra": normalise_text(extra),
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Identifier screening — the one channel the schema leaves open
# ---------------------------------------------------------------------------

# Deliberately narrow. A broad rule ("any capitalised word") would fire on every
# condition name and every drug, train clinicians to click through the warning,
# and so protect nothing. These are the markers that mean someone typed an
# identity on purpose.
_IDENTIFIER_PATTERNS = (
    (r"\b(?:patient|pt)\s*(?:name|id|no|number|#)\b", "a patient identifier"),
    (r"\b(?:ip|opd|op|hosp(?:ital)?)\s*(?:no|number|#)\b", "a hospital number"),
    (r"\bnin\b", "a national identification number"),
    (r"\bname\s*(?:is|:)\s*\S+", "a name"),
    # The title matches case-insensitively; the word after it does not, so
    # "Mrs Achen" is caught without every lower-case word after a title firing.
    (r"\b(?:mr|mrs|ms|miss|dr)\.?\s+(?-i:[A-Z][a-z]+)", "a name"),
    (r"\b(?:date\s+of\s+birth|dob)\b", "a date of birth"),
    (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "a full date"),
)


def identifier_warning(*texts: str) -> str | None:
    """Return a warning if the text about to be stored looks like it names someone.

    Advisory only: the clinician decides. Aletheia refuses hazards in code, but
    it does not refuse to save a clinician's own note.
    """
    for text in texts:
        if not text:
            continue
        for pattern, what in _IDENTIFIER_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return (
                    f"This looks like it contains {what}. Saved cases are meant to "
                    "describe a presentation, not a patient — remove it before saving."
                )
    return None


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@dataclass
class SavedCase:
    key: str
    stage: str
    data: dict                       # the stage output, as the consumers read it
    saved_at: str                    # ISO 8601, UTC
    edited: bool = False             # True when a clinician corrected it first
    schema_version: int = SCHEMA_VERSION
    inputs: dict = field(default_factory=dict)   # normalised, for display only

    @property
    def age_days(self) -> int:
        try:
            saved = datetime.fromisoformat(self.saved_at)
        except ValueError:
            return 0
        if saved.tzinfo is None:
            saved = saved.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - saved).days)

    def is_stale(self, threshold: int | None = None) -> bool:
        return self.age_days > (stale_after_days() if threshold is None else threshold)

    @property
    def saved_on(self) -> str:
        """Just the date — the time of day is noise to a reader."""
        return (self.saved_at or "")[:10]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["age_days"] = self.age_days
        d["stale"] = self.is_stale()
        d["saved_on"] = self.saved_on
        return d

    def provenance(self) -> str:
        """One line a clinician can read before deciding to trust this."""
        origin = "clinician-edited" if self.edited else "as generated"
        line = f"Recalled from a case saved on {self.saved_on} ({origin})"
        if self.is_stale():
            line += f" — {self.age_days} days old, guidance may have changed"
        return line + "."

    @classmethod
    def from_dict(cls, d: dict) -> "SavedCase":
        return cls(
            key=d["key"],
            stage=d.get("stage", ""),
            data=d.get("data") or {},
            saved_at=d.get("saved_at", ""),
            edited=bool(d.get("edited", False)),
            schema_version=int(d.get("schema_version", 1)),
            inputs=d.get("inputs") or {},
        )


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------


def _read(path: Path | None = None) -> dict:
    """Load the store, treating every failure as an empty store.

    A corrupt or half-written file must not stop a clinician from using
    Aletheia. Recall is an optimisation; inference is the product.
    """
    path = path or store_path()
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"schema_version": SCHEMA_VERSION, "cases": {}}
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), dict):
        return {"schema_version": SCHEMA_VERSION, "cases": {}}
    return doc


def _write(doc: dict, path: Path | None = None) -> None:
    """Write atomically, so an interrupted save cannot destroy the store.

    Laptops in this setting lose power. Writing a temp file in the same
    directory and replacing means the worst outcome is losing the newest case,
    never losing every case saved before it.
    """
    path = path or store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def lookup(symptoms, duration_days: int, age_group: str, sex: str,
           stage: str, extra: str = "", path: Path | None = None) -> SavedCase | None:
    """Return a saved case for these exact inputs, or None.

    This is an offer. It never runs on its own and it never suppresses a fresh
    run — the caller decides what to do with what comes back, and every caller
    in this project shows the clinician before using it.
    """
    key = case_key(symptoms, duration_days, age_group, sex, stage, extra)
    entry = _read(path)["cases"].get(key)
    if not entry:
        return None
    try:
        return SavedCase.from_dict(entry)
    except (KeyError, TypeError, ValueError):
        return None


def save(symptoms, duration_days: int, age_group: str, sex: str,
         stage: str, data: dict, extra: str = "", edited: bool = False,
         path: Path | None = None) -> SavedCase:
    """Store a finished stage under its case key, replacing any earlier one.

    A later save wins: if a clinician has corrected an answer that was already
    saved, the correction is the one worth keeping.
    """
    key = case_key(symptoms, duration_days, age_group, sex, stage, extra)
    case = SavedCase(
        key=key,
        stage=stage,
        data=data,
        saved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        edited=edited,
        inputs={
            "symptoms": normalise_symptoms(symptoms),
            "duration_band": duration_band(duration_days),
            "age_group": (age_group or "unknown").strip().lower(),
            "sex": (sex or "unknown").strip().lower(),
            "has_extra": bool(normalise_text(extra)),
        },
    )
    doc = _read(path)
    doc["schema_version"] = SCHEMA_VERSION
    doc["cases"][key] = asdict(case)
    _write(doc, path)
    return case


def delete(key: str, path: Path | None = None) -> bool:
    doc = _read(path)
    if key in doc["cases"]:
        del doc["cases"][key]
        _write(doc, path)
        return True
    return False


def clear(path: Path | None = None) -> int:
    doc = _read(path)
    n = len(doc["cases"])
    _write({"schema_version": SCHEMA_VERSION, "cases": {}}, path)
    return n


def all_cases(path: Path | None = None) -> Iterator[SavedCase]:
    """Every saved case, newest first."""
    entries = list(_read(path)["cases"].values())
    entries.sort(key=lambda e: e.get("saved_at", ""), reverse=True)
    for entry in entries:
        try:
            yield SavedCase.from_dict(entry)
        except (KeyError, TypeError, ValueError):
            continue


def stats(path: Path | None = None) -> dict:
    cases = list(all_cases(path))
    return {
        "count": len(cases),
        "edited": sum(1 for c in cases if c.edited),
        "stale": sum(1 for c in cases if c.is_stale()),
        "path": str(path or store_path()),
    }


# ---------------------------------------------------------------------------
# Self-check: python3 -m inference.recall
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import shutil

    tmpdir = Path(tempfile.mkdtemp(prefix="aletheia-recall-"))
    p = tmpdir / "cases.json"
    failures = []

    def check(label, condition):
        if not condition:
            failures.append(label)
        print(f"  {'ok  ' if condition else 'FAIL'}  {label}")

    print("Case key")
    base = (["fever", "headache"], 2, "child", "female", "initial_with_followup")
    check("symptom order does not split a match",
          case_key(*base) == case_key(["Headache", " FEVER "], 2, "child", "female",
                                      "initial_with_followup"))
    check("2 and 3 days are the same band", case_key(*base) == case_key(
        ["fever", "headache"], 3, "child", "female", "initial_with_followup"))
    check("2 and 9 days are not", case_key(*base) != case_key(
        ["fever", "headache"], 9, "child", "female", "initial_with_followup"))
    check("age group separates cases", case_key(*base) != case_key(
        ["fever", "headache"], 2, "adult", "female", "initial_with_followup"))
    check("stage separates cases", case_key(*base) != case_key(
        ["fever", "headache"], 2, "child", "female", "test_recommendation"))
    check("different follow-up answers separate cases",
          case_key(["fever"], 2, "child", "female", "test_recommendation", "no rash")
          != case_key(["fever"], 2, "child", "female", "test_recommendation", "rash present"))
    check("the same answers, differently spaced, do not",
          case_key(["fever"], 2, "child", "female", "test_recommendation", "No  rash")
          == case_key(["fever"], 2, "child", "female", "test_recommendation", "no rash"))

    print("\nStore")
    check("a miss on an empty store returns None",
          lookup(["fever"], 2, "child", "female", "initial_with_followup", path=p) is None)
    save(["fever", "headache"], 2, "child", "female", "initial_with_followup",
         {"tentative_differentials": [{"condition": "Malaria", "probability": 0.6}]},
         path=p)
    hit = lookup(["headache", "fever"], 3, "child", "female",
                 "initial_with_followup", path=p)
    check("a repeat presentation hits", hit is not None)
    check("the stored output comes back",
          hit and hit.data["tentative_differentials"][0]["condition"] == "Malaria")
    check("a fresh case is not stale", hit and not hit.is_stale())
    check("provenance names the origin", hit and "as generated" in hit.provenance())

    save(["fever", "headache"], 2, "child", "female", "initial_with_followup",
         {"tentative_differentials": [{"condition": "Typhoid", "probability": 0.7}]},
         edited=True, path=p)
    hit = lookup(["fever", "headache"], 2, "child", "female",
                 "initial_with_followup", path=p)
    check("a correction replaces the earlier answer",
          hit and hit.data["tentative_differentials"][0]["condition"] == "Typhoid")
    check("the correction is marked as edited", hit and hit.edited)
    check("provenance says so", hit and "clinician-edited" in hit.provenance())
    check("one case, not two", stats(p)["count"] == 1)

    print("\nAgeing")
    doc = _read(p)
    only = next(iter(doc["cases"]))
    doc["cases"][only]["saved_at"] = "2020-01-01T00:00:00+00:00"
    _write(doc, p)
    old = lookup(["fever", "headache"], 2, "child", "female",
                 "initial_with_followup", path=p)
    check("an old case is stale", old and old.is_stale())
    check("staleness is visible in the provenance line",
          old and "guidance may have changed" in old.provenance())

    print("\nResilience")
    p.write_text("{ this is not json", encoding="utf-8")
    check("a corrupt store reads as empty", stats(p)["count"] == 0)
    check("a corrupt store does not raise on lookup",
          lookup(["fever"], 2, "child", "female", "initial_with_followup", path=p) is None)
    save(["fever"], 2, "child", "female", "initial_with_followup", {"x": 1}, path=p)
    check("and can be written over", stats(p)["count"] == 1)

    print("\nIdentifier screening")
    check("a bare presentation passes",
          identifier_warning("fever, convulsions, neck stiffness") is None)
    check("a drug and a lab value pass",
          identifier_warning("gave 500 mg ceftriaxone at 0600, creatinine now 180") is None)
    check("a condition name passes",
          identifier_warning("query Cerebral Malaria, Buruli ulcer excluded") is None)
    check("a name is caught", identifier_warning("name is Achen Grace") is not None)
    check("a title is caught", identifier_warning("Mrs Achen, 34, fever") is not None)
    check("a hospital number is caught", identifier_warning("IP no 44821") is not None)
    check("a date of birth is caught", identifier_warning("DOB 12/04/1991") is not None)

    shutil.rmtree(tmpdir, ignore_errors=True)
    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        raise SystemExit(1)
    print("All recall checks passed.")
