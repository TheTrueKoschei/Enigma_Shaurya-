"""Conformance grading: does this material meet that specification?

Pure functions over materials.MATERIAL_PROPERTIES and specs.SPECS. No Streamlit,
no randomness, no model - the same material and specification always produce the
same verdict, and every verdict carries the arithmetic that produced it.

The design rule is that a failure must always be attributable. "Not suitable" is
never an answer on its own: a failing grade names the property, the limit, the
measured value and the size of the gap.
"""

from __future__ import annotations

import materials
import specs

# Grade A needs this much headroom on every limit, as a fraction of the limit.
# The point is to separate "comfortably inside specification, survives normal
# process variation" from "inside today, and one bad shift from being outside".
GRADE_A_HEADROOM = 0.15

# A single failure smaller than this is a near miss - worth a blend or a process
# tweak. Anything worse is a different material.
NEAR_MISS = 0.20


def resolve(expression: str, props: dict):
    """Evaluate a property expression such as "sio2+al2o3+fe2o3".

    Returns (value, missing_parts). A single missing component makes the whole
    expression unassessable, which is the honest outcome: an unmeasured oxide
    cannot be assumed to be zero.
    """
    parts = [p.strip() for p in str(expression).split("+")]
    missing = [p for p in parts if props.get(p) is None]
    if missing:
        return None, missing
    return float(sum(float(props[p]) for p in parts)), []


def _headroom(operator: str, actual: float, threshold: float) -> tuple:
    """Signed margin in the property's own units, and as a fraction of the limit.

    Positive means inside the limit. The fraction is what the grade bands use,
    so a 1% absolute margin counts differently against a limit of 3 than
    against a limit of 320.
    """
    margin = (actual - threshold) if operator == ">=" else (threshold - actual)
    scale = abs(threshold) if threshold else 1.0
    return margin, margin / scale


def check_limit(limit: tuple, props: dict) -> dict:
    """One limit against one property vector."""
    expression, operator, threshold, unit_note = limit
    actual, missing = resolve(expression, props)

    if actual is None:
        return {
            "property": expression,
            "operator": operator,
            "threshold": float(threshold),
            "actual": None,
            "passes": False,
            "measured": False,
            "margin": None,
            "headroom_frac": None,
            "unit_note": unit_note,
            "detail": "not measured for this stream: " + ", ".join(missing),
        }

    margin, headroom = _headroom(operator, actual, float(threshold))
    return {
        "property": expression,
        "operator": operator,
        "threshold": float(threshold),
        "actual": actual,
        "passes": margin >= 0,
        "measured": True,
        "margin": margin,
        "headroom_frac": headroom,
        "unit_note": unit_note,
        "detail": "",
    }


def check_ratios(spec_name: str, props: dict) -> list:
    """Ratio rules, which cannot be written as a threshold on a sum."""
    out = []
    for expression, operator, threshold, description in specs.RATIO_RULES.get(spec_name, []):
        numerator, denominator = expression.split("/")
        num_value, num_missing = resolve(numerator.strip("()"), props)
        den_value, den_missing = resolve(denominator.strip("()"), props)
        if num_value is None or den_value is None or not den_value:
            out.append({"expression": expression, "threshold": threshold,
                        "actual": None, "passes": False, "measured": False,
                        "description": description})
            continue
        actual = num_value / den_value
        passes = actual > threshold if operator == ">" else actual < threshold
        out.append({"expression": expression, "threshold": threshold,
                    "actual": actual, "passes": bool(passes), "measured": True,
                    "description": description})
    return out


