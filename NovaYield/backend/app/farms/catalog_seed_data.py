"""Product Direction v1 seed facts with field-level evidence and limitations.

The Product Owner authorized researched starter values and close analogues for
this MVP. Each parameter is tagged as direct-source evidence, an analogue
estimate, or a desk synthesis with confidence/applicability/limitations.
Everything remains provisional until Ghana-local review; no seed asserts a
field water balance, measured soil benefit, or locally validated calendar.
"""

from __future__ import annotations

from typing import Any

from app.decisions.crop_profiles import CROP_LIBRARY_VERSION, CROP_PROFILES
from app.models.crop_catalog import EvidenceValue, GrowthStage, SourceEvidence

CSIR_VARIETIES = "https://technologies.csirgh.com/maincropvarieties"
MOFA_MAIZE = "https://mofa.gov.gh/site/images/pdf/production_guides/GUIDE_TO_MAIZE_PRODUCTION.pdf"
MOFA_RICE = "https://mofa.gov.gh/site/images/pdf/production_guides/RICE_Production_Guide.pdf"
FAO_WATER = "https://www.fao.org/4/t7202e/t7202e05.htm"
FAO_CASSAVA = "https://www.fao.org/4/i2929e/i2929e.pdf"
FAO_GHANA_YAM = (
    "https://www.fao.org/fileadmin/templates/agphome/documents/PGR/SoW1/africa/GHANA.PDF"
)
EJURA_TOWN_PROFILE = "https://esma.gov.gh/about-us/town-profile/"
MOFA_EJURA_PROFILE = (
    "https://mofa.gov.gh/site/directorates/55-district-directorates/"
    "district-ashanti/164-ejura-sekyeredumase"
)
LEGACY_GENERIC_PROFILE_NOTE = (
    "Generic identity has no validated local duration or numerical crop traits."
)
GENERIC_PROFILE_SOURCE_NOTE = (
    f"{CROP_LIBRARY_VERSION}: generic identity with provisional NY-8 water class where "
    "sourced; no locally validated calendar, field water balance, or crop-specific threshold."
)

CROP_IDENTITY_SEEDS: tuple[dict[str, Any], ...] = (
    dict(
        crop_key="maize",
        common_name="Maize",
        scientific_name="Zea mays",
        family="Poaceae",
        identity_source_url=MOFA_MAIZE,
        history_selectable=True,
        recommendation_candidate=True,
    ),
    dict(
        crop_key="cowpea",
        common_name="Cowpea",
        scientific_name="Vigna unguiculata",
        family="Fabaceae",
        identity_source_url=CSIR_VARIETIES,
        history_selectable=True,
        recommendation_candidate=True,
    ),
    dict(
        crop_key="groundnut",
        common_name="Groundnut",
        scientific_name="Arachis hypogaea",
        family="Fabaceae",
        identity_source_url=CSIR_VARIETIES,
        history_selectable=True,
        recommendation_candidate=True,
    ),
    dict(
        crop_key="cassava",
        common_name="Cassava",
        scientific_name="Manihot esculenta",
        family="Euphorbiaceae",
        identity_source_url=CSIR_VARIETIES,
        history_selectable=True,
        recommendation_candidate=True,
    ),
    dict(
        crop_key="yam",
        common_name="Yam",
        scientific_name="Dioscorea spp.",
        family="Dioscoreaceae",
        identity_source_url=FAO_GHANA_YAM,
        history_selectable=True,
        recommendation_candidate=True,
    ),
    dict(
        crop_key="rice",
        common_name="Rice",
        scientific_name="Oryza spp.",
        family="Poaceae",
        identity_source_url=MOFA_RICE,
        history_selectable=True,
        recommendation_candidate=False,
        requires_production_system_for_assessment=True,
    ),
    dict(
        crop_key="rice-upland",
        base_crop_key="rice",
        common_name="Rice — Upland",
        scientific_name="Oryza sativa",
        family="Poaceae",
        identity_source_url=MOFA_RICE,
        history_selectable=False,
        recommendation_candidate=True,
        production_system="upland",
        requires_production_system_for_assessment=True,
    ),
    dict(
        crop_key="rice-rain-fed-lowland",
        base_crop_key="rice",
        common_name="Rice — Rain-fed lowland",
        scientific_name="Oryza sativa",
        family="Poaceae",
        identity_source_url=MOFA_RICE,
        history_selectable=False,
        recommendation_candidate=True,
        production_system="rain-fed-lowland",
        requires_production_system_for_assessment=True,
    ),
    dict(
        crop_key="rice-irrigated",
        base_crop_key="rice",
        common_name="Rice — Irrigated",
        scientific_name="Oryza sativa",
        family="Poaceae",
        identity_source_url=MOFA_RICE,
        history_selectable=False,
        recommendation_candidate=True,
        production_system="irrigated",
        requires_production_system_for_assessment=True,
    ),
    # Approved history-only choices reflect reported pilot crops. They never join
    # the six recommendation candidates; ambiguous "beans" has no identity.
    dict(
        crop_key="plantain",
        common_name="Plantain",
        scientific_name=None,
        family=None,
        identity_source_url=EJURA_TOWN_PROFILE,
        history_selectable=True,
        recommendation_candidate=False,
    ),
    dict(
        crop_key="sorghum",
        common_name="Sorghum (guinea corn)",
        scientific_name=None,
        family=None,
        identity_source_url=MOFA_EJURA_PROFILE,
        history_selectable=True,
        recommendation_candidate=False,
    ),
)


