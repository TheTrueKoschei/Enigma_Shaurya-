"""Tests for Symbiosis Finder.

One test per acceptance criterion in the brief, plus the invariants that must
hold for the numbers on screen to mean anything.

Run with:  python -m pytest test_engine.py -v
"""

from __future__ import annotations

import io

import pandas as pd
import pytest

import engine
import explain
import kb

REGISTRY = "sample_facilities.csv"


@pytest.fixture(scope="module")
def facilities():
    clean, problems = engine.validate(pd.read_csv(REGISTRY))
    assert len(clean) > 0, "the sample registry must survive validation"
    return clean


@pytest.fixture(scope="module")
def matches(facilities):
    return engine.find_matches(facilities)


@pytest.fixture(scope="module")
def gaps(facilities, matches):
    return engine.unmatched_outputs(facilities, matches)


# ----------------------------------------------------------------------
# Knowledge base
# ----------------------------------------------------------------------

def test_knowledge_base_has_at_least_forty_substitutions():
    assert len(kb.SUBSTITUTIONS) >= 40


def test_knowledge_base_entries_are_well_formed():
    required = {
        "material", "application", "accepting_sectors", "replaces",
        "substitution_ratio", "max_share", "processing", "max_km",
        "co2_saved_t", "virgin_value", "hazard", "note",
    }
    for entry in kb.SUBSTITUTIONS:
        missing = required - set(entry)
        assert not missing, f"{entry.get('material')} is missing {missing}"
        assert entry["processing"] in engine.PROCESSING_FACTOR
        assert entry["hazard"] in ("none", "regulated")
        assert 0 < entry["max_share"] <= 1.0
        assert entry["max_km"] > 0
        assert entry["substitution_ratio"] > 0
        assert entry["accepting_sectors"], "an entry with no receiver sector can never match"
        assert entry["note"].strip(), "every entry must state its practical catch"


def test_knowledge_base_covers_the_required_materials():
    required = {
        "fly ash", "bottom ash", "FGD gypsum", "blast furnace slag", "steel slag",
        "mill scale", "coke oven gas", "waste heat", "bagasse", "press mud",
        "molasses", "spent wash", "rice husk", "rice husk ash", "sawdust",
        "lime sludge", "paper sludge", "textile ETP sludge", "cotton waste",
        "spent grain", "whey", "used cooking oil", "process CO2", "red mud",
        "spent pot lining", "recovered sulphur", "spent catalyst", "ferrous scrap",
        "RDF", "waste tyres", "glass cullet", "C&D waste",
    }
    known = {m.lower() for m in kb.materials()}
    assert {m.lower() for m in required} <= known


def test_fly_ash_in_cement_respects_is_1489():
    """IS 1489 caps fly ash in PPC at 35%. A naive matcher would allow 100%."""
    entry = next(e for e in kb.uses_for("fly ash") if "cement" in e["accepting_sectors"])
    assert entry["max_share"] == pytest.approx(0.35)


def test_bulky_materials_travel_less_far_than_valuable_ones():
    bagasse = max(e["max_km"] for e in kb.uses_for("bagasse"))
    catalyst = max(e["max_km"] for e in kb.uses_for("spent catalyst"))
    assert bagasse <= 200, "a low-value bulk residue cannot pay for a long haul"
    assert catalyst >= 1000, "recoverable metal supports a long haul"


# ----------------------------------------------------------------------
# Acceptance: the sample registry yields a spread of viable matches
# ----------------------------------------------------------------------

def test_sample_registry_yields_at_least_twenty_matches(matches):
    assert len(matches) >= 20


def test_scores_are_spread_not_clustered(matches):
    """Scores must occupy the range, not pile up in one band."""
    bands = pd.cut(matches["score"], bins=[35, 50, 65, 80, 100], include_lowest=True)
    occupied = bands.value_counts()
    assert (occupied > 0).sum() >= 4, f"scores clustered: {occupied.to_dict()}"
    assert matches["score"].max() - matches["score"].min() > 40
    assert matches["score"].std() > 8


def test_every_score_is_in_range_and_above_the_floor(matches):
    assert matches["score"].between(engine.MIN_SCORE_DEFAULT, 100.0).all()


