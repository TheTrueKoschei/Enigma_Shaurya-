"""Tests for the materials-intelligence layer.

Covers the property model, the specification library and conformance grading.
The blending and carbon tests live here too once those modules exist.
"""

from __future__ import annotations

import pytest

import conformance
import materials
import specs

IS3812_P1 = "Fly ash for structural concrete (IS 3812 Part 1)"
IS3812_P2 = "Fly ash as admixture, PPC and mortar (IS 3812 Part 2)"
C618_N = "Pozzolanic SCM, natural pozzolana class (ASTM C618 Class N)"
GGBS_SPEC = "GGBS for Portland slag cement (IS 16714)"


# ----------------------------------------------------------------------
# Property model
# ----------------------------------------------------------------------

def test_every_material_has_a_usable_property_vector():
    assert len(materials.MATERIAL_PROPERTIES) >= 12
    for name in materials.materials():
        measured = materials.measured_properties(name)
        assert measured, f"{name} has no measured properties"
        for key, value in measured.items():
            assert key in materials.PROPERTY_KEYS, f"{name}: unknown property {key}"
            assert isinstance(value, (int, float)), f"{name}.{key} is not numeric"
            assert value >= 0, f"{name}.{key} is negative"


def test_oxide_totals_are_physically_plausible():
    """Oxides plus loss on ignition cannot exceed 100% of the mass."""
    oxides = ("sio2", "al2o3", "fe2o3", "cao", "mgo", "so3")
    for name in materials.materials():
        props = materials.measured_properties(name)
        total = sum(props.get(k, 0.0) for k in oxides) + props.get("loi", 0.0)
        assert total <= 103.0, f"{name} oxides + LOI = {total:.1f}%"


def test_the_three_fly_ashes_are_genuinely_different():
    """The whole premise is that 'fly ash' is not one material."""
    ashes = [n for n in materials.materials() if n.startswith("Fly ash")]
    assert len(ashes) >= 3
    lois = {materials.measured_properties(n)["loi"] for n in ashes}
    fineness = {materials.measured_properties(n)["fineness_m2kg"] for n in ashes}
    assert len(lois) == len(ashes), "the ashes must differ on unburnt carbon"
    assert len(fineness) == len(ashes), "the ashes must differ on fineness"


def test_unknown_material_returns_none_rather_than_raising():
    assert materials.properties_of("unobtainium") is None
    assert materials.measured_properties("unobtainium") == {}


# ----------------------------------------------------------------------
# Specification library
# ----------------------------------------------------------------------

def test_specs_are_well_formed_and_reference_real_properties():
    assert len(specs.SPECS) >= 15
    for name, entry in specs.SPECS.items():
        assert entry["confidence"] in ("standard", "indicative"), name
        assert entry["standard"].strip(), name
        assert entry["note"].strip(), f"{name} must say where its limits come from"
        assert entry["value_inr_t"] > 0, name
        assert entry["limits"], name
        for expression, operator, threshold, unit_note in entry["limits"]:
            assert operator in (">=", "<="), f"{name}: bad operator {operator}"
            assert isinstance(threshold, (int, float))
            assert unit_note.strip()
            for part in expression.split("+"):
                assert part.strip() in materials.PROPERTY_KEYS, \
                    f"{name} refers to unknown property {part}"


def test_the_library_spans_a_real_value_range():
    values = [entry["value_inr_t"] for entry in specs.SPECS.values()]
    assert min(values) <= 500, "there must be a low-value floor to cascade down to"
    assert max(values) >= 20000, "there must be a high-value rung to aspire to"


def test_is_3812_part_1_limits_match_the_standard():
    """These are the numbers a judge is most likely to check."""
    entry = specs.spec(IS3812_P1)
    limits = {expression: (operator, threshold)
              for expression, operator, threshold, _ in entry["limits"]}
    assert limits["sio2+al2o3+fe2o3"] == (">=", 70.0)
    assert limits["sio2"] == (">=", 35.0)
    assert limits["loi"] == ("<=", 5.0)
    assert limits["moisture"] == ("<=", 2.0)
    assert limits["fineness_m2kg"] == (">=", 320)
    assert limits["so3"] == ("<=", 3.0)
    assert limits["mgo"] == ("<=", 5.0)
    assert limits["alkali_na2oeq"] == ("<=", 1.5)
    assert limits["retained_45um"] == ("<=", 34.0)
    assert entry["confidence"] == "standard"


