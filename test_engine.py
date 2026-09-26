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
    # Rail adds a per-tonne terminal charge on top of the distance rate; road and
    # pipeline carry none, so this covers all three modes.
    transport = (matches["matched_tpa"] * matches["road_km"] * matches["freight_rate"]
                 + matches["matched_tpa"] * matches["terminal_rate"])
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


# ----------------------------------------------------------------------
# Transport mode: rail against road
# ----------------------------------------------------------------------

def test_rail_is_only_chosen_when_it_is_actually_cheaper():
    entry = {"processing": "none"}
    # short haul, large tonnage -> road
    mode, _, _ = engine.choose_transport(entry, 500_000, 120)
    assert mode == "road"
    # long haul, small tonnage -> road, no rake available
    mode, _, _ = engine.choose_transport(entry, 500, 900)
    assert mode == "road"
    # long haul, large tonnage -> rail, and it must genuinely undercut road
    mode, rate, terminal = engine.choose_transport(entry, 500_000, 900)
    assert mode == "rail"
    assert 900 * rate + terminal < 900 * engine.FREIGHT_RATE
    # pipeline streams have no choice
    mode, rate, terminal = engine.choose_transport(
        {"processing": "none", "transport_mode": "pipeline"}, 500_000, 900)
    assert mode == "pipeline" and rate == engine.PIPELINE_RATE and terminal == 0.0


def test_transport_cost_includes_terminal_handling(matches):
    expected = (matches["matched_tpa"] * matches["road_km"] * matches["freight_rate"]
                + matches["matched_tpa"] * matches["terminal_rate"])
    assert (matches["transport_cost"] - expected).abs().max() < 1e-6


def test_rail_never_costs_more_than_road_would_have(matches):
    rail = matches[matches["transport_mode"] == "rail"]
    assert len(rail) >= 1, "the sample registry should exercise the rail path"
    road_equivalent = rail["matched_tpa"] * rail["road_km"] * engine.FREIGHT_RATE
    assert (rail["transport_cost"] < road_equivalent).all()
    assert (rail["road_km"] >= engine.RAIL_MIN_KM).all()
    assert (rail["matched_tpa"] >= engine.RAIL_MIN_TONNES).all()


# ----------------------------------------------------------------------
# Analogue discovery
# ----------------------------------------------------------------------

def test_every_knowledge_base_material_has_a_property_profile():
    for material in kb.materials():
        profile = kb.profile_for(material)
        assert profile is not None, f"{material} has no profile"
        assert set(profile) == set(kb.PROFILE_KEYS)
        for key, value in profile.items():
            assert 0.0 <= value <= 1.0, f"{material}.{key} = {value} is out of range"


def test_profile_similarity_is_symmetric_and_bounded():
    assert engine.profile_similarity("fly ash", "fly ash") == pytest.approx(1.0)
    ab = engine.profile_similarity("fly ash", "blast furnace slag")
    ba = engine.profile_similarity("blast furnace slag", "fly ash")
    assert ab == pytest.approx(ba)
    assert 0.0 <= ab <= 1.0
    assert engine.profile_similarity("fly ash", "not a material") is None


def test_analogues_are_ranked_and_chemically_sensible():
    """A stream with no recorded use must still point somewhere defensible."""
    found = engine.analogues("jarosite", top_n=5)
    assert len(found) == 5
    assert found["similarity"].is_monotonic_decreasing
    assert (found["recorded_uses"] > 0).all(), "an analogue with no uses helps nobody"
    assert "jarosite" not in set(found["material"])
    # jarosite is an iron-sulphate residue; its nearest analogues should be other
    # sulphur- or iron-bearing residues, not a dry fuel
    assert found.iloc[0]["similarity"] > 0.7
    assert "sulphur" in found.iloc[0]["shared_properties"] or "iron" in found.iloc[0]["shared_properties"]


def test_analogues_for_cement_kiln_dust_find_the_lime_bearing_streams():
    found = engine.analogues("cement kiln dust", top_n=3)
    assert "lime" in " ".join(found["shared_properties"]).lower()
    assert {"lime sludge", "steel slag", "blast furnace slag"} & set(found["material"])