def test_weights_sum_to_one():
    assert sum(engine.WEIGHTS.values()) == pytest.approx(1.0)


def test_score_equals_the_sum_of_its_weighted_contributions(matches):
    """The audit panel adds the points up in front of a judge; they must add up."""
    total = (matches["c_quantity"] + matches["c_proximity"] + matches["c_timing"]
             + matches["c_processing"] + matches["c_compliance"])
    assert (total - matches["score"]).abs().max() < 0.01


# ----------------------------------------------------------------------
# Acceptance: tonnage, self-matching and distance invariants
# ----------------------------------------------------------------------

def test_matched_tonnage_never_exceeds_supplier_output(matches):
    assert (matches["matched_tpa"] <= matches["supplier_output_tpa"] + 1e-9).all()


def test_matched_tonnage_never_exceeds_the_receiver_ceiling(matches):
    assert (matches["matched_tpa"] <= matches["ceiling_tpa"] + 1e-9).all()


def test_ceiling_is_the_receiver_need_times_max_share(matches):
    expected = matches["receiver_need_tpa"] * matches["max_share"]
    assert (matches["ceiling_tpa"] - expected).abs().max() < 1e-6


def test_no_self_matches(matches):
    assert (matches["supplier"] != matches["receiver"]).all()


def test_no_match_beyond_the_hard_distance_limit(matches):
    limit = matches["max_km"] * engine.DISTANCE_HARD_LIMIT
    assert (matches["road_km"] <= limit + 1e-9).all()


def test_no_match_below_the_minimum_tonnage(matches):
    assert (matches["matched_tpa"] >= engine.MIN_MATCH_TONNES).all()


def test_matches_beyond_max_km_score_zero_on_proximity(matches):
    beyond = matches[matches["beyond_max_km"]]
    if len(beyond):
        assert (beyond["f_proximity"] == 0.0).all()


def test_road_distance_is_the_straight_line_inflated(matches):
    expected = matches["straight_km"] * engine.ROAD_CIRCUITY_FACTOR
    assert (matches["road_km"] - expected).abs().max() < 1e-6


# ----------------------------------------------------------------------
# Acceptance: seasonality and compliance actually bite
# ----------------------------------------------------------------------

def test_at_least_one_seasonal_supplier_scores_below_one_on_timing(matches):
    seasonal = matches[matches["f_timing"] < 1.0]
    assert len(seasonal) >= 1
    assert seasonal["supplier_availability"].str.contains(
        "season|milling|flush", case=False, regex=True).any()


def test_regulated_materials_score_below_one_on_compliance(matches):
    regulated = matches[matches["hazard"] == "regulated"]
    assert len(regulated) >= 1, "the registry must exercise the regulated path"
    assert (regulated["f_compliance"] < 1.0).all()
    assert (matches[matches["hazard"] == "none"]["f_compliance"] == 1.0).all()


def test_unauthorised_receivers_score_worse_than_authorised_ones():
    assert (engine.COMPLIANCE_REGULATED_UNAUTHORISED
            < engine.COMPLIANCE_REGULATED_AUTHORISED
            < engine.COMPLIANCE_UNREGULATED)


def test_season_parsing():
    assert engine.active_months("crushing season (Nov-Apr)") == frozenset({11, 12, 1, 2, 3, 4})
    assert engine.active_months("kharif milling (Oct-Jan)") == frozenset({10, 11, 12, 1})
    assert engine.active_months("continuous (year-round)") == frozenset(range(1, 13))
    assert engine.active_months("") == frozenset(range(1, 13))
    assert engine.active_months(None) == frozenset(range(1, 13))
    # a six-month season against a year-round receiver covers half the year
    assert engine.timing_factor("crushing season (Nov-Apr)",
                                "continuous (year-round)") == pytest.approx(0.5)


# ----------------------------------------------------------------------
# Acceptance: the gap list has content
# ----------------------------------------------------------------------

def test_gap_list_is_not_empty(gaps):
    assert len(gaps) >= 1


def test_gaps_and_matches_are_disjoint(gaps, matches):
    placed = {(s, str(m).lower()) for s, m in zip(matches["supplier"], matches["material"])}
    for row in gaps.itertuples(index=False):
        assert (row.supplier, str(row.material).lower()) not in placed


