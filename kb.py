"""Substitution knowledge base for Symbiosis Finder.

Each entry records one documented industrial substitution: a by-product, the
application a receiver puts it to, and the virgin material it displaces there.

The two fields that stop this being naive keyword matching are `max_share`
(how much of the receiver's input the by-product may actually cover) and
`max_km` (past which the exchange stops making commercial sense). A bulky,
low-value stream such as bagasse cannot pay for its own freight beyond about
120 km; spent refinery catalyst carries enough recoverable metal to ship
across the country.

Field reference
---------------
material            by-product offered by the supplier
application         what the receiver uses it for
accepting_sectors   plant types that can take it (matched against the registry)
replaces            virgin material displaced at the receiver
substitution_ratio  tonnes of virgin material displaced per tonne used
max_share           highest fraction of the receiver's input it can cover
processing          none / simple / moderate / complex
max_km              beyond this distance the exchange stops making sense
co2_saved_t         tonnes CO2 avoided per tonne exchanged
virgin_value        approximate value of the displaced material, INR/tonne
hazard              none / regulated
note                the practical catch, shown to the user
disposal_cost       optional INR/tonne disposal cost avoided; falls back to
                    engine.DISPOSAL_COST_DEFAULT when absent
transport_mode      "road" (default) or "pipeline" for heat and gas streams
basis               "mass" (default) or "energy" where the registry tonnage is
                    a coal-equivalent stand-in rather than a physical tonnage

Values are representative figures assembled from Indian standards, CPCB
guidance and published plant practice. They are defensible orders of
magnitude for screening, not audited contract terms.
"""