# ----------------------------------------------------------------------
# Expression resolution
# ----------------------------------------------------------------------

def test_sum_expressions_add_their_parts():
    props = materials.measured_properties("Fly ash (Korba STPS)")
    value, missing = conformance.resolve("sio2+al2o3+fe2o3", props)
    assert not missing
    assert value == pytest.approx(props["sio2"] + props["al2o3"] + props["fe2o3"])


def test_a_missing_component_makes_the_whole_expression_unassessable():
    """An unmeasured oxide must not be silently treated as zero."""
    props = materials.measured_properties("Mill scale (Durgapur Steel Plant)")
    assert "glass_content" not in props
    value, missing = conformance.resolve("glass_content", props)
    assert value is None and missing == ["glass_content"]


# ----------------------------------------------------------------------
# Grading
# ----------------------------------------------------------------------

def test_grade_is_deterministic():
    first = conformance.grade("Fly ash (Korba STPS)", IS3812_P1)
    second = conformance.grade("Fly ash (Korba STPS)", IS3812_P1)
    assert first["grade"] == second["grade"]
    assert first["passes"] == second["passes"]
    assert [r["actual"] for r in first["results"]] == [r["actual"] for r in second["results"]]


def test_a_clean_ash_passes_structural_concrete_grade():
    report = conformance.grade("Fly ash (Vindhyachal STPS)", IS3812_P1)
    assert report["passes"]
    assert report["grade"] == "A"
    assert not report["failures"]
    assert report["binding"] is not None


def test_a_marginal_ash_passes_but_only_just():
    report = conformance.grade("Fly ash (Korba STPS)", IS3812_P1)
    assert report["passes"]
    assert report["grade"] == "B", "a stream inside the limit but without headroom is a B"
    assert report["binding"]["headroom_frac"] < conformance.GRADE_A_HEADROOM


def test_a_poor_ash_fails_and_says_exactly_why():
    report = conformance.grade("Fly ash (Talcher TPS)", IS3812_P1)
    assert not report["passes"]
    assert report["grade"] == "D"
    failing = {f["property"] for f in report["failures"]}
    assert {"loi", "fineness_m2kg", "retained_45um"} <= failing
    worst = report["failures"][0]
    assert worst["property"] == "loi", "failures must be sorted worst-miss first"
    assert worst["actual"] == 7.8 and worst["threshold"] == 5.0
    assert worst["margin"] == pytest.approx(-2.8)


def test_every_limit_result_carries_its_arithmetic():
    """A verdict with no numbers behind it is not inspectable."""
    report = conformance.grade("Fly ash (Talcher TPS)", IS3812_P1)
    for result in report["results"]:
        assert result["property"] and result["operator"]
        assert result["threshold"] is not None
        if result["measured"]:
            assert result["actual"] is not None
            assert result["margin"] is not None
            assert result["headroom_frac"] is not None
            # margin must agree with the operator's direction
            if result["operator"] == ">=":
                assert result["margin"] == pytest.approx(result["actual"] - result["threshold"])
            else:
                assert result["margin"] == pytest.approx(result["threshold"] - result["actual"])
            assert result["passes"] == (result["margin"] >= 0)


def test_an_unmeasured_property_never_counts_as_a_pass():
    """Mill scale has no glass content, so it cannot pass a slag specification."""
    report = conformance.grade("Mill scale (Durgapur Steel Plant)", GGBS_SPEC)
    assert not report["passes"]
    unmeasured = [r for r in report["results"] if not r["measured"]]
    assert unmeasured, "the missing property must be reported, not skipped"
    assert all(not r["passes"] for r in unmeasured)
    assert report["grade"] == "D"


def test_ratio_rules_are_reported_separately_from_the_limit_table():
    report = conformance.grade("GGBS (Bhilai Steel Plant)", GGBS_SPEC)
    assert report["ratios"], "IS 16714's basicity ratio must be checked"
    ratio = report["ratios"][0]
    props = materials.measured_properties("GGBS (Bhilai Steel Plant)")
    expected = (props["cao"] + props["mgo"]) / props["sio2"]
    assert ratio["actual"] == pytest.approx(expected)
    assert ratio["passes"] is True
    assert report["passes"], "good GGBS should clear IS 16714"