def test_gaps_carry_a_disposal_cost_and_a_reason(gaps):
    assert (gaps["output_tpa"] > 0).all()
    assert (gaps["disposal_cost"] > 0).all()
    assert gaps["reason"].str.strip().astype(bool).all()


def test_gap_list_covers_both_kinds_of_failure(gaps):
    """A stream the knowledge base does not know, and one whose receivers are too far."""
    assert (gaps["recorded_uses"] == 0).any()
    assert (gaps["recorded_uses"] > 0).any()


# ----------------------------------------------------------------------
# Acceptance: bad matches are shown, not hidden
# ----------------------------------------------------------------------

def test_loss_making_matches_are_listed(matches):
    assert (matches["net_value"] < 0).any(), (
        "a tool that only finds good news is not believable - the sample registry "
        "must contain at least one exchange that costs more than it saves"
    )


def test_net_value_is_the_sum_of_its_components(matches):
    expected = (matches["material_value"] + matches["disposal_saved"]
                - matches["transport_cost"] - matches["processing_cost"])
    assert (matches["net_value"] - expected).abs().max() < 1e-6


def test_money_components_use_the_stated_constants(matches):
    transport = matches["matched_tpa"] * matches["road_km"] * matches["freight_rate"]
    assert (matches["transport_cost"] - transport).abs().max() < 1e-6
    material = (matches["matched_tpa"] * matches["substitution_ratio"]
                * matches["virgin_value"])
    assert (matches["material_value"] - material).abs().max() < 1e-6


# ----------------------------------------------------------------------
# Allocation: the same tonne is never promised twice
# ----------------------------------------------------------------------

def test_allocation_never_exceeds_the_pairwise_match(matches):
    assert (matches["allocated_tpa"] <= matches["matched_tpa"] + 1e-9).all()


def test_allocation_never_over_commits_a_supplier(matches):
    for (_, _), group in matches.groupby(["supplier", "material"]):
        assert group["allocated_tpa"].sum() <= group["supplier_output_tpa"].iloc[0] + 1e-6


def test_allocation_never_over_commits_a_receiver(matches):
    for _, group in matches.groupby("receiver"):
        assert group["allocated_tpa"].sum() <= group["receiver_need_tpa"].iloc[0] + 1e-6


# ----------------------------------------------------------------------
# Determinism
# ----------------------------------------------------------------------

def test_the_same_registry_always_produces_the_same_matches(facilities, matches):
    again = engine.find_matches(facilities)
    assert again.equals(matches)


def test_row_order_does_not_change_the_result(facilities, matches):
    shuffled = facilities.sample(frac=1.0, random_state=7).reset_index(drop=True)
    from_shuffled = engine.find_matches(shuffled)
    assert len(from_shuffled) == len(matches)
    pd.testing.assert_frame_equal(
        from_shuffled.drop(columns=["rank"]).reset_index(drop=True),
        matches.drop(columns=["rank"]).reset_index(drop=True),
    )


def test_ranks_are_dense_and_ordered_by_score(matches):
    assert list(matches["rank"]) == list(range(1, len(matches) + 1))
    assert matches["score"].is_monotonic_decreasing


# ----------------------------------------------------------------------
# Acceptance: a messy upload warns rather than crashing
# ----------------------------------------------------------------------

MESSY = """Facility Name,Industry,state,Latitude,Longitude,Waste Material,Waste TPA,demand_tpa,Season
Good Plant,cement,Madhya Pradesh,24.5667,80.8322,,0,2500000,continuous
Bad Coords,steel,Odisha,not-a-number,84.85,steel slag,50000,0,continuous
Off Planet,steel,Odisha,999,84.85,steel slag,50000,0,continuous
,thermal power,Chhattisgarh,22.35,82.69,fly ash,100000,0,continuous
Text Tonnage,thermal power,Chhattisgarh,22.35,82.69,fly ash,"lots, really",0,continuous
Negative Plant,sugar,Uttar Pradesh,29.47,77.70,molasses,-5000,-100,crushing season (Nov-Apr)
Unknown Stream,leather,Uttar Pradesh,26.45,80.33,unobtainium sludge,9000,0,continuous
"""


