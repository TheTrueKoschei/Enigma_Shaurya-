"""English and Hindi strings for the interface chrome.

Only the navigation, labels, headings and short standing text are translated.
The analytical narrative produced by explain.py stays in English in this build,
and the interface says so when Hindi is selected rather than leaving the reader
to discover it. Devanagari renders through Noto Sans Devanagari, loaded with the
rest of the type.
"""

from __future__ import annotations

LANGUAGES = {"en": "English", "hi": "हिन्दी"}

STRINGS = {
    # --- masthead and chrome ---
    "portal": {"en": "Industrial Symbiosis Portal",
               "hi": "औद्योगिक सहजीवन पोर्टल"},
    "portal_sub": {"en": "By-product exchange discovery and assessment",
                   "hi": "उपोत्पाद विनिमय की खोज और मूल्यांकन"},
    "prototype": {
        "en": "Prototype built for ENIGMA 5.0, Sustainability track, PS 5. "
              "Not affiliated with, or endorsed by, any government body.",
        "hi": "ENIGMA 5.0, सस्टेनेबिलिटी ट्रैक, PS 5 के लिए बनाया गया प्रोटोटाइप। "
              "किसी सरकारी संस्था से संबद्ध या अनुमोदित नहीं।"},
    "skip": {"en": "Skip to main content", "hi": "मुख्य सामग्री पर जाएँ"},
    "text_size": {"en": "Text size", "hi": "अक्षर आकार"},
    "contrast": {"en": "High contrast", "hi": "उच्च कंट्रास्ट"},
    "language": {"en": "Language", "hi": "भाषा"},
    "home": {"en": "Home", "hi": "मुख्य पृष्ठ"},
    "hindi_note": {
        "en": "",
        "hi": "सूचना: नेविगेशन और लेबल हिन्दी में हैं। विश्लेषणात्मक विवरण, "
              "ज्ञान-आधार की टिप्पणियाँ और लेखा-परीक्षा तालिकाएँ इस संस्करण में "
              "अंग्रेज़ी में ही रहती हैं।"},

    # --- tabs ---
    "tab_grading": {"en": "Material Grading", "hi": "सामग्री श्रेणीकरण"},
    "tab_blend": {"en": "Blend to Spec", "hi": "मिश्रण द्वारा अनुपालन"},
    "tab_mine": {"en": "Find My Matches", "hi": "मेरे मिलान खोजें"},
    "tab_network": {"en": "Exchange Network", "hi": "विनिमय नेटवर्क"},
    "tab_matches": {"en": "Ranked Matches", "hi": "क्रमित मिलान"},
    "tab_chains": {"en": "Chains & Impact", "hi": "शृंखलाएँ और प्रभाव"},
    "tab_gaps": {"en": "Gap Analysis", "hi": "अंतराल विश्लेषण"},
    "tab_method": {"en": "Method", "hi": "पद्धति"},

    # --- headline indicators ---
    "kpi_exchanges": {"en": "Viable exchanges", "hi": "व्यवहार्य विनिमय"},
    "kpi_tonnes": {"en": "Tonnes diverted", "hi": "परिवर्तित टनभार"},
    "kpi_co2": {"en": "CO2 avoided", "hi": "टाली गई CO2"},
    "kpi_value": {"en": "Value unlocked", "hi": "अर्जित मूल्य"},
    "kpi_unmatched": {"en": "Still unmatched", "hi": "अब भी अमिलित"},
    "kpi_circularity": {"en": "Circularity", "hi": "चक्रीयता"},
    "per_year": {"en": "per year", "hi": "प्रति वर्ष"},
    "suppliers_receivers": {"en": "suppliers", "hi": "आपूर्तिकर्ता"},
    "receivers": {"en": "receivers", "hi": "प्राप्तकर्ता"},
    "at_a_loss": {"en": "run at a loss", "hi": "घाटे में"},
    "streams_unplaced": {"en": "streams with nowhere to go", "hi": "धाराएँ बिना गंतव्य"},
    "of_produced": {"en": "of by-product produced", "hi": "उत्पादित उपोत्पाद में से"},

    # --- sidebar ---
    "sb_registry": {"en": "Registry", "hi": "पंजी"},
    "sb_sample": {"en": "Sample registry", "hi": "नमूना पंजी"},
    "sb_upload": {"en": "Upload a CSV", "hi": "CSV अपलोड करें"},
    "sb_template": {"en": "Download CSV template", "hi": "CSV टेम्पलेट डाउनलोड करें"},
    "sb_threshold": {"en": "Threshold", "hi": "न्यूनतम सीमा"},
    "sb_min_score": {"en": "Minimum score", "hi": "न्यूनतम अंक"},

    # --- find my matches ---
    "mine_heading": {"en": "Describe your plant", "hi": "अपने संयंत्र का विवरण दें"},
    "mine_role": {"en": "What are you looking for?", "hi": "आप क्या खोज रहे हैं?"},
    "role_supplier": {"en": "I have a by-product to place",
                      "hi": "मेरे पास रखने योग्य उपोत्पाद है"},
    "role_receiver": {"en": "I need raw material", "hi": "मुझे कच्चा माल चाहिए"},
    "f_byproduct": {"en": "By-product you produce", "hi": "आपका उपोत्पाद"},
    "f_accept": {"en": "By-product you could accept", "hi": "स्वीकार्य उपोत्पाद"},
    "f_sector": {"en": "Your sector", "hi": "आपका क्षेत्र"},
    "f_location": {"en": "Nearest industrial centre", "hi": "निकटतम औद्योगिक केंद्र"},
    "f_exact": {"en": "Enter exact coordinates", "hi": "सटीक निर्देशांक भरें"},
    "f_qty_out": {"en": "Tonnes per year you produce", "hi": "वार्षिक उत्पादन (टन)"},
    "f_qty_in": {"en": "Tonnes per year of input you draw", "hi": "वार्षिक कच्चा माल (टन)"},
    "f_season": {"en": "When you operate", "hi": "संचालन अवधि"},
    "f_authorised": {"en": "Authorised to handle hazardous waste",
                     "hi": "संकटमय अपशिष्ट हेतु अधिकृत"},
    "btn_rank": {"en": "Rank my options", "hi": "विकल्प क्रमित करें"},
    "mine_partners": {"en": "Viable partners", "hi": "व्यवहार्य साझेदार"},
    "mine_best": {"en": "Best score", "hi": "सर्वोच्च अंक"},
    "mine_best_value": {"en": "Best net value", "hi": "सर्वोच्च शुद्ध मूल्य"},
    "mine_best_co2": {"en": "Best CO2 avoided", "hi": "सर्वाधिक टाली गई CO2"},
    "mine_ranked": {"en": "Ranked partners", "hi": "क्रमित साझेदार"},
    "mine_inspect": {"en": "Inspect a partner", "hi": "साझेदार का विवरण"},
    "mine_download": {"en": "Download my ranked list", "hi": "क्रमित सूची डाउनलोड करें"},

    # --- shared ---
    "audit": {"en": "Audit this score and valuation",
              "hi": "अंक और मूल्यांकन की लेखा-परीक्षा"},
    "download_all": {"en": "Download all matches as CSV",
                     "hi": "सभी मिलान CSV में डाउनलोड करें"},
    "exchange": {"en": "Exchange", "hi": "विनिमय"},
    "score": {"en": "Score", "hi": "अंक"},
    "net_value_yr": {"en": "Net value/yr", "hi": "शुद्ध मूल्य/वर्ष"},
    "tonnes_yr": {"en": "Tonnes/yr", "hi": "टन/वर्ष"},
    "co2_yr": {"en": "CO2 avoided/yr", "hi": "CO2 बचत/वर्ष"},
    "data_quality": {"en": "Data quality notes on this registry",
                     "hi": "इस पंजी पर डेटा गुणवत्ता टिप्पणियाँ"},

    # --- network ---
    "map_colour_by": {"en": "Colour states by", "hi": "राज्यों का रंग आधार"},
    "map_filter_states": {"en": "Filter states", "hi": "राज्य छाँटें"},
    "map_filter_materials": {"en": "Filter materials", "hi": "सामग्री छाँटें"},
    "map_flows": {"en": "Flows to draw", "hi": "प्रदर्शित प्रवाह"},
    "map_top_states": {"en": "Top states by", "hi": "शीर्ष राज्य"},
    "m_exchanges": {"en": "Exchanges involved", "hi": "संबद्ध विनिमय"},
    "m_supplied": {"en": "Tonnes supplied", "hi": "आपूर्ति टनभार"},
    "m_received": {"en": "Tonnes received", "hi": "प्राप्त टनभार"},
    "m_facilities": {"en": "Facilities", "hi": "संयंत्र"},

    # --- chains and impact ---
    "chains_heading": {"en": "What the network is worth, and how to run it",
                       "hi": "नेटवर्क का मूल्य और संचालन"},
    "basis": {"en": "Allocation basis", "hi": "आवंटन आधार"},
    "basis_opt": {"en": "Optimised (linear programming)", "hi": "अनुकूलित (रैखिक प्रोग्रामिंग)"},
    "basis_greedy": {"en": "Greedy (best score first)", "hi": "लोभी (सर्वोच्च अंक पहले)"},
    "imp_landfill": {"en": "Landfill diverted", "hi": "भराव से बचाव"},
    "imp_virgin": {"en": "Virgin material avoided", "hi": "टाला गया कुँवारा पदार्थ"},
    "imp_net": {"en": "Net value", "hi": "शुद्ध मूल्य"},
    "opt_vs_greedy": {"en": "Optimiser against greedy", "hi": "अनुकूलक बनाम लोभी"},
    "chains_found": {"en": "Multi-hop chains", "hi": "बहु-चरण शृंखलाएँ"},
    "chain_walk": {"en": "Walk a chain", "hi": "शृंखला देखें"},

    # --- gaps ---
    "gaps_heading": {"en": "By-products with no viable receiver",
                     "hi": "बिना प्राप्तकर्ता के उपोत्पाद"},
    "gaps_unplaced": {"en": "Unplaced streams", "hi": "अस्थापित धाराएँ"},
    "gaps_tonnes": {"en": "Tonnes with nowhere to go", "hi": "बिना गंतव्य टनभार"},
    "gaps_disposal": {"en": "Disposal cost carried", "hi": "वहन किया गया निपटान व्यय"},
    "gaps_examine": {"en": "Examine a stream", "hi": "धारा की जाँच करें"},
    "gaps_resembles": {"en": "What this stream resembles", "hi": "यह धारा किससे मिलती है"},
    "gaps_uses": {"en": "Every recorded use for this stream",
                  "hi": "इस धारा के सभी अभिलिखित उपयोग"},

    # --- material grading ---
    "mg_heading": {"en": "Grade a by-product against every specification",
                   "hi": "हर विनिर्देश के विरुद्ध उपोत्पाद का श्रेणीकरण"},
    "mg_pick": {"en": "By-product stream", "hi": "उपोत्पाद धारा"},
    "mg_composition": {"en": "Measured composition", "hi": "मापित संघटन"},
    "mg_against": {"en": "Graded against the specification library",
                   "hi": "विनिर्देश संग्रह के विरुद्ध श्रेणीकरण"},
    "mg_detail": {"en": "Inspect a specification", "hi": "विनिर्देश की जाँच करें"},
    "mg_qualifies": {"en": "Applications it qualifies for",
                     "hi": "योग्य अनुप्रयोग"},
    "mg_best": {"en": "Best qualifying use", "hi": "सर्वोत्तम योग्य उपयोग"},
    "mg_discount": {"en": "Quality discount", "hi": "गुणवत्ता छूट"},
    "mg_ladder": {"en": "Value ladder", "hi": "मूल्य सोपान"},
    "mg_upgrade": {"en": "Closest rung not yet reached",
                   "hi": "निकटतम अप्राप्त स्तर"},

    # --- blending ---
    "bl_heading": {"en": "Reach a specification by blending two streams",
                   "hi": "दो धाराओं के मिश्रण से विनिर्देश प्राप्त करें"},
    "bl_stream_a": {"en": "Stream A", "hi": "धारा A"},
    "bl_stream_b": {"en": "Stream B", "hi": "धारा B"},
    "bl_target": {"en": "Target specification", "hi": "लक्ष्य विनिर्देश"},
    "bl_feasible": {"en": "Feasible blend range", "hi": "संभाव्य मिश्रण परास"},
    "bl_recommended": {"en": "Recommended blend", "hi": "अनुशंसित मिश्रण"},
    "bl_before_after": {"en": "Before and after", "hi": "पहले और बाद"},
    "bl_ladder": {"en": "Value ladder", "hi": "मूल्य सोपान"},

    # --- method ---
    "method_scoring": {"en": "How a match is scored", "hi": "मिलान का अंकन कैसे होता है"},
    "method_gates": {"en": "Gates", "hi": "अस्वीकृति नियम"},
    "method_valuation": {"en": "Valuation, per year", "hi": "वार्षिक मूल्यांकन"},
    "method_assumptions": {"en": "Every assumption, stated", "hi": "सभी मान्यताएँ"},
    "method_limits": {"en": "Known limits of this model", "hi": "मॉडल की ज्ञात सीमाएँ"},
    "method_beyond": {"en": "Beyond the substitution table",
                      "hi": "प्रतिस्थापन तालिका से आगे"},
    "method_kb": {"en": "Knowledge base", "hi": "ज्ञान आधार"},
    "method_registry": {"en": "Registry in use", "hi": "प्रयुक्त पंजी"},
}


def t(key: str, lang: str = "en") -> str:
    """Look up a string. Falls back to English, then to the key itself."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get("en") or key