SUBSTITUTIONS = [
    # ------------------------------------------------------------------
    # Coal ash streams
    # ------------------------------------------------------------------
    {
        "material": "fly ash",
        "application": "Portland pozzolana cement blending",
        "accepting_sectors": ["cement"],
        "replaces": "OPC clinker",
        "substitution_ratio": 1.0,
        "max_share": 0.35,
        "processing": "none",
        "max_km": 400,
        "co2_saved_t": 0.85,
        "virgin_value": 4200,
        "hazard": "none",
        "note": "IS 1489 Part 1 permits 15-35% fly ash in PPC and IS 3812 Part 1 sets the "
                "fineness and loss-on-ignition limits; 35% is the ceiling, not a target. "
                "Dry collection from ESP hoppers is required - pond ash will not qualify.",
    },
    {
        "material": "fly ash",
        "application": "autoclaved aerated concrete and fly ash bricks",
        "accepting_sectors": ["construction materials"],
        "replaces": "clay and river sand",
        "substitution_ratio": 1.0,
        "max_share": 0.60,
        "processing": "simple",
        "max_km": 250,
        "co2_saved_t": 0.20,
        "virgin_value": 900,
        "hazard": "none",
        "note": "IS 12894 fly ash-lime brick practice; ash is 55-65% of the mix. Displaces "
                "topsoil excavation rather than clinker, so the CO2 credit is modest.",
    },
    {
        "material": "fly ash",
        "application": "road embankment and structural fill",
        "accepting_sectors": ["road project", "construction materials"],
        "replaces": "borrow earth",
        "substitution_ratio": 1.0,
        "max_share": 0.80,
        "processing": "none",
        "max_km": 120,
        "co2_saved_t": 0.05,
        "virgin_value": 400,
        "hazard": "none",
        "note": "IRC SP:58 covers ash embankments and the MoEFCC fly ash notification makes "
                "ash mandatory within 300 km of a plant. The material is nearly free, so "
                "freight alone decides viability - past ~120 km borrow earth wins.",
    },
    {
        "material": "bottom ash",
        "application": "fine aggregate in concrete blocks and paver units",
        "accepting_sectors": ["construction materials"],
        "replaces": "river sand",
        "substitution_ratio": 1.0,
        "max_share": 0.30,
        "processing": "simple",
        "max_km": 150,
        "co2_saved_t": 0.06,
        "virgin_value": 700,
        "hazard": "none",
        "note": "Coarser and more porous than fly ash, so it needs screening and a higher "
                "water allowance. Useful mainly where river sand is scarce or levy-heavy.",
    },
    # ------------------------------------------------------------------
    # Flue gas desulphurisation gypsum
    # ------------------------------------------------------------------
    {
        "material": "FGD gypsum",
        "application": "cement set retarder",
        "accepting_sectors": ["cement"],
        "replaces": "mineral gypsum",
        "substitution_ratio": 1.0,
        "max_share": 0.05,
        "processing": "simple",
        "max_km": 500,
        "co2_saved_t": 0.04,
        "virgin_value": 2600,
        "hazard": "none",
        "note": "Retarder is only 3-5% of cement by mass, so a large kiln still absorbs very "
                "little. India imports most of its mineral gypsum, which is why the value "
                "per tonne supports long hauls. Needs dewatering below ~10% free moisture.",
    },
    {
        "material": "FGD gypsum",
        "application": "gypsum plasterboard and wall putty",
        "accepting_sectors": ["construction materials"],
        "replaces": "mineral gypsum",
        "substitution_ratio": 1.0,
        "max_share": 0.85,
        "processing": "simple",
        "max_km": 600,
        "co2_saved_t": 0.05,
        "virgin_value": 2800,
        "hazard": "none",
        "note": "Board plants can run almost entirely on synthetic gypsum if whiteness and "
                "chloride limits are met. Consistency matters more than volume here.",
    },
    {
        "material": "FGD gypsum",
        "application": "sodic soil reclamation",
        "accepting_sectors": ["agriculture"],
        "replaces": "mined agricultural gypsum",
        "substitution_ratio": 1.0,
        "max_share": 1.00,
        "processing": "none",
        "max_km": 200,
        "co2_saved_t": 0.02,
        "virgin_value": 1800,
        "hazard": "none",
        "note": "Standard reclamation practice on sodic soils in Uttar Pradesh and Haryana. "
                "Demand is seasonal and dispersed, so aggregation is the real obstacle.",
    },
    # ------------------------------------------------------------------
    # Iron and steel
    # ------------------------------------------------------------------
    {
        "material": "blast furnace slag",
        "application": "ground granulated slag for slag cement",
        "accepting_sectors": ["cement"],
        "replaces": "OPC clinker",
        "substitution_ratio": 1.0,
        "max_share": 0.70,
        "processing": "moderate",
        "max_km": 700,
        "co2_saved_t": 0.80,
        "virgin_value": 4200,
        "hazard": "none",
        "note": "IS 455 allows 25-70% granulated slag in Portland slag cement, so this is the "
                "single largest clinker substitution available in India. Requires rapid water "
                "quenching at the furnace and grinding to ~400 m2/kg, hence moderate processing.",
    },
    {
        "material": "blast furnace slag",
        "application": "road sub-base and unbound aggregate",
        "accepting_sectors": ["road project", "construction materials"],
        "replaces": "quarried stone aggregate",
        "substitution_ratio": 1.0,
        "max_share": 0.50,
        "processing": "simple",
        "max_km": 150,
        "co2_saved_t": 0.03,
        "virgin_value": 700,
        "hazard": "none",
        "note": "Air-cooled slag only. Competes directly with local quarry stone, so this use "
                "is a fallback where no grinding unit is within reach.",
    },
    {
        "material": "steel slag",
        "application": "road base aggregate",
        "accepting_sectors": ["road project", "construction materials"],
        "replaces": "quarried stone aggregate",
        "substitution_ratio": 1.0,
        "max_share": 0.40,
        "processing": "moderate",
        "max_km": 150,
        "co2_saved_t": 0.04,
        "virgin_value": 750,
        "hazard": "none",
        "note": "Free lime makes fresh LD slag expansive; it must be weathered or steam-aged "
                "for several months before use under a pavement. Skipping that step is the "
                "usual cause of failure.",
    },
    {
        "material": "steel slag",
        "application": "sinter plant and BOF flux",
        "accepting_sectors": ["steel"],
        "replaces": "limestone and dolomite",
        "substitution_ratio": 1.0,
        "max_share": 0.10,
        "processing": "simple",
        "max_km": 250,
        "co2_saved_t": 0.25,
        "virgin_value": 1600,
        "hazard": "none",
        "note": "Returning slag as flux recovers its lime and iron and avoids limestone "
                "calcination, which is where the CO2 credit comes from. Phosphorus build-up "
                "limits the recycle fraction.",
    },
    {
        "material": "mill scale",
        "application": "sinter and pellet feed iron source",
        "accepting_sectors": ["steel"],
        "replaces": "iron ore fines",
        "substitution_ratio": 1.0,
        "max_share": 0.08,
        "processing": "simple",
        "max_km": 600,
        "co2_saved_t": 0.15,
        "virgin_value": 5200,
        "hazard": "none",
        "note": "Around 70% Fe, richer than most Indian ore fines. Rolling mill scale carries "
                "lubricant oil and needs de-oiling below ~1% before it can enter a sinter bed.",
    },
    {
        "material": "mill scale",
        "application": "cement kiln iron corrective",
        "accepting_sectors": ["cement"],
        "replaces": "laterite and iron ore",
        "substitution_ratio": 1.0,
        "max_share": 0.03,
        "processing": "none",
        "max_km": 500,
        "co2_saved_t": 0.10,
        "virgin_value": 3800,
        "hazard": "none",
        "note": "Raw meal needs only 1-3% iron corrective, so even a large kiln takes a small "
                "tonnage. Attractive because it needs no preparation at all.",
    },
    {
        "material": "ferrous scrap",
        "application": "electric arc and induction furnace charge",
        "accepting_sectors": ["steel", "foundry"],
        "replaces": "sponge iron and pig iron",
        "substitution_ratio": 1.0,
        "max_share": 0.85,
        "processing": "simple",
        "max_km": 700,
        "co2_saved_t": 1.40,
        "virgin_value": 38000,
        "hazard": "none",
        "note": "Scrap-based steel avoids ironmaking altogether, which is the largest per-tonne "
                "CO2 saving in this table. Tramp elements (copper, tin) cap the share for "
                "flat products; long products tolerate more.",
    },
    {
        "material": "coke oven gas",
        "application": "reheating furnace and boiler fuel gas",
        "accepting_sectors": ["steel", "cement", "chemicals"],
        "replaces": "natural gas",
        "substitution_ratio": 0.80,
        "max_share": 0.35,
        "processing": "moderate",
        "max_km": 12,
        "co2_saved_t": 2.20,
        "virgin_value": 28000,
        "hazard": "none",
        "note": "Moves by pipeline, not truck - the 12 km limit is a physical one. Registry "
                "tonnage is the gas mass; at roughly 38 GJ/t it displaces about 0.8 t of "
                "natural gas per tonne. Needs tar and H2S cleaning before use.",
        "transport_mode": "pipeline",
        "basis": "energy",
    },
    {
        "material": "waste heat",
        "application": "waste heat recovery steam and process heating",
        "accepting_sectors": ["steel", "cement", "chemicals", "paper", "textile"],
        "replaces": "thermal coal",
        "substitution_ratio": 1.0,
        "max_share": 0.25,
        "processing": "moderate",
        "max_km": 8,
        "co2_saved_t": 2.00,
        "virgin_value": 5500,
        "hazard": "none",
        "note": "Registry tonnage is tonnes of coal equivalent, not a physical mass - heat has "
                "no tonnage. Transfer is by steam line, so 8 km is generous already. Requires "
                "a recovery boiler and a receiver whose load profile matches the source.",
        "transport_mode": "pipeline",
        "basis": "energy",
    },
    # ------------------------------------------------------------------
    # Sugar and distillery
    # ------------------------------------------------------------------
    {
        "material": "bagasse",
        "application": "pulp furnish for writing and printing paper",
        "accepting_sectors": ["paper"],
        "replaces": "hardwood pulpwood",
        "substitution_ratio": 0.55,
        "max_share": 0.60,
        "processing": "moderate",
        "max_km": 120,
        "co2_saved_t": 0.35,
        "virgin_value": 4500,
        "hazard": "none",
        "note": "Depithing removes about 30% of the mass before pulping, which is why one "
                "tonne of bagasse displaces roughly 0.55 t of pulpwood. Very low bulk density "
                "caps economic haulage near 120 km. Competes with the mill's own boiler.",
    },
    {
        "material": "bagasse",
        "application": "biomass boiler fuel",
        "accepting_sectors": ["paper", "textile", "cement", "chemicals", "distillery"],
        "replaces": "thermal coal",
        "substitution_ratio": 0.45,
        "max_share": 0.30,
        "processing": "simple",
        "max_km": 120,
        "co2_saved_t": 0.85,
        "virgin_value": 2600,
        "hazard": "none",
        "note": "At 8-9 MJ/kg wet against 18-20 MJ/kg for coal, one tonne replaces under half "
                "a tonne of coal. Only available in the crushing season unless the receiver "
                "can store baled fuel, which most cannot.",
    },
    {
        "material": "press mud",
        "application": "bio-compost and organic manure",
        "accepting_sectors": ["agriculture", "sugar"],
        "replaces": "farmyard manure and phosphatic fertiliser",
        "substitution_ratio": 1.0,
        "max_share": 1.00,
        "processing": "simple",
        "max_km": 80,
        "co2_saved_t": 0.25,
        "virgin_value": 1500,
        "hazard": "none",
        "note": "Composted with spent wash in windrows over 8-10 weeks. Wet, heavy and quick "
                "to turn anaerobic, so it travels badly - most goes to farms within the mill's "
                "own cane command area.",
    },
    {
        "material": "press mud",
        "application": "compressed biogas feedstock",
        "accepting_sectors": ["CBG plant", "distillery"],
        "replaces": "cattle dung and napier feedstock",
        "substitution_ratio": 1.0,
        "max_share": 0.50,
        "processing": "moderate",
        "max_km": 100,
        "co2_saved_t": 0.60,
        "virgin_value": 2200,
        "hazard": "none",
        "note": "Backed by the SATAT programme. Digester feed must be blended and pH-corrected; "
                "a plant sized on press mud alone stops for eight months of the year.",
    },
    {
        "material": "molasses",
        "application": "ethanol fermentation feedstock",
        "accepting_sectors": ["distillery"],
        "replaces": "damaged food grain and cane juice",
        "substitution_ratio": 1.0,
        "max_share": 0.80,
        "processing": "none",
        "max_km": 350,
        "co2_saved_t": 0.30,
        "virgin_value": 8500,
        "hazard": "none",
        "note": "The core feedstock of India's ethanol blending programme. Moves in tankers and "
                "stores for months, so distance matters less than for any other biomass here. "
                "State excise permits govern inter-state movement.",
    },
    {
        "material": "molasses",
        "application": "compound cattle feed binder and energy source",
        "accepting_sectors": ["feed", "dairy"],
        "replaces": "cereal energy concentrate",
        "substitution_ratio": 0.60,
        "max_share": 0.10,
        "processing": "none",
        "max_km": 250,
        "co2_saved_t": 0.10,
        "virgin_value": 7000,
        "hazard": "none",
        "note": "Capped near 10% of the ration by palatability and laxative effect. Competes "
                "with distilleries, which usually bid higher.",
    },
    {
        "material": "spent wash",
        "application": "bio-methanation with potassic fertigation",
        "accepting_sectors": ["distillery", "agriculture"],
        "replaces": "potash fertiliser and boiler coal",
        "substitution_ratio": 0.15,
        "max_share": 0.40,
        "processing": "complex",
        "max_km": 25,
        "co2_saved_t": 0.15,
        "virgin_value": 900,
        "hazard": "regulated",
        "note": "CPCB requires zero liquid discharge from molasses distilleries, so spent wash "
                "is a compliance liability, not a tradeable commodity. Biomethanation then "
                "concentration or incineration is mandatory and the residue moves only a few "
                "km. Receiver needs consent to handle it.",
        "disposal_cost": 3200,
    },
    # ------------------------------------------------------------------
    # Agricultural residue and wood
    # ------------------------------------------------------------------
    {
        "material": "rice husk",
        "application": "biomass boiler fuel",
        "accepting_sectors": ["paper", "textile", "cement", "chemicals", "rice mill", "distillery"],
        "replaces": "thermal coal",
        "substitution_ratio": 0.65,
        "max_share": 0.35,
        "processing": "simple",
        "max_km": 150,
        "co2_saved_t": 1.10,
        "virgin_value": 3500,
        "hazard": "none",
        "note": "About 13 MJ/kg against 20 for coal. High silica ash is abrasive and needs a "
                "grate designed for it. Supply is concentrated in the kharif milling months.",
    },
    {
        "material": "rice husk ash",
        "application": "supplementary cementitious material in concrete",
        "accepting_sectors": ["cement", "construction materials"],
        "replaces": "OPC clinker and silica fume",
        "substitution_ratio": 1.0,
        "max_share": 0.10,
        "processing": "moderate",
        "max_km": 400,
        "co2_saved_t": 0.75,
        "virgin_value": 8000,
        "hazard": "none",
        "note": "Only useful if burnt below ~700 C so the silica stays amorphous; most Indian "
                "husk-fired boilers overshoot and produce crystalline ash that does nothing. "
                "Needs grinding and a reactivity test before any kiln will take it.",
    },
    {
        "material": "rice husk ash",
        "application": "ladle covering and insulating powder",
        "accepting_sectors": ["steel", "foundry"],
        "replaces": "proprietary insulating compound",
        "substitution_ratio": 1.0,
        "max_share": 0.60,
        "processing": "simple",
        "max_km": 500,
        "co2_saved_t": 0.20,
        "virgin_value": 6500,
        "hazard": "none",
        "note": "Long-standing practice in Indian steel melting shops; the high silica and low "
                "conductivity that spoil it as a pozzolan are exactly what work here.",
    },
    {
        "material": "sawdust",
        "application": "particle board and MDF furnish",
        "accepting_sectors": ["wood panel"],
        "replaces": "pulpwood chips",
        "substitution_ratio": 0.90,
        "max_share": 0.45,
        "processing": "simple",
        "max_km": 150,
        "co2_saved_t": 0.30,
        "virgin_value": 3200,
        "hazard": "none",
        "note": "Species mix and moisture decide acceptance; treated or painted offcuts are "
                "excluded. Board plants cluster near sawmills for exactly this reason.",
    },
    {
        "material": "sawdust",
        "application": "briquette fuel for process boilers",
        "accepting_sectors": ["textile", "paper", "chemicals", "cement"],
        "replaces": "thermal coal",
        "substitution_ratio": 0.60,
        "max_share": 0.20,
        "processing": "moderate",
        "max_km": 180,
        "co2_saved_t": 1.00,
        "virgin_value": 3000,
        "hazard": "none",
        "note": "Loose sawdust cannot be fired or freighted economically, so briquetting is "
                "unavoidable and costs real money. Densified fuel then travels further than "
                "the raw material would.",
    },
    # ------------------------------------------------------------------
    # Pulp, paper and lime
    # ------------------------------------------------------------------
    {
        "material": "lime sludge",
        "application": "cement raw meal limestone substitute",
        "accepting_sectors": ["cement"],
        "replaces": "quarried limestone",
        "substitution_ratio": 1.0,
        "max_share": 0.10,
        "processing": "simple",
        "max_km": 250,
        "co2_saved_t": 0.45,
        "virgin_value": 1100,
        "hazard": "none",
        "note": "Already-calcined lime avoids part of the kiln's calcination CO2, which is why "
                "the credit is high for a cheap material. Needs dewatering and silica and "
                "alkali checks before it enters the raw mill.",
    },
    {
        "material": "lime sludge",
        "application": "agricultural liming and soil conditioning",
        "accepting_sectors": ["agriculture"],
        "replaces": "mined agricultural lime",
        "substitution_ratio": 1.0,
        "max_share": 0.80,
        "processing": "simple",
        "max_km": 120,
        "co2_saved_t": 0.10,
        "virgin_value": 900,
        "hazard": "none",
        "note": "Effective on acid soils in the east and north-east. Wet sludge is expensive "
                "to cart relative to its value, so the catchment is small.",
    },
    {
        "material": "paper sludge",
        "application": "cement kiln co-processing as alternative fuel",
        "accepting_sectors": ["cement"],
        "replaces": "thermal coal",
        "substitution_ratio": 0.30,
        "max_share": 0.05,
        "processing": "moderate",
        "max_km": 300,
        "co2_saved_t": 0.55,
        "virgin_value": 2400,
        "hazard": "none",
        "note": "Co-processing follows CPCB's 2017 guidelines; the kiln needs a trial run and "
                "state board concurrence even for a non-hazardous stream. Sludge at 50-60% "
                "moisture must be dried before it contributes any net heat.",
    },
    {
        "material": "paper sludge",
        "application": "moulded fibre packaging and board filler",
        "accepting_sectors": ["paper", "construction materials"],
        "replaces": "virgin recycled fibre",
        "substitution_ratio": 0.45,
        "max_share": 0.15,
        "processing": "moderate",
        "max_km": 150,
        "co2_saved_t": 0.25,
        "virgin_value": 3000,
        "hazard": "none",
        "note": "Short fibres limit strength, so the share stays low in anything structural. "
                "Ash and stickies content decide whether a mill will take it at all.",
    },
    # ------------------------------------------------------------------
    # Textile
    # ------------------------------------------------------------------
    {
        "material": "textile ETP sludge",
        "application": "cement kiln co-processing",
        "accepting_sectors": ["cement"],
        "replaces": "thermal coal and raw meal minerals",
        "substitution_ratio": 0.08,
        "max_share": 0.02,
        "processing": "complex",
        "max_km": 300,
        "co2_saved_t": 0.10,
        "virgin_value": 400,
        "hazard": "regulated",
        "note": "Listed under the Hazardous and Other Wastes Rules 2016; the kiln needs CPCB "
                "co-processing authorisation and a completed trial burn, and the generator "
                "needs manifest-tracked transport. Calorific value is negligible - this is "
                "destruction with mineral recovery, not fuel substitution. Avoiding TSDF "
                "landfill charges is the real economics.",
        "disposal_cost": 6500,
    },
    {
        "material": "cotton waste",
        "application": "open-end yarn from mechanically recycled fibre",
        "accepting_sectors": ["textile"],
        "replaces": "virgin cotton lint",
        "substitution_ratio": 0.85,
        "max_share": 0.30,
        "processing": "moderate",
        "max_km": 600,
        "co2_saved_t": 2.80,
        "virgin_value": 62000,
        "hazard": "none",
        "note": "Cotton's irrigation and fertiliser burden makes this one of the highest CO2 "
                "credits per tonne in the table. Shredding shortens the staple, so recycled "
                "content is capped around 30% before yarn strength fails. Colour sorting is "
                "what decides commercial value.",
    },
    {
        "material": "cotton waste",
        "application": "nonwoven felt, insulation and wiping cloth",
        "accepting_sectors": ["textile", "construction materials"],
        "replaces": "virgin cotton and polyester staple",
        "substitution_ratio": 0.90,
        "max_share": 0.50,
        "processing": "simple",
        "max_km": 500,
        "co2_saved_t": 1.80,
        "virgin_value": 38000,
        "hazard": "none",
        "note": "Tolerates mixed colours and short staple, so it takes the grades yarn "
                "spinning rejects. Lower value per tonne but far easier to qualify.",
    },
    # ------------------------------------------------------------------
    # Food and beverage
    # ------------------------------------------------------------------
    {
        "material": "spent grain",
        "application": "wet cattle and dairy feed",
        "accepting_sectors": ["dairy", "feed", "agriculture"],
        "replaces": "compound cattle feed",
        "substitution_ratio": 0.35,
        "max_share": 0.25,
        "processing": "none",
        "max_km": 60,
        "co2_saved_t": 0.45,
        "virgin_value": 18000,
        "hazard": "none",
        "note": "Around 75% moisture and it spoils within 48 hours in Indian summers, which is "
                "why the radius is the shortest in this table. Drying would extend it but "
                "rarely pays at brewery scale.",
    },
    {
        "material": "whey",
        "application": "whey protein concentrate and permeate recovery",
        "accepting_sectors": ["dairy", "feed", "beverage"],
        "replaces": "skim milk powder",
        "substitution_ratio": 0.06,
        "max_share": 0.30,
        "processing": "complex",
        "max_km": 80,
        "co2_saved_t": 0.35,
        "virgin_value": 320000,
        "hazard": "none",
        "note": "Only about 6% solids, so a tonne of whey yields very little powder - the high "
                "unit value of skim milk powder is what makes it worth recovering at all. "
                "Ultrafiltration and spray drying are capital-heavy. Unprocessed whey dumped "
                "to drain is a major BOD load, which is the compliance driver.",
    },
    {
        "material": "used cooking oil",
        "application": "biodiesel transesterification feedstock",
        "accepting_sectors": ["biodiesel", "chemicals"],
        "replaces": "virgin vegetable oil",
        "substitution_ratio": 0.90,
        "max_share": 0.70,
        "processing": "moderate",
        "max_km": 600,
        "co2_saved_t": 2.50,
        "virgin_value": 78000,
        "hazard": "none",
        "note": "FSSAI's RUCO framework bars reuse in food above 25 total polar compounds, "
                "which is what creates the supply. Collection from thousands of small kitchens "
                "is the hard part, not the chemistry. Free fatty acid content sets the "
                "pre-treatment needed.",
    },
    {
        "material": "process CO2",
        "application": "beverage-grade and industrial merchant CO2",
        "accepting_sectors": ["beverage", "chemicals", "fertiliser"],
        "replaces": "merchant CO2 from dedicated production",
        "substitution_ratio": 1.0,
        "max_share": 0.90,
        "processing": "moderate",
        "max_km": 400,
        "co2_saved_t": 0.35,
        "virgin_value": 9000,
        "hazard": "none",
        "note": "Ammonia and ethanol plants vent high-purity CO2 that merchant gas companies "
                "otherwise make on purpose. The credit counts only the avoided production "
                "emissions - the carbon itself is released again when the drink is opened, so "
                "this is not sequestration and should not be presented as such.",
    },
    # ------------------------------------------------------------------
    # Non-ferrous and refinery
    # ------------------------------------------------------------------
    {
        "material": "red mud",
        "application": "cement raw meal iron corrective",
        "accepting_sectors": ["cement"],
        "replaces": "laterite and iron ore",
        "substitution_ratio": 1.0,
        "max_share": 0.03,
        "processing": "moderate",
        "max_km": 250,
        "co2_saved_t": 0.12,
        "virgin_value": 1500,
        "hazard": "none",
        "note": "Not listed as hazardous in India, but pH 10-12 and high sodium mean SPCB "
                "consent, covered transport and careful handling. Alkali limits in clinker cap "
                "the addition near 3% of raw meal - a huge alumina refinery can only place a "
                "small fraction of its output this way.",
        "disposal_cost": 900,
    },
    {
        "material": "red mud",
        "application": "road embankment and low-grade fill",
        "accepting_sectors": ["road project"],
        "replaces": "borrow earth",
        "substitution_ratio": 1.0,
        "max_share": 0.25,
        "processing": "moderate",
        "max_km": 100,
        "co2_saved_t": 0.04,
        "virgin_value": 400,
        "hazard": "none",
        "note": "Trialled on NH stretches in Odisha and Gujarat. Needs neutralisation, lime "
                "or gypsum blending and a sealed capping layer to stop alkaline runoff; "
                "without that, it should not be used.",
        "disposal_cost": 900,
    },
    {
        "material": "spent pot lining",
        "application": "cement kiln co-processing and steel flux",
        "accepting_sectors": ["cement", "steel"],
        "replaces": "fluorspar and thermal coal",
        "substitution_ratio": 0.25,
        "max_share": 0.01,
        "processing": "complex",
        "max_km": 500,
        "co2_saved_t": 0.30,
        "virgin_value": 3500,
        "hazard": "regulated",
        "note": "Schedule I hazardous waste under the 2016 Rules - it contains cyanide and "
                "leachable fluoride and reacts with water to release ammonia and hydrogen. "
                "Co-processing needs CPCB authorisation and a trial burn, and the first cut "
                "(carbon) is usually separated from the second (refractory). Disposal cost "
                "avoided is the dominant term in the economics.",
        "disposal_cost": 9000,
    },
    {
        "material": "recovered sulphur",
        "application": "sulphuric acid and phosphatic fertiliser feed",
        "accepting_sectors": ["fertiliser", "chemicals"],
        "replaces": "imported elemental sulphur",
        "substitution_ratio": 1.0,
        "max_share": 0.95,
        "processing": "none",
        "max_km": 900,
        "co2_saved_t": 0.20,
        "virgin_value": 12000,
        "hazard": "none",
        "note": "India imports most of its sulphur, so refinery Claus units and fertiliser "
                "plants are natural partners and rail hauls of 900 km already happen. Prilled "
                "or granular form ships far better than molten.",
    },
    {
        "material": "spent catalyst",
        "application": "molybdenum, vanadium and nickel recovery",
        "accepting_sectors": ["metal recovery", "chemicals"],
        "replaces": "virgin ferro-molybdenum and vanadium pentoxide",
        "substitution_ratio": 0.12,
        "max_share": 0.40,
        "processing": "complex",
        "max_km": 1200,
        "co2_saved_t": 6.50,
        "virgin_value": 480000,
        "hazard": "regulated",
        "note": "Schedule I hazardous waste, and the highest-value stream here: primary "
                "molybdenum and vanadium production is so energy-intensive that recovery saves "
                "several tonnes of CO2 per tonne of catalyst. That value is what supports a "
                "1200 km haul. Requires an authorised recycler, manifest tracking and "
                "de-oiling and roasting before hydrometallurgy.",
        "disposal_cost": 15000,
    },
    # ------------------------------------------------------------------
    # Municipal and mixed streams
    # ------------------------------------------------------------------
    {
        "material": "RDF",
        "application": "cement kiln alternative fuel",
        "accepting_sectors": ["cement"],
        "replaces": "thermal coal",
        "substitution_ratio": 0.55,
        "max_share": 0.15,
        "processing": "moderate",
        "max_km": 250,
        "co2_saved_t": 0.95,
        "virgin_value": 3200,
        "hazard": "none",
        "note": "Thermal substitution rates at Indian kilns sit near 5-15% against 40%+ in "
                "Europe, limited by chlorine, moisture and feeding equipment rather than by "
                "supply. CPCB co-processing guidelines apply and the kiln needs a pre-heater "
                "feed point. Quality varies with the source city's segregation.",
    },
    {
        "material": "waste tyres",
        "application": "tyre-derived fuel with steel recovery",
        "accepting_sectors": ["cement"],
        "replaces": "thermal coal",
        "substitution_ratio": 1.10,
        "max_share": 0.10,
        "processing": "moderate",
        "max_km": 400,
        "co2_saved_t": 1.60,
        "virgin_value": 4200,
        "hazard": "none",
        "note": "At 30-32 MJ/kg, tyre chips out-perform Indian coal tonne for tonne, and the "
                "bead wire reports to clinker as useful iron. Whole-tyre injection needs a "
                "kiln door modification; chipping is the cheaper route. Zinc build-up sets "
                "the ceiling.",
    },
    {
        "material": "glass cullet",
        "application": "container glass furnace batch",
        "accepting_sectors": ["glass"],
        "replaces": "silica sand, soda ash and limestone",
        "substitution_ratio": 1.20,
        "max_share": 0.70,
        "processing": "simple",
        "max_km": 400,
        "co2_saved_t": 0.60,
        "virgin_value": 4800,
        "hazard": "none",
        "note": "Cullet melts at a lower temperature and carries no carbonate, so it saves both "
                "fuel and process CO2 - and 1.2 t of batch materials per tonne used. Colour "
                "separation and removal of ceramics and metal closures are the binding "
                "constraints; a single stone can ruin a furnace campaign.",
    },
    {
        "material": "C&D waste",
        "application": "recycled coarse aggregate for concrete and sub-base",
        "accepting_sectors": ["construction materials", "road project"],
        "replaces": "natural coarse aggregate",
        "substitution_ratio": 1.0,
        "max_share": 0.30,
        "processing": "moderate",
        "max_km": 80,
        "co2_saved_t": 0.05,
        "virgin_value": 750,
        "hazard": "none",
        "note": "IS 383:2016 permits up to 25% recycled concrete aggregate in plain concrete "
                "and 100% in lean applications. The C&D Waste Rules 2016 require bulk "
                "generators to hand material over. Value is so low that anything beyond about "
                "80 km is freight-dead.",
    },
]