def test_steel_slag_fails_slag_cement_on_glass_content():
    report = conformance.grade("Steel slag (Rourkela Steel Plant)", GGBS_SPEC)
    assert not report["passes"]
    assert "glass_content" in {f["property"] for f in report["failures"]}


def test_binding_property_is_the_tightest_one():
    report = conformance.grade("Fly ash (Korba STPS)", IS3812_P1)
    measured = [r for r in report["results"] if r["measured"]]
    tightest = min(measured, key=lambda r: r["headroom_frac"])
    assert report["binding"]["property"] == tightest["property"]


def test_grade_of_an_unknown_material_or_spec_is_safe():
    assert conformance.grade("unobtainium", IS3812_P1)["grade"] == "D"
    assert conformance.grade("Fly ash (Korba STPS)", "no such spec")["grade"] == "D"


# ----------------------------------------------------------------------
# Value cascade
# ----------------------------------------------------------------------

def test_cascade_is_ranked_by_value_and_marks_qualification():
    ladder = conformance.cascade("Fly ash (Korba STPS)")
    values = [r["value_inr_t"] for r in ladder["rungs"]]
    assert values == sorted(values, reverse=True)
    assert all(r["passes"] for r in ladder["qualifying"])
    assert ladder["best_qualifying_value"] == max(
        (r["value_inr_t"] for r in ladder["qualifying"]), default=0)


def test_a_poor_stream_fails_a_high_value_spec_but_clears_a_lower_one():
    """The cascade needs something to show - this is that case."""
    high = conformance.grade("Fly ash (Talcher TPS)", IS3812_P1)
    low = conformance.grade("Fly ash (Talcher TPS)", IS3812_P2)
    assert not high["passes"], "Talcher ash must fail structural concrete grade"
    assert low["passes"], "but must still clear the admixture grade"
    assert specs.spec(IS3812_P2)["value_inr_t"] < specs.spec(IS3812_P1)["value_inr_t"]


def test_quality_discount_is_the_gap_to_the_best_use_in_the_library():
    ladder = conformance.cascade("Fly ash (Talcher TPS)")
    _, best_value = specs.highest_value()
    assert ladder["library_best_value"] == best_value
    assert ladder["quality_discount"] == best_value - ladder["best_qualifying_value"]
    assert ladder["quality_discount"] > 0


def test_nearest_upgrade_is_the_closest_rung_not_the_richest():
    """Advice has to be actionable: the reachable rung, not the most valuable."""
    ladder = conformance.cascade("Fly ash (Talcher TPS)")
    upgrade = ladder["nearest_upgrade"]
    assert upgrade is not None
    assert upgrade["value_inr_t"] > ladder["best_qualifying_value"]
    worst_miss = max(abs(f["headroom_frac"]) for f in upgrade["failures"]
                     if f["headroom_frac"] is not None)
    # no other blocked rung above the achieved value comes closer
    for rung in ladder["rungs"]:
        if rung["passes"] or rung["value_inr_t"] <= ladder["best_qualifying_value"]:
            continue
        if any(not f["measured"] for f in rung["failures"]):
            continue
        other = max(abs(f["headroom_frac"]) for f in rung["failures"]
                    if f["headroom_frac"] is not None)
        assert worst_miss <= other + 1e-9


def test_every_material_cascades_without_error():
    for name in materials.materials():
        ladder = conformance.cascade(name)
        assert len(ladder["rungs"]) == len(specs.SPECS)
        assert ladder["quality_discount"] >= 0


# ----------------------------------------------------------------------
# Blending
# ----------------------------------------------------------------------

import blending

TALCHER = "Fly ash (Talcher TPS)"
VINDHYACHAL = "Fly ash (Vindhyachal STPS)"
RED_MUD = "Red mud (Lanjigarh alumina refinery)"
BOTTOM_ASH = "Bottom ash (Singrauli STPS)"


def test_blend_at_the_endpoints_reduces_to_the_pure_materials():
    """f = 1 must be pure A and f = 0 pure B, or the mixing maths is wrong."""
    a = materials.measured_properties(TALCHER)
    b = materials.measured_properties(VINDHYACHAL)
    at_one = blending.blend_properties(a, b, 1.0)
    at_zero = blending.blend_properties(a, b, 0.0)
    for key in set(a) & set(b):
        assert at_one[key] == pytest.approx(a[key]), key
        assert at_zero[key] == pytest.approx(b[key]), key