def _source(
    url: str,
    title: str,
    *,
    variety: str | None = None,
    production_system: str | None = None,
    source_confidence: str = "moderate",
    pilot_transferability: str = "low",
    applicability: str,
    limitations: str,
    study_location: str | None = None,
) -> SourceEvidence:
    return SourceEvidence(
        source_url=url,
        source_title=title,
        study_location=study_location,
        agroecological_zone="Ghana forest–savanna transition" if url == CSIR_VARIETIES else None,
        variety=variety,
        production_system=production_system,
        source_confidence=source_confidence,
        pilot_transferability=pilot_transferability,
        applicability=applicability,
        limitations=limitations,
        validation_status="provisional",
    )


def _water_class_evidence(crop_key: str) -> EvidenceValue | None:
    """Copy reviewed NY-8 desk evidence into the versioned Mongo crop profile."""

    crop_profile = CROP_PROFILES[crop_key]
    trait = crop_profile.trait("water_resilience_class")
    if trait is None or trait.value not in {"low", "moderate", "high"}:
        return None
    references = tuple(
        reference.strip()
        for reference in (trait.source_reference or "").split(";")
        if reference.strip()
    )
    if not references:
        return None
    return EvidenceValue(
        value={"class": trait.value},
        source=SourceEvidence(
            source_url=references[0],
            additional_source_urls=references[1:],
            source_title=trait.source_title or "NY-8 provisional crop-by-criterion evidence matrix",
            source_publication_date=trait.source_date,
            study_location=trait.study_location,
            agroecological_zone=trait.agroecological_zone,
            variety=trait.variety,
            production_system=trait.production_system,
            management=trait.management_conditions,
            source_confidence=trait.confidence or "low",
            pilot_transferability=trait.pilot_transferability or "low",
            applicability=trait.applicability_notes or "Scoped desk-research crop evidence.",
            limitations=trait.limitations
            or "Pilot transfer and farm-specific suitability are unknown.",
            validation_status="provisional",
        ),
    )


WATER_RESILIENCE_EVIDENCE = {
    crop_key: evidence
    for crop_key in CROP_PROFILES
    if (evidence := _water_class_evidence(crop_key)) is not None
}


def _sensitive_stage(stage_key: str, url: str, title: str, crop: str) -> GrowthStage:
    from app.models.crop_catalog import EvidenceValue

    return GrowthStage(
        stage_key=stage_key,
        start_offset_days=None,
        duration_days=None,
        sensitivity=EvidenceValue(
            value={"factor": "water_shortage", "direction": "sensitive"},
            source=_source(
                url,
                title,
                applicability=f"Broad qualitative {crop} stage sensitivity only.",
                limitations=(
                    "No named pilot variety, exact stage offset/duration, field water balance, "
                    "or damage threshold is established."
                ),
            ),
        ),
    )