def test_messy_upload_produces_warnings_not_a_traceback():
    clean, problems = engine.validate(pd.read_csv(io.StringIO(MESSY)))
    assert len(problems) >= 5, problems
    joined = " ".join(problems).lower()
    assert "renamed" in joined                      # aliased column names
    assert "authorised_hazardous" in joined         # missing column filled
    assert "coordinates" in joined                  # bad coordinates dropped
    assert "non-numeric" in joined                  # text in a numeric field
    assert "negative" in joined                     # negative tonnage clamped
    assert "knowledge base" in joined               # unknown material flagged
    assert "Bad Coords" not in set(clean["name"])
    assert "Off Planet" not in set(clean["name"])
    assert "" not in set(clean["name"])
    assert (clean["output_tpa"] >= 0).all()
    # and the engine still runs on what survived
    engine.find_matches(clean)


def test_validate_survives_an_empty_or_useless_file():
    clean, problems = engine.validate(pd.DataFrame())
    assert clean.empty and problems
    clean, problems = engine.validate(pd.DataFrame({"name": ["only a name"]}))
    assert clean.empty and problems


def test_validate_returns_the_expected_columns(facilities):
    assert list(facilities.columns) == engine.REQUIRED_COLUMNS


def test_template_csv_round_trips_through_validate():
    clean, problems = engine.validate(pd.read_csv(io.StringIO(engine.template_csv())))
    assert len(clean) == 3
    assert not [p for p in problems if "missing" in p.lower()]


# ----------------------------------------------------------------------
# Acceptance: every match explains without error
# ----------------------------------------------------------------------

def test_every_match_produces_explanation_text(matches):
    seen_bands = set()
    for i in range(len(matches)):
        story = explain.explain(matches.iloc[i])
        assert story["headline"].strip()
        assert set(story["sections"]) == set(explain.SECTION_ORDER)
        for title, text in story["sections"].items():
            assert text.strip(), f"empty section {title} on row {i}"
        seen_bands.add(story["band"])
    assert len(seen_bands) >= 3, f"wording should vary by band, saw {seen_bands}"


def test_loss_making_explanations_say_so(matches):
    losses = matches[matches["net_value"] < 0]
    assert len(losses) >= 1
    for i in range(len(losses)):
        text = explain.explain(losses.iloc[i])["sections"]["What it is worth"]
        assert "does not pay for itself" in text
        assert "environmental case may still stand" in text


def test_every_gap_produces_explanation_text(gaps):
    for i in range(len(gaps)):
        assert explain.explain_gap(gaps.iloc[i]).strip()


def test_explanation_wording_differs_between_a_strong_and_a_weak_match(matches):
    best = explain.explain(matches.iloc[0])
    worst = explain.explain(matches.iloc[-1])
    assert best["band"] != worst["band"]
    assert best["headline"] != worst["headline"]


def test_explain_accepts_a_plain_dict(matches):
    as_dict = matches.iloc[0].to_dict()
    assert explain.explain(as_dict)["sections"]["What could be exchanged"].strip()


# ----------------------------------------------------------------------
# Summary and formatting
# ----------------------------------------------------------------------

def test_network_summary_does_not_double_count_supplier_tonnage(matches, facilities):
    summary = engine.network_summary(matches)
    assert summary["exchanges"] == len(matches)
    assert summary["tonnes_diverted"] <= matches["matched_tpa"].sum()
    assert summary["loss_making"] == int((matches["net_value"] < 0).sum())
    total_output = facilities["output_tpa"].sum()
    assert summary["allocated_tonnes"] <= total_output + 1e-6


def test_network_summary_of_nothing_is_zeroed():
    summary = engine.network_summary(engine._empty_matches())
    assert summary["exchanges"] == 0
    assert summary["tonnes_diverted"] == 0.0


def test_find_matches_on_an_empty_registry_returns_the_full_schema():
    empty = engine.find_matches(pd.DataFrame(columns=engine.REQUIRED_COLUMNS))
    assert empty.empty
    for column in ("score", "matched_tpa", "net_value", "allocated_tpa", "note"):
        assert column in empty.columns


