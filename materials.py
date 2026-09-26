"""Material property vectors.

The rest of this application matches material *names*. This module models a
by-product as what it is actually made of, so it can be tested against a written
specification rather than against a label.

Units
-----
Oxides, loss on ignition, moisture, chloride, free lime, sulphide sulphur, glass
content and gypsum purity are all percentages by mass.
`fineness_m2kg`  specific surface, m2/kg, Blaine unless the note says otherwise
`retained_45um`  residue on the 45 micron sieve, % by mass (wet sieving)
`alkali_na2oeq`  total alkali as Na2O equivalent, % (Na2O + 0.658 x K2O)
`calorific_mjkg` net calorific value, MJ/kg, as received

Provenance
----------
These are REPRESENTATIVE compositions for a stream of that type from a plant of
that type - the middle of the published range, not an assay of anybody's actual
waste. They are here so the grading logic can be demonstrated and argued with.
A real trade needs a laboratory certificate for the actual consignment, and the
interface says so wherever a grade is shown.

A property that is genuinely not measured for a stream is left out rather than
guessed. Conformance grading treats a missing property as "cannot be assessed",
never as a pass.
"""

from __future__ import annotations

# Every property the specification library can refer to.
PROPERTY_KEYS = (
    "sio2", "al2o3", "fe2o3", "cao", "mgo", "so3", "loi", "moisture",
    "fineness_m2kg", "alkali_na2oeq", "retained_45um", "cl", "calorific_mjkg",
    "glass_content", "free_lime", "sulphide_s", "purity_caso4",
)

PROPERTY_LABELS = {
    "sio2": "SiO2", "al2o3": "Al2O3", "fe2o3": "Fe2O3", "cao": "CaO",
    "mgo": "MgO", "so3": "SO3", "loi": "Loss on ignition",
    "moisture": "Moisture", "fineness_m2kg": "Fineness (Blaine)",
    "alkali_na2oeq": "Alkali as Na2O eq", "retained_45um": "Retained on 45 um",
    "cl": "Chloride", "calorific_mjkg": "Net calorific value",
    "glass_content": "Glass content", "free_lime": "Free lime",
    "sulphide_s": "Sulphide sulphur", "purity_caso4": "CaSO4.2H2O purity",
}

PROPERTY_UNITS = {
    "fineness_m2kg": "m2/kg", "calorific_mjkg": "MJ/kg",
}


def unit_for(prop: str) -> str:
    return PROPERTY_UNITS.get(prop, "%")