GENERIC_STAGE_SEEDS: dict[str, tuple[GrowthStage, ...]] = {
    "maize": (
        _sensitive_stage(
            "flowering-grain-filling", FAO_WATER, "FAO crop water shortage sensitivity", "maize"
        ),
    ),
    "groundnut": (
        _sensitive_stage(
            "flowering-pod-setting", FAO_WATER, "FAO crop water shortage sensitivity", "groundnut"
        ),
    ),
    "cassava": (
        _sensitive_stage(
            "early-establishment", FAO_CASSAVA, "FAO Save and Grow: Cassava", "cassava"
        ),
    ),
    "rice": (
        _sensitive_stage(
            "head-development-flowering", FAO_WATER, "FAO crop water shortage sensitivity", "rice"
        ),
    ),
}


# These ranges are exactly scoped to named varieties. Source table endpoint
# meaning was not verified, so endpoint_verified=False blocks exact scheduling.
NAMED_PROFILE_SEEDS: tuple[dict[str, Any], ...] = (
    dict(
        crop_key="maize",
        variety_key="obatanpa",
        production_system_key=None,
        min_days=105,
        max_days=110,
        source_url=CSIR_VARIETIES,
        variety="Obatanpa",
    ),
    dict(
        crop_key="cowpea",
        variety_key="cri-nketewade",
        production_system_key=None,
        min_days=62,
        max_days=65,
        source_url=CSIR_VARIETIES,
        variety="CRI-Nketewade",
    ),
    dict(
        crop_key="cowpea",
        variety_key="cri-zamzam",
        production_system_key=None,
        min_days=64,
        max_days=67,
        source_url=CSIR_VARIETIES,
        variety="CRI-Zamzam",
    ),
    dict(
        crop_key="groundnut",
        variety_key="crops-nkatie",
        production_system_key=None,
        min_days=90,
        max_days=95,
        source_url=CSIR_VARIETIES,
        variety="Crops nkatie",
    ),
    dict(
        crop_key="groundnut",
        variety_key="crops-agbeyeye",
        production_system_key=None,
        min_days=90,
        max_days=95,
        source_url=CSIR_VARIETIES,
        variety="Crops Agbeyeye",
    ),
    dict(
        crop_key="cassava",
        variety_key="cri-doku-duade",
        production_system_key=None,
        min_days=365,
        max_days=458,
        source_url=CSIR_VARIETIES,
        variety="CRI-Doku Duade",
    ),
    # MoFA and CSIR give conflicting Nabogo ranges. Preserve a scoped record,
    # but no usable duration until an expert resolves the source conflict.
    dict(
        crop_key="rice",
        variety_key="nabogo",
        production_system_key=None,
        min_days=None,
        max_days=None,
        source_url=MOFA_RICE,
        variety="Nabogo",
        evidence_status="conflicted",
    ),
)