def test_blend_is_linear_in_the_mass_fraction():
    a = materials.measured_properties(TALCHER)
    b = materials.measured_properties(VINDHYACHAL)
    half = blending.blend_properties(a, b, 0.5)
    for key in set(a) & set(b):
        assert half[key] == pytest.approx((a[key] + b[key]) / 2.0), key
    quarter = blending.blend_properties(a, b, 0.25)
    for key in set(a) & set(b):
        assert quarter[key] == pytest.approx(0.25 * a[key] + 0.75 * b[key]), key


def test_a_failing_ash_can_be_blended_into_specification():
    """The demonstration case: neither trucking nor processing, just chemistry."""
    assert not conformance.grade(TALCHER, IS3812_P1)["passes"]
    assert conformance.grade(VINDHYACHAL, IS3812_P1)["passes"]

    result = blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)
    assert result["feasible"]
    assert 0.0 < result["f_recommended"] <= result["f_max"]
    assert result["report"]["passes"], "the recommended blend must actually pass"


def test_the_recommendation_maximises_the_stream_that_needs_rescuing():
    """Recommending 0% of the problem stream would create nothing."""
    result = blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)
    assert result["favoured"] == TALCHER
    assert result["f_recommended"] >= result["f_max"] - blending.STEP - 1e-9
    assert result["f_recommended"] > 0.4, "should place a substantial share of it"


def test_the_recommended_ratio_is_inside_the_feasible_range():
    for a, b, spec_name in [
        (TALCHER, VINDHYACHAL, IS3812_P1),
        (TALCHER, VINDHYACHAL, IS3812_P2),
        ("Bagasse ash (Kolhapur sugar complex)", VINDHYACHAL, IS3812_P2),
    ]:
        result = blending.blend_to_spec(a, b, spec_name)
        if not result["feasible"]:
            continue
        assert result["f_min"] - 1e-9 <= result["f_recommended"] <= result["f_max"] + 1e-9
        assert 0.0 <= result["f_recommended"] <= 1.0


def test_every_limit_holds_across_the_whole_feasible_range():
    """The interval maths must agree with grading the blend directly."""
    result = blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)
    assert result["feasible"]
    a = materials.measured_properties(TALCHER)
    b = materials.measured_properties(VINDHYACHAL)
    lo, hi = result["f_min"], result["f_max"]
    for f in (lo, (lo + hi) / 2.0, hi):
        blended = blending.blend_properties(a, b, f)
        report = conformance.grade_properties(blended, IS3812_P1)
        assert report["passes"], f"blend at f={f:.3f} should satisfy every limit"


def test_just_outside_the_feasible_range_actually_fails():
    """A range that is not tight is not a range."""
    result = blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)
    assert result["feasible"]
    a = materials.measured_properties(TALCHER)
    b = materials.measured_properties(VINDHYACHAL)
    beyond = result["f_max"] + 0.05
    if beyond <= 1.0:
        report = conformance.grade_properties(
            blending.blend_properties(a, b, beyond), IS3812_P1)
        assert not report["passes"], "past f_max the blend must fail"


def test_an_impossible_blend_names_the_limits_that_block_it():
    result = blending.blend_to_spec(RED_MUD, BOTTOM_ASH, IS3812_P1)
    assert not result["feasible"]
    assert result["blocking"], "an infeasible blend must say which limit stops it"
    assert result["reason"]
    for block in result["blocking"]:
        assert block["property"]
        assert block["value_a"] is not None or block["value_b"] is not None


def test_blending_a_stream_with_itself_is_refused():
    result = blending.blend_to_spec(TALCHER, TALCHER, IS3812_P1)
    assert not result["feasible"]
    assert "different" in result["reason"].lower()


def test_blend_of_unknown_material_is_safe():
    result = blending.blend_to_spec("unobtainium", VINDHYACHAL, IS3812_P1)
    assert not result["feasible"]
    assert result["reason"]


def test_blend_is_deterministic():
    first = blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)
    second = blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)
    assert first["f_recommended"] == second["f_recommended"]
    assert first["f_min"] == second["f_min"] and first["f_max"] == second["f_max"]