def test_raising_the_threshold_only_removes_matches(facilities, matches):
    stricter = engine.find_matches(facilities, min_score=70.0)
    assert len(stricter) <= len(matches)
    assert (stricter["score"] >= 70.0).all()
    pairs = set(zip(matches["supplier"], matches["receiver"], matches["application"]))
    for row in stricter.itertuples(index=False):
        assert (row.supplier, row.receiver, row.application) in pairs


def test_currency_and_tonnage_formatting():
    assert engine.inr(123456789).startswith("₹") and "Cr" in engine.inr(123456789)
    assert "L" in engine.inr(450000)
    assert engine.inr(-450000).startswith("-")
    assert engine.inr("not a number") == "n/a"
    assert engine.tonnes(2400000) == "2.40 Mt"
    assert engine.tonnes(48000) == "48.0 kt"
    assert engine.tonnes(12) == "12 t"
    assert engine.tonnes(float("nan")) == "n/a"


def test_haversine_against_a_known_distance():
    """Bhilai to Jamshedpur: 4.85 deg of longitude at 22 N plus 1.61 deg of
    latitude works out near 530 km great-circle."""
    d = engine.haversine_km(21.1938, 81.3509, 22.8046, 86.2029)
    assert 515 < d < 545
    assert engine.haversine_km(21.0, 81.0, 21.0, 81.0) == pytest.approx(0.0)


# ----------------------------------------------------------------------
# "What could my plant do?" - a facility the user describes
# ----------------------------------------------------------------------

def test_build_facility_matches_the_registry_schema():
    one = engine.build_facility("My plant", "Cement", "Madhya Pradesh", 23.18, 79.98,
                                input_need_tpa=1_200_000, authorised_hazardous=True)
    assert list(one.columns) == engine.REQUIRED_COLUMNS
    assert one.iloc[0]["sector"] == "cement"          # normalised like validate() does
    assert one.iloc[0]["authorised_hazardous"] is True or bool(one.iloc[0]["authorised_hazardous"])


def test_a_described_receiver_gets_a_ranked_list(facilities):
    me = engine.build_facility("My plant", "cement", "Maharashtra", 21.1458, 79.0882,
                               input_need_tpa=1_200_000)
    mine = engine.matches_for_facility(facilities, me)
    assert len(mine) >= 3
    assert list(mine["rank"]) == list(range(1, len(mine) + 1))
    assert mine["score"].is_monotonic_decreasing
    assert (mine["receiver"] == "My plant").all()
    assert (mine["role"] == "receiver").all()
    assert (mine["partner"] == mine["supplier"]).all()


def test_a_described_supplier_gets_a_ranked_list(facilities):
    me = engine.build_facility("My plant", "thermal power", "Maharashtra", 21.1458, 79.0882,
                               output_material="fly ash", output_tpa=250_000)
    mine = engine.matches_for_facility(facilities, me)
    assert len(mine) >= 1
    assert (mine["supplier"] == "My plant").all()
    assert (mine["role"] == "supplier").all()
    assert (mine["partner"] == mine["receiver"]).all()


def test_my_plant_is_scored_by_the_same_engine(facilities):
    """A described plant must not get special treatment - same weights, same gates."""
    me = engine.build_facility("My plant", "cement", "Maharashtra", 21.1458, 79.0882,
                               input_need_tpa=1_200_000)
    mine = engine.matches_for_facility(facilities, me)
    assert len(mine)
    total = (mine["c_quantity"] + mine["c_proximity"] + mine["c_timing"]
             + mine["c_processing"] + mine["c_compliance"])
    assert (total - mine["score"]).abs().max() < 0.01
    assert (mine["score"] >= engine.MIN_SCORE_DEFAULT).all()
    assert (mine["matched_tpa"] <= mine["ceiling_tpa"] + 1e-9).all()
    assert (mine["road_km"] <= mine["max_km"] * engine.DISTANCE_HARD_LIMIT + 1e-9).all()


def test_my_plant_never_matches_itself_or_duplicates_a_registry_row(facilities):
    """Describing a plant that shares a registry name must replace it, not clone it."""
    existing = facilities.iloc[0]["name"]
    me = engine.build_facility(existing, "cement", "Maharashtra", 21.1458, 79.0882,
                               input_need_tpa=900_000)
    mine = engine.matches_for_facility(facilities, me)
    assert (mine["supplier"] != mine["receiver"]).all()
    for row in mine.itertuples(index=False):
        assert row.partner != existing