def test_analogues_of_an_unknown_material_is_empty_not_an_error():
    assert engine.analogues("unobtainium sludge").empty


def test_every_unplaced_stream_gets_at_least_one_analogue(gaps):
    for material in gaps["material"]:
        found = engine.analogues(material, top_n=3)
        assert len(found) >= 1, f"{material} has no analogue to suggest"


# ----------------------------------------------------------------------
# Multi-hop chains
# ----------------------------------------------------------------------

def test_chains_are_found_and_well_formed(matches):
    chains = engine.find_chains(matches)
    assert len(chains) >= 1
    assert (chains["hops"] >= 2).all()
    assert chains["weakest_score"].is_monotonic_decreasing
    for row in chains.itertuples(index=False):
        names = row.path.split(" -> ")
        assert len(names) == len(set(names)), "a facility must not repeat in a chain"
        assert len(names) == row.hops + 1
        stages = row.materials.split(" then ")
        assert len(stages) == row.hops
        assert len(set(stages)) == len(stages), "consecutive hops must move different materials"


def test_chain_links_are_real_matches(matches):
    chains = engine.find_chains(matches, limit=10)
    pairs = set(zip(matches["supplier"], matches["receiver"]))
    for row in chains.itertuples(index=False):
        names = row.path.split(" -> ")
        for a, b in zip(names, names[1:]):
            assert (a, b) in pairs


def test_find_chains_on_nothing_is_empty():
    assert engine.find_chains(engine._empty_matches()).empty
    assert engine.find_chains(None).empty


# ----------------------------------------------------------------------
# Network optimisation
# ----------------------------------------------------------------------

def test_optimiser_respects_every_constraint(matches):
    optimised, report = engine.optimise_network(matches)
    assert "optimised_tpa" in optimised
    assert (optimised["optimised_tpa"] >= -1e-6).all()
    assert (optimised["optimised_tpa"] <= optimised["matched_tpa"] + 1e-6).all()
    for _, group in optimised.groupby(["supplier", "material"]):
        assert group["optimised_tpa"].sum() <= group["supplier_output_tpa"].iloc[0] + 1e-3
    for _, group in optimised.groupby(["receiver", "material"]):
        assert group["optimised_tpa"].sum() <= group["ceiling_tpa"].iloc[0] + 1e-3
    for _, group in optimised.groupby("receiver"):
        assert group["optimised_tpa"].sum() <= group["receiver_need_tpa"].iloc[0] + 1e-3


def test_optimiser_is_at_least_as_good_as_greedy(matches):
    optimised, report = engine.optimise_network(matches)
    if report["solver"].startswith("linear"):
        assert report["improvement"] >= -1e-3
        assert optimised["optimised_net_value"].sum() >= matches["allocated_net_value"].sum() - 1e-3


def test_optimiser_declines_loss_making_exchanges(matches):
    optimised, report = engine.optimise_network(matches)
    if report["solver"].startswith("linear"):
        losses = optimised[optimised["net_value"] < 0]
        assert len(losses) >= 1
        assert losses["optimised_tpa"].max() < 1.0, (
            "maximising value should leave every loss-making exchange at zero"
        )


def test_optimiser_on_nothing_returns_the_frame_unchanged():
    empty = engine._empty_matches()
    result, report = engine.optimise_network(empty)
    assert result.empty and report["solver"]


# ----------------------------------------------------------------------
# Circularity and impact
# ----------------------------------------------------------------------

def test_circularity_is_a_share_of_what_is_actually_produced(facilities, matches):
    stats = engine.circularity(matches, facilities)
    offered = facilities[(facilities["output_material"].astype(str).str.strip() != "")
                         & (facilities["output_tpa"] > 0)]
    assert stats["total_byproduct_t"] == pytest.approx(float(offered["output_tpa"].sum()))
    assert 0.0 <= stats["circularity_pct"] <= 100.0
    assert stats["placed_t"] <= stats["total_byproduct_t"] + 1e-6
    assert stats["placed_t"] + stats["unplaced_t"] == pytest.approx(stats["total_byproduct_t"])
    assert stats["landfill_diverted_t"] == pytest.approx(stats["placed_t"])
    assert stats["virgin_avoided_t"] > 0
    assert stats["co2_avoided_t"] > 0


