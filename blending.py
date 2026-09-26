"""Two-stream blending: reaching a specification through chemistry.

Every property modelled in materials.py is an intensive quantity that mixes
linearly by mass fraction, so a blend of fraction `f` of stream A with `(1 - f)`
of stream B has

    p_blend = f * p_A + (1 - f) * p_B

That makes each limit a linear inequality in `f` with a closed-form solution.
Solving every limit and intersecting the resulting intervals gives the exact
range of blend ratios that satisfies the whole specification - or, when the
intersection is empty, the pair of limits that pull in opposite directions and
make it impossible.

This is the part that creates value without moving anything further: a coarse,
high-carbon ash that fails structural concrete grade on its own can clear it
blended with a finer ash from the next state, and nobody has to build anything.

Caveat that belongs on screen, not just here: linear mixing is a sound
assumption for composition, and a reasonable one for fineness and loss on
ignition. It is NOT a substitute for the performance tests - lime reactivity,
soundness, strength activity index - that the standards also require. A feasible
blend here is a candidate for a trial mix, not a certificate.
"""

from __future__ import annotations

import conformance
import materials
import specs

# Blend fractions are reported to this resolution. Finer than a plant can
# actually dose, which is the point: the recommendation is rounded inward so a
# rounding error cannot push the mix outside the specification.
STEP = 0.01


def _interval_for_limit(limit: tuple, props_a: dict, props_b: dict) -> dict:
    """The range of f satisfying one limit, as a dict with lo, hi and why."""
    expression, operator, threshold, unit_note = limit
    value_a, missing_a = conformance.resolve(expression, props_a)
    value_b, missing_b = conformance.resolve(expression, props_b)

    if value_a is None or value_b is None:
        return {"property": expression, "operator": operator,
                "threshold": float(threshold), "lo": None, "hi": None,
                "value_a": value_a, "value_b": value_b, "feasible": False,
                "unit_note": unit_note,
                "reason": "not measured for " + (", ".join(missing_a or missing_b))}

    threshold = float(threshold)
    slope = value_a - value_b            # d(blend)/df
    lo, hi = 0.0, 1.0
    feasible = True
    reason = ""

    if abs(slope) < 1e-12:
        # Both streams sit at the same value, so f cannot change the outcome.
        satisfied = (value_b >= threshold) if operator == ">=" else (value_b <= threshold)
        if not satisfied:
            feasible = False
            reason = ("both streams are at "
                      f"{value_b:g}, which no blend ratio can change")
    else:
        crossing = (threshold - value_b) / slope
        if (operator == ">=" and slope > 0) or (operator == "<=" and slope < 0):
            lo = crossing                 # need more of A
        else:
            hi = crossing                 # need less of A

    lo = max(0.0, lo)
    hi = min(1.0, hi)
    if feasible and lo > hi:
        feasible = False
        reason = "no ratio of these two streams satisfies this limit"

    return {"property": expression, "operator": operator, "threshold": threshold,
            "lo": lo, "hi": hi, "value_a": value_a, "value_b": value_b,
            "feasible": feasible, "unit_note": unit_note, "reason": reason}


def blend_properties(props_a: dict, props_b: dict, f: float) -> dict:
    """Linear mix of two property vectors at fraction f of A.

    A property present in only one of the two streams is dropped rather than
    half-counted: a blend cannot be assessed on a property that was never
    measured on both sides.
    """
    shared = set(props_a) & set(props_b)
    return {k: f * float(props_a[k]) + (1.0 - f) * float(props_b[k]) for k in shared}