def test_both_a_feasible_and_an_infeasible_pair_exist_to_demonstrate():
    assert blending.blend_to_spec(TALCHER, VINDHYACHAL, IS3812_P1)["feasible"]
    assert not blending.blend_to_spec(RED_MUD, BOTTOM_ASH, IS3812_P1)["feasible"]


# ----------------------------------------------------------------------
# Carbon intensity and CCTS
# ----------------------------------------------------------------------

import carbon


def test_raising_the_scm_share_lowers_the_intensity_monotonically():
    shares = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]
    intensities = [carbon.cement_intensity(s) for s in shares]
    assert intensities == sorted(intensities, reverse=True)
    assert all(i > 0 for i in intensities)


def test_intensity_matches_the_stated_clinker_model():
    share = 0.30
    clinker_factor = 1.0 - carbon.GYPSUM_SHARE - share
    expected = (clinker_factor * carbon.CLINKER_EMISSION_FACTOR
                + carbon.CEMENT_OTHER_EMISSIONS)
    assert carbon.cement_intensity(share) == pytest.approx(expected)


def test_scm_share_is_clamped_to_something_physical():
    """Gypsum still has to be in the cement, so the share cannot reach 1.0."""
    assert carbon.cement_intensity(1.5) == carbon.cement_intensity(1.0 - carbon.GYPSUM_SHARE)
    assert carbon.cement_intensity(-0.2) == carbon.cement_intensity(0.0)


def test_certificates_are_the_intensity_gap_times_production():
    result = carbon.assess("Satna Cement Works", 0.35)
    entry = carbon.plant("Satna Cement Works")
    expected = ((entry["target_gei"] - carbon.cement_intensity(0.35))
                * entry["annual_production_t"])
    assert result["certificates"] == pytest.approx(expected)


def test_a_plant_can_move_from_shortfall_into_compliance():
    """The story the tab tells has to be true of the numbers."""
    before = carbon.assess("Satna Cement Works", 0.18)
    after = carbon.assess("Satna Cement Works", 0.35)
    assert not before["compliant"] and before["certificates"] < 0
    assert after["compliant"] and after["certificates"] > 0
    assert after["co2_avoided_t"] > 0


def test_shortfall_exposure_uses_the_doubled_penalty():
    short = carbon.assess("Satna Cement Works", 0.18, certificate_price=2000)
    assert short["certificates"] < 0
    assert short["exposure_at_penalty_inr"] == pytest.approx(
        short["certificates"] * 2000 * carbon.PENALTY_MULTIPLE)
    # a compliant plant has no penalty exposure
    good = carbon.assess("Satna Cement Works", 0.35, certificate_price=2000)
    assert good["exposure_at_penalty_inr"] == 0.0


def test_every_rupee_figure_scales_with_the_price_assumption():
    """No rupee number may be baked in - the price is an assumption, not a fact."""
    low = carbon.assess("Satna Cement Works", 0.35, certificate_price=1000)
    high = carbon.assess("Satna Cement Works", 0.35, certificate_price=2000)
    assert high["position_inr"] == pytest.approx(2 * low["position_inr"])
    assert high["value_of_change_inr"] == pytest.approx(2 * low["value_of_change_inr"])
    # the physical quantities must not move with the price
    assert low["actual_gei"] == high["actual_gei"]
    assert low["co2_avoided_t"] == high["co2_avoided_t"]
    assert low["certificates"] == high["certificates"]


def test_compare_options_returns_one_row_per_option():
    options = [
        {"label": "baseline", "scm_share": 0.18, "cost_inr_t": 4200,
         "quality_margin": None, "meets_spec": True},
        {"label": "blended ash", "scm_share": 0.35, "cost_inr_t": 900,
         "quality_margin": 0.7, "meets_spec": True},
    ]
    rows = carbon.compare_options("Satna Cement Works", options)
    assert len(rows) == 2
    assert rows[1]["co2_t_yr"] < rows[0]["co2_t_yr"]
    assert rows[1]["certificates"] > rows[0]["certificates"]


def test_unknown_plant_is_safe():
    assert carbon.assess("no such plant", 0.3)["found"] is False
    assert carbon.compare_options("no such plant", [{"label": "x", "scm_share": 0.3}]) == []


def test_assess_is_deterministic():
    first = carbon.assess("Wadi Cement Plant", 0.32, 2500)
    second = carbon.assess("Wadi Cement Plant", 0.32, 2500)
    assert first == second