def test_circularity_can_be_read_off_the_optimised_plan(facilities, matches):
    optimised, report = engine.optimise_network(matches)
    stats = engine.circularity(optimised, facilities, tonnes_column="optimised_tpa")
    assert stats["basis"] == "optimised_tpa"
    assert 0.0 <= stats["circularity_pct"] <= 100.0
    if report["solver"].startswith("linear"):
        assert stats["net_value"] >= engine.circularity(matches, facilities)["net_value"] - 1e-3


def test_circularity_of_an_empty_network_is_zero(facilities):
    stats = engine.circularity(engine._empty_matches(), facilities)
    assert stats["circularity_pct"] == 0.0
    assert stats["placed_t"] == 0.0
    assert stats["unplaced_t"] == stats["total_byproduct_t"]


def test_boundary_follows_the_survey_of_india_convention():
    """The external boundary must show India's claimed extent, not the ceasefire line.

    A map of India that stops at the Line of Control is wrong for this audience and
    unlawful to publish in India. Jammu and Kashmir must therefore include the areas
    India claims but does not administer, and Ladakh must include Aksai Chin.
    """
    import json
    with open("data/india_states.geojson", encoding="utf-8") as fh:
        geo = json.load(fh)
    by_state = {f["properties"]["state"]: f for f in geo["features"]}

    assert "Jammu and Kashmir" in by_state
    assert "Ladakh" in by_state

    def extent(name):
        points = [p for poly in by_state[name]["geometry"]["coordinates"]
                  for ring in poly for p in ring]
        return (min(p[0] for p in points), max(p[0] for p in points),
                min(p[1] for p in points), max(p[1] for p in points))

    jk_lon_min, _, _, jk_lat_max = extent("Jammu and Kashmir")
    _, ladakh_lon_max, _, _ = extent("Ladakh")

    # Gilgit-Baltistan carries the northern tip past 36.5 N; an LoC-clipped file
    # stops near 35.5 N.
    assert jk_lat_max > 36.5, f"northern extent only reaches {jk_lat_max}"
    # Azad Kashmir carries the western edge past 74 E.
    assert jk_lon_min < 74.0, f"western extent only reaches {jk_lon_min}"
    # Aksai Chin carries Ladakh's eastern edge past 79 E.
    assert ladakh_lon_max > 79.0, f"eastern extent only reaches {ladakh_lon_max}"


def test_map_frame_contains_the_whole_boundary():
    """INDIA_BOUNDS must not clip the corrected northern boundary."""
    import json
    with open("data/india_states.geojson", encoding="utf-8") as fh:
        geo = json.load(fh)
    points = [p for f in geo["features"] for poly in f["geometry"]["coordinates"]
              for ring in poly for p in ring]
    bounds = engine.INDIA_BOUNDS
    assert max(p[1] for p in points) <= bounds["lat_max"]
    assert min(p[1] for p in points) >= bounds["lat_min"]
    assert max(p[0] for p in points) <= bounds["lon_max"]
    assert min(p[0] for p in points) >= bounds["lon_min"]


def test_interface_strings_cover_both_languages():
    import i18n
    assert set(i18n.LANGUAGES) == {"en", "hi"}
    for key, entry in i18n.STRINGS.items():
        assert "en" in entry, f"{key} has no English string"
        assert "hi" in entry, f"{key} has no Hindi string"
        assert entry["en"].strip() or key == "hindi_note"
    # an unknown key falls back to itself rather than raising
    assert i18n.t("no_such_key", "hi") == "no_such_key"
    assert i18n.t("portal", "en") != i18n.t("portal", "hi")


# ----------------------------------------------------------------------
# Spatial index and scale
# ----------------------------------------------------------------------

def test_the_spatial_index_finds_exactly_what_brute_force_finds(facilities):
    """The index must change which pairs are tested, never which pairs match."""
    indexed = engine.find_matches(facilities)
    brute = engine.find_matches_bruteforce(facilities)
    assert indexed.equals(brute)


