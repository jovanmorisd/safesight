"""Turn per-item states into a per-person verdict for a site's required PPE."""
from __future__ import annotations

from .types import PersonAssessment

SEVERITY = {"helmet": "high", "vest": "medium", "boots": "medium", "goggles": "medium",
            "gloves": "low", "mask": "low", "earmuffs": "low"}
_RANK = {"low": 0, "medium": 1, "high": 2}


def judge(pa: PersonAssessment, required: list[str]) -> PersonAssessment:
    """A violation needs a required item to be *absent*. Unknown is never a violation, and
    items the model cannot detect (not_checked) are left out of the verdict entirely."""
    checkable = [i for i in required if i in pa.items and pa.items[i].state != "not_checked"]
    pa.missing = [i for i in checkable if pa.items[i].state == "absent"]
    pa.uncertain = [i for i in checkable if pa.items[i].state == "unknown"]
    if pa.missing:
        pa.overall = "violation"
    elif pa.uncertain or not checkable:
        pa.overall = "unknown"
    else:
        pa.overall = "compliant"
    return pa


def severity(missing: list[str]) -> str:
    if not missing:
        return "low"
    return max((SEVERITY.get(i, "low") for i in missing), key=_RANK.__getitem__)