def test_authorisation_changes_a_regulated_match_for_my_plant(facilities):
    """The compliance factor must respond to the toggle the interface offers."""
    def best_regulated(authorised):
        me = engine.build_facility("My plant", "cement", "Odisha", 21.3333, 83.6167,
                                   input_need_tpa=1_800_000,
                                   authorised_hazardous=authorised)
        mine = engine.matches_for_facility(facilities, me, min_score=0.0)
        regulated = mine[mine["hazard"] == "regulated"]
        return regulated

    without = best_regulated(False)
    with_auth = best_regulated(True)
    assert len(without) and len(with_auth)
    assert (without["f_compliance"] == engine.COMPLIANCE_REGULATED_UNAUTHORISED).all()
    assert (with_auth["f_compliance"] == engine.COMPLIANCE_REGULATED_AUTHORISED).all()
    assert with_auth["score"].max() > without["score"].max()


def test_matches_for_facility_with_nothing_to_offer_is_empty(facilities):
    me = engine.build_facility("My plant", "cement", "Kerala", 9.93, 76.27)
    assert engine.matches_for_facility(facilities, me).empty
    assert engine.matches_for_facility(facilities, None).empty


def test_season_presets_all_parse():
    for label, value in engine.SEASON_PRESETS.items():
        months = engine.active_months(value)
        assert 1 <= len(months) <= 12, f"{label} parsed to {months}"
    assert len(engine.active_months(engine.SEASON_PRESETS["Year-round"])) == 12
    assert len(engine.active_months(
        engine.SEASON_PRESETS["Sugar crushing season (Nov-Apr)"])) == 6


def test_sector_and_material_lookups_agree_with_the_knowledge_base():
    for sector in kb.sectors():
        materials = engine.materials_for_sector(sector)
        assert materials, f"{sector} accepts nothing"
        for material in materials:
            assert sector in engine.sectors_for_material(material)
    assert "cement" in engine.sectors_for_material("fly ash")
    assert engine.materials_for_sector("not a real sector") == []


# ----------------------------------------------------------------------
# State rollup and the bundled map
# ----------------------------------------------------------------------

def test_state_activity_totals_reconcile(facilities, matches):
    activity = engine.state_activity(matches, facilities)
    assert len(activity) >= 1
    assert activity["facilities"].sum() == len(facilities)
    assert activity["tonnes_supplied"].sum() == pytest.approx(matches["allocated_tpa"].sum())
    assert activity["tonnes_received"].sum() == pytest.approx(matches["allocated_tpa"].sum())
    assert (activity["exchanges"] >= 0).all()


def test_state_activity_of_nothing_still_lists_the_registry(facilities):
    activity = engine.state_activity(engine._empty_matches(), facilities)
    assert len(activity) >= 1
    assert activity["exchanges"].sum() == 0
    assert activity["facilities"].sum() == len(facilities)


def test_bundled_state_boundaries_are_usable(facilities):
    """The map draws from this file, so nothing is fetched at render time."""
    import json
    import os
    path = "data/india_states.geojson"
    assert os.path.exists(path), "the map's boundary data must ship with the app"
    assert os.path.getsize(path) < 2_000_000, "keep the bundled geometry small enough to draw"
    with open(path, encoding="utf-8") as fh:
        geo = json.load(fh)
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) >= 30
    named = {f["properties"]["state"] for f in geo["features"]}
    for feature in geo["features"]:
        assert feature["geometry"]["type"] == "MultiPolygon"
        for polygon in feature["geometry"]["coordinates"]:
            for ring in polygon:
                assert len(ring) >= 4
                assert ring[0] == ring[-1], "every ring must close"
                for lon, lat in ring:
                    assert 67.0 <= lon <= 98.5 and 6.0 <= lat <= 37.5
    # every state in the sample registry must be paintable on the map
    missing = {str(s) for s in facilities["state"].unique()} - named
    assert not missing, f"no boundary for {missing}"