def blend_to_spec(material_a: str, material_b: str, spec_name: str) -> dict:
    """Find the blend ratios of A and B that satisfy a specification.

    Returns a dict with:
      feasible      whether any ratio works
      f_min, f_max  the feasible range of the mass fraction of A
      f_recommended the ratio to run, biased toward the stream with the larger
                    annual disposal burden - the one there is more of to place
      intervals     per limit: the value in each stream and the f range it allows
      blocking      when infeasible, the limits that cannot be satisfied together
      report        the full conformance grade of the recommended blend
    """
    props_a = materials.measured_properties(material_a)
    props_b = materials.measured_properties(material_b)
    entry = specs.spec(spec_name)

    blank = {"material_a": material_a, "material_b": material_b, "spec": spec_name,
             "feasible": False, "f_min": None, "f_max": None,
             "f_recommended": None, "intervals": [], "blocking": [],
             "blend": {}, "report": None, "reason": ""}

    if not props_a or not props_b or entry is None:
        blank["reason"] = "Material or specification not found."
        return blank
    if material_a == material_b:
        blank["reason"] = "Pick two different streams - blending a stream with itself changes nothing."
        return blank

    intervals = [_interval_for_limit(limit, props_a, props_b) for limit in entry["limits"]]
    blocking = [i for i in intervals if not i["feasible"]]

    f_min, f_max = 0.0, 1.0
    for interval in intervals:
        if interval["feasible"] and interval["lo"] is not None:
            f_min = max(f_min, interval["lo"])
            f_max = min(f_max, interval["hi"])

    if blocking or f_min > f_max:
        if not blocking:
            # Two limits are individually satisfiable but pull opposite ways.
            binding_low = max((i for i in intervals if i["feasible"]),
                              key=lambda i: i["lo"], default=None)
            binding_high = min((i for i in intervals if i["feasible"]),
                               key=lambda i: i["hi"], default=None)
            blocking = [i for i in (binding_low, binding_high) if i is not None]
        blank["intervals"] = intervals
        blank["blocking"] = blocking
        blank["reason"] = "No blend ratio satisfies every limit at once."
        return blank

    # Which stream should the blend carry as much of as possible?
    #
    # The point of blending is to place a stream that cannot be placed on its
    # own. So the first rule is to favour whichever of the two does NOT already
    # meet the specification - maximising the stream that already qualifies
    # would be a recommendation to use none of the problem material, which
    # creates nothing. Only when both qualify, or neither does, does the
    # decision fall back to which stream costs more to dispose of.
    a_qualifies = conformance.grade(material_a, spec_name)["passes"]
    b_qualifies = conformance.grade(material_b, spec_name)["passes"]

    burden_a = (materials.properties_of(material_a) or {}).get("annual_tpa", 0) * \
               (materials.properties_of(material_a) or {}).get("disposal_inr_t", 0)
    burden_b = (materials.properties_of(material_b) or {}).get("annual_tpa", 0) * \
               (materials.properties_of(material_b) or {}).get("disposal_inr_t", 0)

    if a_qualifies != b_qualifies:
        favour_a = not a_qualifies
        rationale = ("maximising the stream that cannot meet this specification "
                     "on its own")
    else:
        favour_a = burden_a >= burden_b
        rationale = ("neither stream is rescued by the other, so the blend "
                     "favours the larger annual disposal burden")

    if favour_a:
        recommended = max(f_min, math_floor_step(f_max))
    else:
        recommended = min(f_max, math_ceil_step(f_min))

    blend = blend_properties(props_a, props_b, recommended)
    report = conformance.grade_properties(
        blend, spec_name,
        material_label=f"{recommended:.0%} {material_a} + {1 - recommended:.0%} {material_b}")

    return {
        "material_a": material_a, "material_b": material_b, "spec": spec_name,
        "feasible": True, "f_min": f_min, "f_max": f_max,
        "f_recommended": recommended, "intervals": intervals, "blocking": [],
        "blend": blend, "report": report,
        "burden_a": burden_a, "burden_b": burden_b,
        "favoured": material_a if favour_a else material_b,
        "rationale": rationale,
        "a_qualifies_alone": a_qualifies, "b_qualifies_alone": b_qualifies,
        "reason": "",
    }


def math_floor_step(value: float) -> float:
    """Round down to the reporting step, staying inside the feasible range."""
    return int(value / STEP) * STEP


def math_ceil_step(value: float) -> float:
    """Round up to the reporting step, staying inside the feasible range."""
    stepped = int(value / STEP) * STEP
    return stepped if abs(stepped - value) < 1e-12 else stepped + STEP


def feasible_pairs(spec_name: str, limit: int = 12) -> list:
    """Every ordered pair of streams that can be blended to meet a specification.

    Used by the interface to suggest a pairing worth looking at rather than
    making the user hunt for one.
    """
    found = []
    names = materials.materials()
    for a in names:
        for b in names:
            if a >= b:
                continue
            result = blend_to_spec(a, b, spec_name)
            if not result["feasible"]:
                continue
            # A blend is only interesting if neither stream already qualifies.
            if conformance.grade(a, spec_name)["passes"] and \
               conformance.grade(b, spec_name)["passes"]:
                continue
            found.append((a, b, result["f_recommended"], result["report"]["grade"]))
            if len(found) >= limit:
                return found
    return found