REFERENCE_OPTION_SEEDS: tuple[dict[str, Any], ...] = (
    dict(
        kind="soil_texture",
        key="sandy",
        label="Sandy",
        definition="Farmer-reported broad sandy texture; water storage has not been measured.",
    ),
    dict(
        kind="soil_texture",
        key="loamy",
        label="Loamy",
        definition="Farmer-reported broad loamy texture; water storage has not been measured.",
    ),
    dict(
        kind="soil_texture",
        key="clayey",
        label="Clayey",
        definition="Farmer-reported broad clayey texture; water storage has not been measured.",
    ),
    dict(
        kind="soil_texture",
        key="unknown",
        label="I do not know",
        definition="Soil texture is not known or has not been selected.",
    ),
    dict(
        kind="irrigation_access",
        key="none",
        label="No irrigation access",
        definition="Farmer reports no irrigation access; actual rainfall use is not measured.",
    ),
    dict(
        kind="irrigation_access",
        key="supplemental",
        label="Supplemental irrigation access",
        definition="Farmer reports occasional irrigation access; delivered water is unknown.",
    ),
    dict(
        kind="irrigation_access",
        key="regular",
        label="Regular irrigation access",
        definition="Farmer reports regular irrigation access; delivered water is unknown.",
    ),
    dict(
        kind="irrigation_access",
        key="unknown",
        label="I do not know",
        definition="Irrigation access is not known or has not been selected.",
    ),
    dict(
        kind="labour_capacity",
        key="Low",
        label="Low",
        definition="The available labour capacity for this decision plot is low.",
    ),
    dict(
        kind="labour_capacity",
        key="Medium",
        label="Medium",
        definition="The available labour capacity for this decision plot is medium.",
    ),
    dict(
        kind="labour_capacity",
        key="High",
        label="High",
        definition="The available labour capacity for this decision plot is high.",
    ),
    dict(
        kind="farmer_priority",
        key="water_security",
        label="Water security",
        definition="Give water resilience more influence in the rotation comparison.",
    ),
    dict(
        kind="farmer_priority",
        key="soil_health",
        label="Soil health",
        definition=(
            "Give the relative soil-effect profile more influence; this is not a soil measurement."
        ),
    ),
    dict(
        kind="farmer_priority",
        key="fast_turnover",
        label="Fast turnover",
        definition="Give shorter maturity and faster crop turnover more influence.",
    ),
    dict(
        kind="farmer_priority",
        key="low_labour",
        label="Low labour",
        definition="Give lower relative labour demand more influence.",
    ),
    dict(
        kind="rice_production_system",
        key="upland",
        label="Upland",
        definition="Rice grown in an upland production ecology.",
    ),
    dict(
        kind="rice_production_system",
        key="rain-fed-lowland",
        label="Rain-fed lowland",
        definition="Lowland rice dependent on rainfall and local water regime.",
    ),
    dict(
        kind="rice_production_system",
        key="irrigated",
        label="Irrigated",
        definition=(
            "Rice grown with irrigation; this does not imply that water delivery is guaranteed."
        ),
    ),
    dict(
        kind="rice_production_system",
        key="unknown",
        label="I do not know",
        definition="Retain rice in history without inferring its production ecology.",
    ),
)


REGIONAL_CALENDAR_SEEDS: tuple[dict[str, Any], ...] = (
    dict(
        location_key="ejura",
        crop_key="maize",
        season_key="major-rainy-season",
        start_month_day="03-15",
        end_month_day="04-30",
        crosses_year=False,
        calendar_version="product-direction-starter-v1",
        source_url=MOFA_MAIZE,
        source_title="Ghana MoFA Maize Production Guide (2020), transition zone",
        evidence_status="provisional",
        source_note="MoFA regional forest–savanna guide says mid-March to end April. "
        "Mid-month boundary is a calendar encoding of the published phrase, not a validated "
        "local planting date or rain-onset rule.",
    ),
    dict(
        location_key="ejura",
        crop_key="maize",
        season_key="minor-rainy-season",
        start_month_day="07-15",
        end_month_day="09-10",
        crosses_year=False,
        calendar_version="product-direction-starter-v1",
        source_url=MOFA_MAIZE,
        source_title="Ghana MoFA Maize Production Guide (2020), transition zone",
        evidence_status="provisional",
        source_note="MoFA regional forest–savanna guide says mid-July to August/early "
        "September. The end-of-window day is an encoding of 'early September', not a "
        "validated local planting date.",
    ),
    dict(
        location_key="anyinasu",
        crop_key="maize",
        season_key="major-rainy-season",
        start_month_day="03-15",
        end_month_day="04-30",
        crosses_year=False,
        calendar_version="product-direction-starter-v1",
        source_url=MOFA_MAIZE,
        source_title="Ghana MoFA Maize Production Guide (2020), transition zone",
        evidence_status="provisional",
        source_note="MoFA regional forest–savanna guide says mid-March to end April. "
        "This Anyinasu row is supported by the guide's transition-zone scope, not copied "
        "from an Ejura-specific calendar.",
    ),
    dict(
        location_key="anyinasu",
        crop_key="maize",
        season_key="minor-rainy-season",
        start_month_day="07-15",
        end_month_day="09-10",
        crosses_year=False,
        calendar_version="product-direction-starter-v1",
        source_url=MOFA_MAIZE,
        source_title="Ghana MoFA Maize Production Guide (2020), transition zone",
        evidence_status="provisional",
        source_note="MoFA regional forest–savanna guide says mid-July to August/early "
        "September. This Anyinasu row is supported by the guide's transition-zone scope, "
        "not copied from an Ejura-specific calendar.",
    ),
    *(
        dict(
            location_key=location,
            crop_key="cowpea",
            season_key="minor-rainy-season",
            start_month_day="08-01",
            end_month_day="09-30",
            crosses_year=False,
            calendar_version="product-direction-starter-v1",
            source_url=(
                "https://ir.ucc.edu.gh/xmlui/bitstream/handle/123456789/8474/HORD"
                "ZI%2C%202008.pdf?isAllowed=y&sequence=1"
            ),
            source_title=(
                "Hordzi (2008), University of Cape Coast thesis; Ghana-wide season reference"
            ),
            evidence_status="provisional",
            source_note="The cited Ghana-wide source reports August–September for the minor "
            "cowpea season. It is active as a provisional calendar row; it is not local "
            "extension validation for this community.",
        )
        for location in ("ejura", "anyinasu")
    ),
    dict(
        location_key="anyinasu",
        crop_key="yam",
        season_key="major-rainy-season",
        start_month_day="02-01",
        end_month_day="03-31",
        crosses_year=False,
        calendar_version="product-direction-starter-v1",
        source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC10008982/",
        source_title="Baffour-Ata et al. (2023), Ejura-Sekyedumase yam farmer study",
        evidence_status="provisional",
        source_note="February–March reflects an Anyinasu key-informant report in the local "
        "study. It remains provisional and is not extended to Ejura or Kintampo.",
    ),
)