def grade(material_name: str, spec_name: str) -> dict:
    """Grade one material against one specification.

    Returns a dict carrying the verdict and everything behind it:
      passes    every limit and ratio rule satisfied
      results   one entry per limit, with required, actual, margin and headroom
      ratios    ratio rules, reported separately from the limit table
      failures  the failing entries, worst miss first
      grade     A  every limit passes with at least 15% headroom
                B  every limit passes
                C  one limit fails by less than 20% of the limit
                D  anything worse, or a property that is not measured
      binding   the limit closest to its threshold - what actually constrains
                this material, whether or not it currently passes
    """
    props = materials.measured_properties(material_name)
    entry = specs.spec(spec_name)
    if not props or entry is None:
        return {
            "material": material_name, "spec": spec_name, "passes": False,
            "grade": "D", "results": [], "ratios": [], "failures": [],
            "binding": None, "value_inr_t": 0, "standard": "", "confidence": "",
            "note": "Material or specification not found.",
        }

    results = [check_limit(limit, props) for limit in entry["limits"]]
    ratios = check_ratios(spec_name, props)

    failures = [r for r in results if not r["passes"]]
    failures.sort(key=lambda r: (r["headroom_frac"] is not None,
                                 r["headroom_frac"] if r["headroom_frac"] is not None else 0))
    ratio_failures = [r for r in ratios if not r["passes"]]

    passes = not failures and not ratio_failures

    measured = [r for r in results if r["measured"]]
    binding = min(measured, key=lambda r: r["headroom_frac"]) if measured else None

    if passes:
        worst = min((r["headroom_frac"] for r in measured), default=0.0)
        letter = "A" if worst >= GRADE_A_HEADROOM else "B"
    elif len(failures) + len(ratio_failures) == 1 and failures and failures[0]["measured"] \
            and abs(failures[0]["headroom_frac"]) < NEAR_MISS:
        letter = "C"
    else:
        letter = "D"

    return {
        "material": material_name,
        "spec": spec_name,
        "passes": passes,
        "grade": letter,
        "results": results,
        "ratios": ratios,
        "failures": failures,
        "ratio_failures": ratio_failures,
        "binding": binding,
        "value_inr_t": entry["value_inr_t"],
        "standard": entry["standard"],
        "confidence": entry["confidence"],
        "note": entry.get("note", ""),
    }


def grade_all(material_name: str) -> list:
    """Grade a material against every specification, most valuable first."""
    return [grade(material_name, name) for name in specs.specs()]


def cascade(material_name: str) -> dict:
    """The value ladder for one material.

    Every application in the library, ranked by value, each marked qualifying or
    not - and then the number that answers "how could this by-product be further
    utilised": the gap between the best use it actually qualifies for and the
    best use in the library.
    """
    rungs = grade_all(material_name)
    qualifying = [r for r in rungs if r["passes"]]

    best_name, best_value = specs.highest_value()
    achieved = qualifying[0] if qualifying else None
    achieved_value = achieved["value_inr_t"] if achieved else 0

    # The actionable rung is the one it comes closest to clearing, not the most
    # valuable one it misses. Ranking blocked rungs by the size of their worst
    # miss answers "what would it take to move up", which is the question; the
    # most valuable rung is usually a different material altogether.
    blocked = [r for r in rungs if not r["passes"]
               and r["value_inr_t"] > achieved_value]

    def distance(rung):
        misses = [abs(f["headroom_frac"]) for f in rung["failures"]
                  if f["headroom_frac"] is not None]
        unmeasured = sum(1 for f in rung["failures"] if not f["measured"])
        # An unmeasured property is not a near miss - it is an unknown, and it
        # sorts behind every rung whose gap is actually quantified.
        return (unmeasured > 0, max(misses) if misses else float("inf"),
                -rung["value_inr_t"])

    nearest_upgrade = min(blocked, key=distance) if blocked else None

    return {
        "material": material_name,
        "rungs": rungs,
        "qualifying": qualifying,
        "best_qualifying": achieved,
        "best_qualifying_value": achieved_value,
        "library_best": best_name,
        "library_best_value": best_value,
        "quality_discount": max(0, best_value - achieved_value),
        "nearest_upgrade": nearest_upgrade,
    }
