"""Carbon intensity and the Carbon Credit Trading Scheme.

India's CCTS sets **intensity-based** targets: tonnes of CO2 equivalent per
tonne of product, not an absolute cap. A facility that beats its target earns
tradeable carbon credit certificates; one that misses must buy certificates to
cover the shortfall, and the penalty for non-compliance is set at twice the
market price of a certificate. The obligated sectors include cement, iron and
steel, aluminium, pulp and paper, petroleum refining, textiles and fertiliser.

Why this module exists: when a cement plant raises its supplementary
cementitious material share, it lowers the clinker factor, which directly lowers
the emissions intensity it is legally measured on. That turns industrial
symbiosis from a cost saving into a compliance lever, which is a different and
much stronger argument.

What is assumption and what is not
----------------------------------
The scheme, its intensity basis, the sectors covered and the doubled penalty are
features of the scheme. The **certificate price is not** - Indian certificate
trading has no settled price yet, so every rupee figure here moves with a price
the user sets, and the interface presents it as an assumption rather than a
forecast. The emission factors below are published sector averages, not any
specific plant's verified figure; a real filing uses metered data.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Emission factors. Indian sector averages, stated as such.
# ----------------------------------------------------------------------
CLINKER_EMISSION_FACTOR = 0.86   # tCO2 per tonne of clinker: roughly 0.53 from
                                 # limestone calcination, which no fuel switch
                                 # can remove, plus about 0.33 from kiln fuel.
CEMENT_OTHER_EMISSIONS = 0.06    # tCO2 per tonne of cement for grinding,
                                 # conveying and packing electricity.
GYPSUM_SHARE = 0.05              # mass fraction of set retarder in the cement,
                                 # which is not available for substitution.

DEFAULT_CERTIFICATE_PRICE = 2000.0   # INR per tCO2e. AN ASSUMPTION - see above.
PENALTY_MULTIPLE = 2.0               # non-compliance costs twice the market price

SCHEME_NOTES = (
    "CCTS targets are intensity-based (tCO2e per tonne of product). Facilities "
    "beating their target earn tradeable certificates; those missing it must buy "
    "certificates or pay a penalty set at twice the certificate price. First "
    "compliance filings are due 31 July 2026, with trading on the power exchanges "
    "expected from around October 2026."
)


def cement_intensity(scm_share: float) -> float:
    """Gross emissions intensity of cement, tCO2e per tonne, at a given SCM share.

    clinker factor = 1 - SCM share - gypsum share, so every tonne of fly ash or
    slag that goes in displaces a tonne of clinker and the calcination emissions
    that come with it.
    """
    scm_share = max(0.0, min(1.0 - GYPSUM_SHARE, float(scm_share)))
    clinker_factor = 1.0 - GYPSUM_SHARE - scm_share
    return clinker_factor * CLINKER_EMISSION_FACTOR + CEMENT_OTHER_EMISSIONS


# Receiving plants, with the intensity target each is measured against.
PLANTS = {
    "Chandrapur Cement Works": dict(
        sector="cement", annual_production_t=2_750_000,
        baseline_scm_share=0.22, target_gei=0.62, state="Maharashtra",
        note="Ordinary Portland cement with a modest fly ash share. The target "
             "shown is illustrative of the trajectory the scheme implies, not a "
             "figure notified for this plant.",
    ),
    "Satna Cement Works": dict(
        sector="cement", annual_production_t=3_400_000,
        baseline_scm_share=0.18, target_gei=0.62, state="Madhya Pradesh",
        note="Lower SCM share than its peers, so it has the most to gain and the "
             "furthest to travel.",
    ),
    "Bargarh Cement Works": dict(
        sector="cement", annual_production_t=1_850_000,
        baseline_scm_share=0.30, target_gei=0.62, state="Odisha",
        note="Already blending heavily; further substitution earns certificates "
             "rather than merely avoiding a shortfall.",
    ),
    "Wadi Cement Plant": dict(
        sector="cement", annual_production_t=3_050_000,
        baseline_scm_share=0.25, target_gei=0.62, state="Karnataka",
        note="Large kiln with a typical Indian PPC blend.",
    ),
}


def plants() -> list:
    return list(PLANTS)


def plant(name: str) -> dict | None:
    key = str(name).strip().lower()
    for candidate, entry in PLANTS.items():
        if candidate.lower() == key:
            return entry
    return None


def assess(plant_name: str, scm_share: float,
           certificate_price: float = DEFAULT_CERTIFICATE_PRICE) -> dict:
    """CCTS position for a plant at a given SCM share.

    Positive `certificates` means the plant beats its target and earns tradeable
    certificates. Negative means a shortfall it must cover, and the exposure is
    reported at the penalty rate as well as at the market rate, because those are
    two different numbers a plant would put in front of a board.
    """
    entry = plant(plant_name)
    if entry is None:
        return {"plant": plant_name, "found": False}

    production = float(entry["annual_production_t"])
    target = float(entry["target_gei"])
    baseline_gei = cement_intensity(entry["baseline_scm_share"])
    actual_gei = cement_intensity(scm_share)

    certificates = (target - actual_gei) * production
    baseline_certificates = (target - baseline_gei) * production

    return {
        "plant": plant_name,
        "found": True,
        "sector": entry["sector"],
        "annual_production_t": production,
        "scm_share": float(scm_share),
        "baseline_scm_share": float(entry["baseline_scm_share"]),
        "target_gei": target,
        "baseline_gei": baseline_gei,
        "actual_gei": actual_gei,
        "intensity_reduction": baseline_gei - actual_gei,
        "annual_co2_baseline_t": baseline_gei * production,
        "annual_co2_actual_t": actual_gei * production,
        "co2_avoided_t": (baseline_gei - actual_gei) * production,
        "certificates": certificates,
        "baseline_certificates": baseline_certificates,
        "certificates_gained": certificates - baseline_certificates,
        "compliant": certificates >= 0,
        "certificate_price": float(certificate_price),
        "position_inr": certificates * float(certificate_price),
        "exposure_at_penalty_inr": (min(0.0, certificates) * float(certificate_price)
                                    * PENALTY_MULTIPLE),
        "value_of_change_inr": (certificates - baseline_certificates)
                               * float(certificate_price),
        "note": entry.get("note", ""),
    }


def compare_options(plant_name: str, options: list,
                    certificate_price: float = DEFAULT_CERTIFICATE_PRICE) -> list:
    """One row per sourcing option for a receiving plant.

    Each option is a dict with `label`, `scm_share`, `cost_inr_t` (delivered cost
    of the substitute per tonne of cement produced) and `quality_margin`, the
    headroom of the binding property against the specification, which is how much
    room the plant has before a bad consignment puts it outside the standard.
    """
    rows = []
    for option in options:
        result = assess(plant_name, option.get("scm_share", 0.0), certificate_price)
        if not result.get("found"):
            continue
        rows.append({
            "option": option.get("label", ""),
            "scm_share": result["scm_share"],
            "cost_inr_t": option.get("cost_inr_t"),
            "quality_margin": option.get("quality_margin"),
            "meets_spec": option.get("meets_spec"),
            "gei": result["actual_gei"],
            "co2_t_yr": result["annual_co2_actual_t"],
            "co2_avoided_t_yr": result["co2_avoided_t"],
            "certificates": result["certificates"],
            "position_inr": result["position_inr"],
            "compliant": result["compliant"],
        })
    return rows