# Product Direction v1 crop records. Trait estimates carry their own evidence
# kind and limitations; values are not claims of local validation.
PRODUCT_CROP_PARAMETER_SEEDS: tuple[dict[str, Any], ...] = (
    dict(
        crop_key="maize",
        group="Cereal",
        aliases=("corn",),
        water_resilience="Low",
        soil_effect="Draws down",
        maturity_days_min=90,
        maturity_days_max=110,
        growth_speed="Medium",
        labour="Low",
        parameter_evidence={
            "water_resilience": dict(
                urls=(FAO_WATER,),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "FAO gives maize 500–800 mm per crop period and medium-to-high "
                    "drought sensitivity."
                ),
            ),
            "soil_effect": dict(
                urls=(
                    "https://pure.ug.edu.gh/en/publications/evaluating-sustainable-and-profitable-cropping-sequences-with-cas-2/",
                ),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Cereal continuous-cropping and maize-stover comparison supports "
                    "a relative drawdown proxy; fertilizer and residue management can "
                    "change the outcome."
                ),
            ),
            "maturity": dict(
                urls=(MOFA_MAIZE,),
                kind="direct_source",
                confidence="high",
                note=(
                    "MoFA gives early varieties 90–95 and medium varieties 105–110 "
                    "days; the catalog stores the combined 90–110 representative "
                    "range."
                ),
            ),
            "growth_speed": dict(
                urls=(MOFA_MAIZE,),
                kind="desk_synthesis",
                confidence="high",
                note=(
                    "Derived from the midpoint of the reported maturity range using "
                    "the configurable 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=("https://pmc.ncbi.nlm.nih.gov/articles/PMC5614088/",),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "Relative labour tier estimated from a Ghana field-operation "
                    "comparison; its maize task estimate is lower than the listed "
                    "cowpea and groundnut totals, but it is not farm-specific."
                ),
            ),
        },
        source_note=(
            "Representative maturity range and relative traits are desk "
            "evidence; no field-specific validation."
        ),
    ),
    dict(
        crop_key="cowpea",
        group="Legume",
        aliases=("cow pea", "nyemba"),
        water_resilience="Medium",
        soil_effect="Adds nitrogen",
        maturity_days_min=62,
        maturity_days_max=72,
        growth_speed="Fast",
        labour="Medium",
        parameter_evidence={
            "water_resilience": dict(
                urls=(
                    "https://cspace.csirgh.com/items/show/1466",
                    "https://ugspace.ug.edu.gh/items/6ca7b2cc-9533-4d3b-9922-cf4589f3a914",
                ),
                kind="desk_synthesis",
                confidence="low",
                note=(
                    "Ghana evidence indicates variety- and environment-dependent "
                    "drought response; Medium is a cautious provisional class, not a "
                    "measured threshold."
                ),
            ),
            "soil_effect": dict(
                urls=(
                    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5946709/",
                    "https://pure.ug.edu.gh/en/publications/evaluating-sustainable-and-profitable-cropping-sequences-with-cas-2/",
                ),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Ghana trials document N fixation and sequence effects. "
                    "Adds-nitrogen assumes residues/biomass are retained; harvested "
                    "grain alone does not guarantee a net soil benefit."
                ),
            ),
            "maturity": dict(
                urls=(CSIR_VARIETIES,),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Representative transition-zone CSIR entries CRI-Nketewade, "
                    "CRI-Zamzam and related varieties report approximately 62–72 "
                    "days."
                ),
            ),
            "growth_speed": dict(
                urls=(CSIR_VARIETIES,),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Derived from the representative maturity range using the "
                    "configured 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=("https://pmc.ncbi.nlm.nih.gov/articles/PMC5614088/",),
                kind="direct_source",
                confidence="low",
                note=(
                    "A Ghana field-operation estimate places cowpea between the "
                    "study's maize and groundnut examples; plot size, mechanization, "
                    "and harvest practice vary."
                ),
            ),
        },
        source_note=(
            "Legume soil effect is conditional on biological fixation, "
            "biomass and residue management."
        ),
    ),
    dict(
        crop_key="groundnut",
        group="Legume",
        aliases=("peanut", "groundnuts"),
        water_resilience="High",
        soil_effect="Adds nitrogen",
        maturity_days_min=90,
        maturity_days_max=95,
        growth_speed="Medium",
        labour="High",
        parameter_evidence={
            "water_resilience": dict(
                urls=(FAO_WATER, CSIR_VARIETIES),
                kind="direct_source",
                confidence="low",
                note=(
                    "FAO reports low-to-medium drought sensitivity; CSIR lists "
                    "drought-tolerant varieties. High is a provisional crop-level "
                    "synthesis, not local performance evidence."
                ),
            ),
            "soil_effect": dict(
                urls=(
                    "https://pmc.ncbi.nlm.nih.gov/articles/PMC5946709/",
                    "https://journals.ug.edu.gh/index.php/wajae/article/view/799",
                ),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Ghana trials document N fixation and residue-linked rotation "
                    "effects. Adds-nitrogen assumes biomass/residues remain; the "
                    "label is not a measured farm soil result."
                ),
            ),
            "maturity": dict(
                urls=(CSIR_VARIETIES,),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Crops nkatie/Agbeyeye are listed at approximately 90–95 days in "
                    "the forest–savanna transition; catalog zero-day rows were "
                    "rejected."
                ),
            ),
            "growth_speed": dict(
                urls=(CSIR_VARIETIES,),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Derived from the representative maturity range using the "
                    "configured 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=("https://pmc.ncbi.nlm.nih.gov/articles/PMC5614088/",),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "The cited Ghana study estimated more operation labour for "
                    "groundnut than its maize/cowpea examples, including harvest and "
                    "shelling; not a farm-specific requirement."
                ),
            ),
        },
        source_note=(
            "Relative traits are sourced desk evidence; management and local "
            "validation remain open."
        ),
    ),
    dict(
        crop_key="cassava",
        group="Root/tuber",
        aliases=("manioc", "bankye"),
        water_resilience="Medium",
        soil_effect="Draws down",
        maturity_days_min=365,
        maturity_days_max=458,
        growth_speed="Slow",
        labour="High",
        parameter_evidence={
            "water_resilience": dict(
                urls=(FAO_CASSAVA,),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Cassava tolerates dry spells after establishment but is "
                    "sensitive during early establishment; Medium represents that "
                    "mixed response and not a plot water balance."
                ),
            ),
            "soil_effect": dict(
                urls=(
                    "https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2023.1095207/full",
                    "https://www.fao.org/4/y2413e/y2413e08.htm",
                ),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Ghana research describes nutrient removal, especially potassium, "
                    "and long-term soil effects that depend on yield, erosion, "
                    "fertilizer and residue return."
                ),
            ),
            "maturity": dict(
                urls=(CSIR_VARIETIES,),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "The CSIR catalog reports 365–458 days for several Ghana "
                    "varieties in the transition zone; harvest timing remains "
                    "variety- and use-dependent."
                ),
            ),
            "growth_speed": dict(
                urls=(CSIR_VARIETIES,),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Derived from the representative maturity range using the "
                    "configurable 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=("https://www.fao.org/4/a0154e/A0154E02.htm",),
                kind="direct_source",
                confidence="low",
                note=(
                    "FAO's Ghana subsector review notes cassava harvest labour per "
                    "hectare is comparatively high; actual effort depends on soil and "
                    "harvesting method."
                ),
            ),
        },
        source_note=(
            "The maturity and labour values indicate long occupancy/relative "
            "effort, not an exact farm schedule."
        ),
    ),
    dict(
        crop_key="yam",
        group="Root/tuber",
        aliases=("white yam", "water yam"),
        water_resilience="Low",
        soil_effect="Draws down",
        maturity_days_min=180,
        maturity_days_max=300,
        growth_speed="Slow",
        labour="High",
        parameter_evidence={
            "water_resilience": dict(
                urls=("https://doi.org/10.5772/intechopen.106504",),
                kind="direct_source",
                confidence="low",
                note=(
                    "West African yam literature describes need for sufficiently "
                    "distributed moisture; Low is a cautious transfer estimate, not a "
                    "local cultivar response."
                ),
            ),
            "soil_effect": dict(
                urls=(
                    "https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2023.1095207/full",
                ),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "No comparable Ejura yam nutrient-balance value was found; "
                    "draws-down is an explicit root/tuber nutrient-removal analogy to "
                    "cassava and must be locally reviewed."
                ),
            ),
            "maturity": dict(
                urls=(
                    "https://ecocrop.apps.fao.org/ecocrop/srv/en/cropView?id=942",
                    "https://pmc.ncbi.nlm.nih.gov/articles/PMC10008982/",
                ),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "180–300 days is a D. rotundata reference range; generic yam "
                    "contains multiple species and local harvest periods vary. It is "
                    "an explicit estimate for MVP scheduling."
                ),
            ),
            "growth_speed": dict(
                urls=("https://ecocrop.apps.fao.org/ecocrop/srv/en/cropView?id=942",),
                kind="desk_synthesis",
                confidence="low",
                note=(
                    "Derived from the representative maturity range using the "
                    "configurable 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=(
                    "https://www.fao.org/4/y4383e/y4383e0g.htm",
                    "https://pmc.ncbi.nlm.nih.gov/articles/PMC10008982/",
                ),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "High is an operations-based estimate from mound preparation, "
                    "planting and harvesting practices described in Ghana sources; no "
                    "local person-day comparison was found."
                ),
            ),
        },
        source_note=(
            "Yam values are explicitly provisional and partly analogous; "
            "species/variety specificity is needed."
        ),
    ),
    dict(
        crop_key="rice-upland",
        group="Cereal",
        aliases=("upland rice",),
        water_resilience="Medium",
        soil_effect="Draws down",
        maturity_days_min=95,
        maturity_days_max=100,
        growth_speed="Medium",
        labour="High",
        parameter_evidence={
            "water_resilience": dict(
                urls=(
                    CSIR_VARIETIES,
                    "https://cropsresearch.org/2022/11/csir-crops-research-institute-outdoors-nine-new-rice-varieties/",
                ),
                kind="direct_source",
                confidence="low",
                note=(
                    "Upland NERICA varieties include drought-tolerant entries; the "
                    "class is provisional and applies only to the upland production "
                    "system."
                ),
            ),
            "soil_effect": dict(
                urls=("https://www.jstage.jst.go.jp/article/jsta/60/2/60_119/_article/-char/en",),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "Lowland/continuous rice studies report soil fertility "
                    "constraints; this drawdown proxy is not specific to upland rice "
                    "or residue practice."
                ),
            ),
            "maturity": dict(
                urls=(MOFA_RICE,),
                kind="direct_source",
                confidence="moderate",
                note="NERICA 2 is listed for upland ecology at about 95–100 days.",
            ),
            "growth_speed": dict(
                urls=(MOFA_RICE,),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Derived from the representative maturity range using the "
                    "configurable 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=(MOFA_RICE,),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "High relative effort is estimated from the guide's land "
                    "preparation, repeated weed-control, and harvest operations; farm "
                    "labour has not been measured."
                ),
            ),
        },
        source_note=(
            "Upland-specific candidate profile; not transferable to either lowland rice system."
        ),
    ),
    dict(
        crop_key="rice-rain-fed-lowland",
        group="Cereal",
        aliases=("rainfed lowland rice",),
        water_resilience="Low",
        soil_effect="Draws down",
        maturity_days_min=115,
        maturity_days_max=120,
        growth_speed="Medium",
        labour="High",
        parameter_evidence={
            "water_resilience": dict(
                urls=(FAO_WATER, MOFA_RICE),
                kind="direct_source",
                confidence="low",
                note=(
                    "Paddy rice has high water demand and lowland rainfall/water "
                    "regime varies; Low is a provisional class, not a field water "
                    "requirement."
                ),
            ),
            "soil_effect": dict(
                urls=("https://www.jstage.jst.go.jp/article/jsta/60/2/60_119/_article/-char/en",),
                kind="direct_source",
                confidence="low",
                note=(
                    "Ghana lowland-rice literature identifies fertility constraints; "
                    "the proxy depends on organic matter and fertilizer management."
                ),
            ),
            "maturity": dict(
                urls=(CSIR_VARIETIES,),
                kind="direct_source",
                confidence="moderate",
                note="CSIR-Gbewaa is listed for lowland ecology at about 115–120 days.",
            ),
            "growth_speed": dict(
                urls=(CSIR_VARIETIES,),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Derived from the representative maturity range using the "
                    "configurable 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=(MOFA_RICE,),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "High relative effort estimate reflects bunding, land "
                    "preparation, weed and water management, and harvest operations; "
                    "not a measured per-farm need."
                ),
            ),
        },
        source_note="Rain-fed lowland profile; no supported pilot crop calendar is yet available.",
    ),
    dict(
        crop_key="rice-irrigated",
        group="Cereal",
        aliases=("irrigated rice",),
        water_resilience="Low",
        soil_effect="Draws down",
        maturity_days_min=110,
        maturity_days_max=115,
        growth_speed="Medium",
        labour="High",
        parameter_evidence={
            "water_resilience": dict(
                urls=(FAO_WATER, MOFA_RICE),
                kind="direct_source",
                confidence="low",
                note=(
                    "Irrigation may manage water supply, but the crop's high paddy "
                    "water demand remains; this is not a claim that a farmer has "
                    "sufficient water."
                ),
            ),
            "soil_effect": dict(
                urls=(
                    "https://www.ug.edu.gh/research/publications/integrated-organic-inorganic-fertilizer-management-rice-production-vertisols-accra-plains-ghana",
                ),
                kind="desk_synthesis",
                confidence="low",
                note=(
                    "Ghana continuous-rice findings show management-related soil "
                    "fertility risks; no universal crop-only effect was measured."
                ),
            ),
            "maturity": dict(
                urls=(MOFA_RICE,),
                kind="direct_source",
                confidence="moderate",
                note=(
                    "Jasmine 85/Gbewaa is listed for lowland and irrigated ecology at "
                    "about 110–115 days."
                ),
            ),
            "growth_speed": dict(
                urls=(MOFA_RICE,),
                kind="desk_synthesis",
                confidence="moderate",
                note=(
                    "Derived from the representative maturity range using the "
                    "configurable 75/150-day cutoffs."
                ),
            ),
            "labour": dict(
                urls=(MOFA_RICE,),
                kind="analogue_estimate",
                confidence="low",
                note=(
                    "High relative effort estimate reflects land preparation, water "
                    "operations and repeated crop care; mechanization and water "
                    "delivery differ by farm."
                ),
            ),
        },
        source_note=(
            "Irrigated rice is a distinct profile; farm access is not "
            "inferred from the crop's production system."
        ),
    ),
)