MATERIAL_PROPERTIES = {
    # ------------------------------------------------------------------
    # Coal ash - three plants, deliberately different, because "fly ash"
    # is not one material and that is the point of this whole module.
    # ------------------------------------------------------------------
    "Fly ash (Vindhyachal STPS)": dict(
        sio2=60.5, al2o3=27.5, fe2o3=5.2, cao=1.6, mgo=0.8, so3=0.3,
        loi=1.4, moisture=0.5, fineness_m2kg=395, alkali_na2oeq=0.7,
        retained_45um=18.0, cl=0.015, calorific_mjkg=0.3,
        sector="thermal power", annual_tpa=4_100_000, disposal_inr_t=350,
        note="Dry ESP collection from a high-efficiency unit. Low unburnt carbon "
             "and high fineness - the best of the three ash streams here.",
    ),
    "Fly ash (Korba STPS)": dict(
        sio2=58.0, al2o3=26.0, fe2o3=6.5, cao=2.1, mgo=1.0, so3=0.4,
        loi=2.2, moisture=0.8, fineness_m2kg=340, alkali_na2oeq=0.9,
        retained_45um=28.0, cl=0.02, calorific_mjkg=0.5,
        sector="thermal power", annual_tpa=3_200_000, disposal_inr_t=350,
        note="Typical dry ESP ash. Clears IS 3812 Part 1 but with little "
             "headroom on fineness, so a bad day at the precipitator matters.",
    ),
    "Fly ash (Talcher TPS)": dict(
        sio2=54.0, al2o3=23.0, fe2o3=8.1, cao=3.2, mgo=1.4, so3=0.7,
        loi=7.8, moisture=1.6, fineness_m2kg=265, alkali_na2oeq=1.2,
        retained_45um=41.0, cl=0.03, calorific_mjkg=1.8,
        sector="thermal power", annual_tpa=1_880_000, disposal_inr_t=350,
        note="Older unit burning higher-ash coal. High unburnt carbon and coarse "
             "- fails structural concrete grade on three counts at once.",
    ),
    "Bottom ash (Singrauli STPS)": dict(
        sio2=55.0, al2o3=24.0, fe2o3=7.5, cao=3.0, mgo=1.2, so3=0.5,
        loi=5.5, moisture=14.0, fineness_m2kg=110, alkali_na2oeq=1.1,
        retained_45um=62.0, cl=0.03, calorific_mjkg=1.2,
        sector="thermal power", annual_tpa=470_000, disposal_inr_t=300,
        note="Coarse, porous and wet from the bottom ash hopper. Never a "
             "pozzolan; its uses are all aggregate or fill.",
    ),
    # ------------------------------------------------------------------
    # Iron and steel
    # ------------------------------------------------------------------
    "GGBS (Bhilai Steel Plant)": dict(
        sio2=34.0, al2o3=18.5, fe2o3=1.1, cao=38.5, mgo=8.2, so3=0.2,
        loi=1.2, moisture=0.6, fineness_m2kg=410, alkali_na2oeq=0.6,
        retained_45um=6.0, cl=0.02, glass_content=92.0, sulphide_s=0.8,
        sector="steel", annual_tpa=2_400_000, disposal_inr_t=250,
        note="Water-quenched and ground. Glass content is what makes it "
             "hydraulic - air-cooled slag of the same chemistry is inert.",
    ),
    "Steel slag (Rourkela Steel Plant)": dict(
        sio2=14.0, al2o3=3.0, fe2o3=25.0, cao=42.0, mgo=7.0, so3=0.3,
        loi=1.0, moisture=3.5, fineness_m2kg=180, alkali_na2oeq=0.4,
        retained_45um=45.0, cl=0.02, glass_content=15.0, free_lime=4.5,
        sector="steel", annual_tpa=690_000, disposal_inr_t=250,
        note="LD converter slag. Free lime makes it expansive until weathered, "
             "and the low glass content rules out cementitious use.",
    ),
    "Mill scale (Durgapur Steel Plant)": dict(
        sio2=1.0, al2o3=0.3, fe2o3=95.0, cao=0.5, mgo=0.2, so3=0.05,
        loi=0.5, moisture=2.5, cl=0.01, alkali_na2oeq=0.1,
        sector="steel", annual_tpa=52_000, disposal_inr_t=200,
        note="Rolling mill scale, richer in iron than most Indian ore fines. "
             "Carries lubricant oil that must be removed before sintering.",
    ),
    # ------------------------------------------------------------------
    # Agricultural and biomass ash
    # ------------------------------------------------------------------
    "Rice husk ash (Raipur cluster)": dict(
        sio2=88.0, al2o3=0.6, fe2o3=0.5, cao=1.1, mgo=0.5, so3=0.3,
        loi=6.5, moisture=1.2, fineness_m2kg=1500, alkali_na2oeq=1.4,
        retained_45um=12.0, cl=0.05, calorific_mjkg=0.8,
        sector="rice mill", annual_tpa=24_000, disposal_inr_t=400,
        note="Controlled-combustion ash, so the silica is amorphous and "
             "reactive. Fineness is Blaine on ground ash; RHA burnt above about "
             "700 C crystallises and is far less reactive at the same assay.",
    ),
    "Bagasse ash (Kolhapur sugar complex)": dict(
        sio2=64.0, al2o3=5.5, fe2o3=3.5, cao=6.5, mgo=2.5, so3=1.2,
        loi=12.5, moisture=2.5, fineness_m2kg=280, alkali_na2oeq=3.2,
        retained_45um=38.0, cl=0.08, calorific_mjkg=1.5,
        sector="sugar", annual_tpa=18_000, disposal_inr_t=350,
        note="Boiler ash with entrained sand and a lot of unburnt carbon. The "
             "high alkali is the real obstacle for concrete use.",
    ),
    # ------------------------------------------------------------------
    # Desulphurisation, alumina and lime residues
    # ------------------------------------------------------------------
    "FGD gypsum (Mundra TPS)": dict(
        sio2=1.2, al2o3=0.5, fe2o3=0.3, cao=31.5, mgo=0.4, so3=44.0,
        loi=19.5, moisture=8.5, cl=0.008, alkali_na2oeq=0.2,
        purity_caso4=94.0,
        sector="thermal power", annual_tpa=255_000, disposal_inr_t=400,
        note="Wet limestone scrubber gypsum. Loss on ignition is high because "
             "it is water of crystallisation, not carbon - a reminder that an "
             "LOI limit means different things for different streams.",
    ),
    "Red mud (Lanjigarh alumina refinery)": dict(
        sio2=12.0, al2o3=17.0, fe2o3=45.0, cao=4.5, mgo=0.6, so3=0.5,
        loi=8.5, moisture=22.0, fineness_m2kg=320, alkali_na2oeq=6.5,
        retained_45um=22.0, cl=0.05,
        sector="aluminium", annual_tpa=1_450_000, disposal_inr_t=900,
        note="Bayer process residue at pH 10-12. The sodium is the whole "
             "problem: it fails every alkali limit in the library by a wide "
             "margin, which is why so little of it is used.",
    ),
    "Lime sludge (Rayagada paper mill)": dict(
        sio2=3.5, al2o3=1.2, fe2o3=0.8, cao=48.0, mgo=1.5, so3=0.3,
        loi=36.0, moisture=32.0, fineness_m2kg=250, alkali_na2oeq=0.5,
        retained_45um=30.0, cl=0.04,
        sector="paper", annual_tpa=36_000, disposal_inr_t=600,
        note="Recausticising residue, essentially reprecipitated calcium "
             "carbonate. Already calcined once, so it saves kiln CO2 - but the "
             "loss on ignition is the CO2 it will give back.",
    ),
    "Silica fume (Bhadravati ferroalloy plant)": dict(
        sio2=93.0, al2o3=0.7, fe2o3=0.6, cao=0.5, mgo=0.4, so3=0.3,
        loi=2.4, moisture=1.1, fineness_m2kg=20000, alkali_na2oeq=0.8,
        retained_45um=4.0, cl=0.02,
        sector="metal recovery", annual_tpa=9_000, disposal_inr_t=500,
        note="Condensed silica fume from a ferrosilicon furnace. Fineness here "
             "is BET surface area, not Blaine - the two are not comparable, and "
             "only the silica fume specification should be read against it.",
    ),
    # ------------------------------------------------------------------
    # Derived and mixed streams
    # ------------------------------------------------------------------
    "RDF (Hyderabad MSW plant)": dict(
        sio2=5.0, al2o3=2.0, fe2o3=1.0, cao=3.0, mgo=0.6, so3=0.4,
        loi=72.0, moisture=18.0, cl=0.85, alkali_na2oeq=0.9,
        calorific_mjkg=16.5,
        sector="waste management", annual_tpa=205_000, disposal_inr_t=1400,
        note="Refuse-derived fuel from segregated municipal waste. Chlorine "
             "from PVC is what decides whether a kiln will take it, not the "
             "calorific value.",
    ),
}


def materials() -> list:
    """Every material with a property vector, in a stable order."""
    return list(MATERIAL_PROPERTIES)


def properties_of(name: str) -> dict | None:
    """The property vector for a material, or None if it is not modelled."""
    key = str(name).strip().lower()
    for candidate, values in MATERIAL_PROPERTIES.items():
        if candidate.lower() == key:
            return values
    return None


def measured_properties(name: str) -> dict:
    """Only the numeric properties, dropping the metadata fields."""
    values = properties_of(name) or {}
    return {k: v for k, v in values.items() if k in PROPERTY_KEYS}