def test_the_index_is_equivalent_on_a_scattered_registry(facilities):
    """A national spread is the hard case: cells are sparse and far apart."""
    import random
    random.seed(3)
    rows = []
    for i in range(200):
        row = dict(facilities.iloc[i % len(facilities)])
        row["name"] = f'{row["name"]} #{i}'
        row["lat"] = random.uniform(8.5, 34.0)
        row["lon"] = random.uniform(69.5, 95.0)
        rows.append(row)
    scattered = pd.DataFrame(rows)[engine.REQUIRED_COLUMNS]
    assert engine.find_matches(scattered).equals(
        engine.find_matches_bruteforce(scattered))


def test_cell_box_always_covers_the_true_radius():
    """Under-covering would silently drop real matches, so it must over-cover."""
    for lat, lon in [(8.5, 70.0), (22.0, 79.0), (34.0, 95.0)]:
        for km in (50.0, 400.0, 1200.0):
            cells = set(engine._cells_within(lat, lon, km))
            # every point at that distance, sampled around the compass, must
            # fall in a cell the box includes
            for bearing in range(0, 360, 15):
                import math
                rad = math.radians(bearing)
                dlat = (km / engine.KM_PER_DEGREE_LAT) * math.cos(rad)
                dlon = (km / (engine.KM_PER_DEGREE_LAT
                              * max(0.2, math.cos(math.radians(lat))))) * math.sin(rad)
                assert engine._cell(lat + dlat, lon + dlon) in cells, \
                    f"missed a cell at {lat},{lon} {km}km bearing {bearing}"


def test_the_sample_registry_is_substantial(facilities):
    assert len(facilities) >= 200, "the registry should cover real national scale"
    assert facilities["state"].nunique() >= 18
    assert facilities["sector"].nunique() >= 25
    offering = ((facilities["output_material"].astype(str).str.strip() != "")
                & (facilities["output_tpa"] > 0)).sum()
    assert offering >= 100


def test_coordinates_are_all_inside_india(facilities):
    bounds = engine.INDIA_BOUNDS
    assert facilities["lat"].between(bounds["lat_min"], bounds["lat_max"]).all()
    assert facilities["lon"].between(bounds["lon_min"], bounds["lon_max"]).all()


# ----------------------------------------------------------------------
# Coverage reporting
# ----------------------------------------------------------------------

def test_coverage_separates_loaded_from_addressable(facilities):
    import reach
    import materials as materials_module
    import specs as specs_module
    report = reach.summary(facilities, kb, specs_module, materials_module)
    assert report["loaded"] == len(facilities)
    assert report["addressable_count"] > report["loaded"], (
        "addressable is the size of the problem, not the size of the demo"
    )
    assert report["addressable_source"].strip()


def test_every_addressable_figure_carries_a_source_and_is_marked_unverified():
    """No headline number may appear without somewhere to check it."""
    import reach
    assert reach.ADDRESSABLE
    for key, entry in reach.ADDRESSABLE.items():
        assert entry["count"] > 0, key
        assert entry["source"].strip(), key
        assert entry["period"].strip(), key
        assert entry["caveat"].strip(), key
        assert entry["verified"] is False, (
            f"{key} claims to be verified; nothing here was fetched live"
        )


def test_indian_number_formatting():
    import reach
    assert reach.format_count(63_000_000) == "6.30 crore"
    assert reach.format_count(250_000) == "2.50 lakh"
    assert reach.format_count(80_000) == "80,000"


def test_benchmark_measures_rather_than_asserts(facilities):
    import reach
    result = reach.benchmark(facilities, size=150, seed=1)
    assert result["ran"]
    assert result["facilities"] == 150
    assert result["seconds"] > 0
    assert result["facilities_per_second"] > 0
    # deterministic for a fixed seed: the same synthetic registry each time
    again = reach.benchmark(facilities, size=150, seed=1)
    assert again["matches"] == result["matches"]


def test_benchmark_on_an_empty_registry_is_safe():
    import reach
    assert reach.benchmark(pd.DataFrame(), 100)["ran"] is False