def sectors() -> list:
    """Every sector that appears as a receiver anywhere in the knowledge base."""
    found = set()
    for entry in SUBSTITUTIONS:
        found.update(entry["accepting_sectors"])
    return sorted(found)


def materials() -> list:
    """Every by-product the knowledge base recognises."""
    return sorted({entry["material"] for entry in SUBSTITUTIONS})


def uses_for(material: str) -> list:
    """All recorded applications for a by-product, in knowledge base order."""
    key = str(material).strip().lower()
    return [e for e in SUBSTITUTIONS if e["material"].lower() == key]


# ======================================================================
# Material property profiles
# ======================================================================
#
# What these are for
# ------------------
# The substitution table above only matches a stream the knowledge base has
# heard of. The "hidden" exchanges are the ones nobody wrote down: a residue
# with no recorded use that is chemically close to one that has several.
#
# These profiles let the engine answer "what does this stream resemble?"
# deterministically, without a language model and without embeddings. Each
# material carries a vector of indicative properties; engine.analogues()
# compares them and reports which properties drive the resemblance, so a
# suggestion can always be argued with rather than taken on faith.
#
# Honesty about the numbers
# -------------------------
# These are INDICATIVE TYPICAL compositions for screening only - the middle of
# a published range for a stream of that type, not an assay of anybody's
# actual waste. A real pairing needs a laboratory analysis of the real
# material. Nothing here feeds the score or the valuation: profiles are used
# only to rank resemblance and to suggest what to test next.
#
# Units: mass fractions 0-1, except
#   calorific  - lower heating value / 35 MJ/kg  (so 1.0 is about fuel oil)
#   density    - bulk density / 2.5 t/m3
#   alkalinity - (pH - 4) / 10, so 0.5 is pH 9 and 0.95 is pH 13.5
PROFILE_KEYS = (
    "sio2", "al2o3", "cao", "fe2o3", "sulphur", "metal",
    "carbon", "calorific", "moisture", "density", "alkalinity",
)

# How much each property counts when ranking resemblance. Composition and
# combustibility decide whether a substitution is even conceivable; moisture
# and density decide whether it can be handled, and matter less.
PROFILE_WEIGHTS = {
    "sio2": 1.2, "al2o3": 1.0, "cao": 1.2, "fe2o3": 1.0, "sulphur": 1.0,
    "metal": 1.3, "carbon": 1.2, "calorific": 1.3, "moisture": 0.7,
    "density": 0.5, "alkalinity": 0.8,
}

MATERIAL_PROFILES = {
    # --- coal ash and desulphurisation residues ---
    "fly ash":            dict(sio2=.58, al2o3=.26, cao=.04, fe2o3=.06, sulphur=.01,
                               metal=.00, carbon=.02, calorific=.03, moisture=.01,
                               density=.42, alkalinity=.50),
    "bottom ash":         dict(sio2=.55, al2o3=.24, cao=.05, fe2o3=.07, sulphur=.01,
                               metal=.00, carbon=.05, calorific=.05, moisture=.15,
                               density=.48, alkalinity=.50),
    "FGD gypsum":         dict(sio2=.02, al2o3=.01, cao=.32, fe2o3=.01, sulphur=.19,
                               metal=.00, carbon=.00, calorific=.00, moisture=.10,
                               density=.45, alkalinity=.45),
    # --- iron and steel ---
    "blast furnace slag": dict(sio2=.34, al2o3=.16, cao=.40, fe2o3=.01, sulphur=.01,
                               metal=.00, carbon=.00, calorific=.00, moisture=.05,
                               density=.48, alkalinity=.60),
    "steel slag":         dict(sio2=.14, al2o3=.03, cao=.42, fe2o3=.25, sulphur=.01,
                               metal=.05, carbon=.00, calorific=.00, moisture=.04,
                               density=.56, alkalinity=.70),
    "mill scale":         dict(sio2=.01, al2o3=.00, cao=.01, fe2o3=.95, sulphur=.00,
                               metal=.70, carbon=.01, calorific=.01, moisture=.03,
                               density=.80, alkalinity=.50),
    "ferrous scrap":      dict(sio2=.01, al2o3=.00, cao=.00, fe2o3=.05, sulphur=.00,
                               metal=.95, carbon=.01, calorific=.00, moisture=.01,
                               density=1.00, alkalinity=.50),
    # --- energy streams ---
    "coke oven gas":      dict(sio2=.00, al2o3=.00, cao=.00, fe2o3=.00, sulphur=.01,
                               metal=.00, carbon=.35, calorific=1.00, moisture=.02,
                               density=.00, alkalinity=.50),
    "waste heat":         dict(sio2=.00, al2o3=.00, cao=.00, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.00, calorific=1.00, moisture=.00,
                               density=.00, alkalinity=.50),
    # --- sugar, distillery and agricultural residue ---
    "bagasse":            dict(sio2=.02, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.45, calorific=.26, moisture=.50,
                               density=.06, alkalinity=.50),
    "press mud":          dict(sio2=.05, al2o3=.01, cao=.08, fe2o3=.02, sulphur=.01,
                               metal=.00, carbon=.35, calorific=.17, moisture=.65,
                               density=.30, alkalinity=.50),
    "molasses":           dict(sio2=.00, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.01,
                               metal=.00, carbon=.40, calorific=.31, moisture=.20,
                               density=.58, alkalinity=.50),
    "spent wash":         dict(sio2=.01, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.02,
                               metal=.00, carbon=.06, calorific=.03, moisture=.92,
                               density=.40, alkalinity=.35),
    "rice husk":          dict(sio2=.18, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.40, calorific=.37, moisture=.10,
                               density=.05, alkalinity=.50),
    "rice husk ash":      dict(sio2=.90, al2o3=.01, cao=.01, fe2o3=.01, sulphur=.00,
                               metal=.00, carbon=.05, calorific=.05, moisture=.02,
                               density=.18, alkalinity=.55),
    "sawdust":            dict(sio2=.01, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.48, calorific=.43, moisture=.15,
                               density=.08, alkalinity=.50),
    "cotton waste":       dict(sio2=.01, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.45, calorific=.49, moisture=.08,
                               density=.06, alkalinity=.50),
    # --- pulp, paper and lime ---
    "lime sludge":        dict(sio2=.03, al2o3=.01, cao=.48, fe2o3=.01, sulphur=.00,
                               metal=.00, carbon=.02, calorific=.01, moisture=.35,
                               density=.40, alkalinity=.75),
    "paper sludge":       dict(sio2=.10, al2o3=.08, cao=.20, fe2o3=.01, sulphur=.00,
                               metal=.00, carbon=.25, calorific=.17, moisture=.55,
                               density=.32, alkalinity=.55),
    # --- textile and food ---
    "textile ETP sludge": dict(sio2=.12, al2o3=.06, cao=.10, fe2o3=.05, sulphur=.03,
                               metal=.02, carbon=.15, calorific=.09, moisture=.60,
                               density=.36, alkalinity=.60),
    "spent grain":        dict(sio2=.01, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.45, calorific=.20, moisture=.75,
                               density=.35, alkalinity=.50),
    "whey":               dict(sio2=.00, al2o3=.00, cao=.01, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.05, calorific=.03, moisture=.94,
                               density=.41, alkalinity=.45),
    "used cooking oil":   dict(sio2=.00, al2o3=.00, cao=.00, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.77, calorific=1.00, moisture=.01,
                               density=.37, alkalinity=.50),
    "process CO2":        dict(sio2=.00, al2o3=.00, cao=.00, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.27, calorific=.00, moisture=.01,
                               density=.00, alkalinity=.45),
    # --- non-ferrous and refinery ---
    "red mud":            dict(sio2=.12, al2o3=.17, cao=.05, fe2o3=.45, sulphur=.01,
                               metal=.01, carbon=.00, calorific=.00, moisture=.30,
                               density=.50, alkalinity=.95),
    "spent pot lining":   dict(sio2=.05, al2o3=.15, cao=.02, fe2o3=.02, sulphur=.01,
                               metal=.02, carbon=.45, calorific=.49, moisture=.02,
                               density=.40, alkalinity=.80),
    "recovered sulphur":  dict(sio2=.00, al2o3=.00, cao=.00, fe2o3=.00, sulphur=1.00,
                               metal=.00, carbon=.00, calorific=.26, moisture=.01,
                               density=.80, alkalinity=.40),
    "spent catalyst":     dict(sio2=.05, al2o3=.45, cao=.01, fe2o3=.02, sulphur=.08,
                               metal=.25, carbon=.10, calorific=.10, moisture=.05,
                               density=.40, alkalinity=.50),
    # --- municipal and mixed ---
    "RDF":                dict(sio2=.05, al2o3=.02, cao=.03, fe2o3=.01, sulphur=.00,
                               metal=.01, carbon=.45, calorific=.49, moisture=.20,
                               density=.12, alkalinity=.50),
    "waste tyres":        dict(sio2=.02, al2o3=.00, cao=.01, fe2o3=.02, sulphur=.02,
                               metal=.12, carbon=.70, calorific=.89, moisture=.01,
                               density=.20, alkalinity=.50),
    "glass cullet":       dict(sio2=.72, al2o3=.02, cao=.10, fe2o3=.00, sulphur=.00,
                               metal=.00, carbon=.00, calorific=.00, moisture=.00,
                               density=1.00, alkalinity=.60),
    "C&D waste":          dict(sio2=.45, al2o3=.10, cao=.18, fe2o3=.03, sulphur=.01,
                               metal=.01, carbon=.02, calorific=.02, moisture=.05,
                               density=.64, alkalinity=.60),

    # --- streams with NO recorded substitution above ---
    # Profiles are given so the engine can still say what they resemble. These
    # are exactly the cases the gap analysis is for.
    "cement kiln dust":   dict(sio2=.14, al2o3=.04, cao=.45, fe2o3=.02, sulphur=.03,
                               metal=.00, carbon=.01, calorific=.00, moisture=.02,
                               density=.40, alkalinity=.90),
    "jarosite":           dict(sio2=.05, al2o3=.02, cao=.02, fe2o3=.30, sulphur=.12,
                               metal=.05, carbon=.00, calorific=.00, moisture=.30,
                               density=.50, alkalinity=.25),
    "chrome tanning sludge": dict(sio2=.05, al2o3=.02, cao=.12, fe2o3=.02, sulphur=.02,
                               metal=.04, carbon=.20, calorific=.10, moisture=.65,
                               density=.38, alkalinity=.60),
}

# A one-line plain description of what dominates each property, used to explain
# why two materials resemble each other.
PROFILE_LABELS = {
    "sio2": "silica content", "al2o3": "alumina content", "cao": "lime content",
    "fe2o3": "iron oxide content", "sulphur": "sulphur content",
    "metal": "recoverable metal content", "carbon": "organic carbon content",
    "calorific": "calorific value", "moisture": "moisture", "density": "bulk density",
    "alkalinity": "alkalinity",
}


def profile_for(material: str) -> dict | None:
    """The indicative property profile for a material, or None if unrecorded."""
    key = str(material).strip().lower()
    for name, profile in MATERIAL_PROFILES.items():
        if name.lower() == key:
            return profile
    return None
