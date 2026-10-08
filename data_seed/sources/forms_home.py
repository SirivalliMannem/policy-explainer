"""Homeowners wording for the synthetic book.

Written for the demo, in the register real ISO forms use, with the section,
page and edition a citation is made of. `plain` is the content owner's
approved reading-grade-8 rendering (PE-04) — approved once, not re-paraphrased
per question, which is how two customers end up with two explanations of the
same sentence.
"""

# form_number, edition, title, kind, page_count
HO3 = ("HO 00 03", "10 00", "Homeowners 3 – Special Form", "base", 22)
BACKUP = ("HO 04 95", "10 00", "Water Back-Up and Sump Discharge or Overflow", "endorsement", 2)
SCHEDULED = ("HO 04 61", "10 00", "Scheduled Personal Property", "endorsement", 3)
WIND = ("HO 03 12", "04 16", "Windstorm or Hail Percentage Deductible", "endorsement", 2)
TX_AMEND = ("HO 01 41", "07 15", "Special Provisions – Texas", "amendatory", 6)

FORMS = [HO3, BACKUP, SCHEDULED, WIND, TX_AMEND]

# form, page, section, heading, clause_type, pattern_code, keywords, text, plain
CLAUSES = [
    (
        HO3, 1, "Section I – Property Coverages", "Coverage A – Dwelling",
        "coverage", "HODwellingCov",
        ["dwelling", "house", "structure", "roof", "building"],
        "We cover: 1. The dwelling on the residence premises shown in the Declarations, including "
        "structures attached to the dwelling; and 2. Materials and supplies located on or next to "
        "the residence premises used to construct, alter or repair the dwelling or other structures "
        "on the residence premises.",
        "Coverage A is the house itself, including anything attached to it such as an attached "
        "garage or deck. The most we will pay for it is the Coverage A limit on your declarations "
        "page.",
    ),
    (
        HO3, 2, "Section I – Property Coverages", "Coverage C – Personal Property",
        "coverage", "HOPersonalPropertyCov",
        ["belongings", "contents", "personal property", "furniture", "clothes"],
        "We cover personal property owned or used by an insured while it is anywhere in the world. "
        "Our limit of liability for personal property usually located at an insured's residence, "
        "other than the residence premises, is 10% of the limit of liability for Coverage C, or "
        "$1,000, whichever is greater.",
        "Coverage C is your belongings — furniture, clothes, electronics — wherever they are in the "
        "world. Things kept at another home you own are covered for a smaller amount.",
    ),
    (
        HO3, 3, "Section I – Property Coverages", "Special Limits Of Liability",
        "limit", "HOPersonalPropertyCov",
        ["jewelry", "jewellery", "watches", "furs", "theft", "special limit", "silverware", "cash"],
        "Special limits of liability apply. These limits do not increase the Coverage C limit of "
        "liability. 3. $1,500 on watercraft. 6. $1,500 for loss by theft of jewelry, watches, "
        "furs, precious and semi-precious stones. 7. $2,500 for loss by theft of firearms. "
        "8. $2,500 for loss by theft of silverware, goldware and pewterware.",
        "Some kinds of property have their own, much lower limit when they are stolen. Jewellery, "
        "watches and furs are limited to $1,500 in total for a theft — not the full contents "
        "limit. Firearms and silverware are limited to $2,500 each.",
    ),
    (
        HO3, 4, "Section I – Property Coverages", "Coverage D – Loss Of Use",
        "coverage", "HOLossOfUseCov",
        ["hotel", "living expenses", "additional living expense", "somewhere to stay", "rent"],
        "If a loss covered under Section I makes that part of the residence premises where you "
        "reside not fit to live in, we cover the Additional Living Expense, meaning any necessary "
        "increase in living expenses incurred by you so that your household can maintain its normal "
        "standard of living.",
        "If a covered loss makes your home unliveable, we pay the extra cost of living somewhere "
        "else — a hotel or a rental, and the extra you spend on meals — so your household can carry "
        "on as normal while repairs happen.",
    ),
    (
        HO3, 7, "Section I – Perils Insured Against", "Accidental Discharge Or Overflow Of Water Or Steam",
        "coverage", "HODwellingCov",
        ["burst pipe", "leak", "plumbing", "overflow", "water heater", "discharge"],
        "We insure for direct physical loss caused by accidental discharge or overflow of water or "
        "steam from within a plumbing, heating, air conditioning or automatic fire protective "
        "sprinkler system or from within a household appliance. This peril does not include loss "
        "caused by or resulting from: constant or repeated seepage or leakage of water over a "
        "period of weeks, months or years.",
        "Water that suddenly escapes from a pipe, a water heater, an air conditioner or an "
        "appliance inside the home is an insured peril. A slow leak that has been going on for "
        "weeks or longer is not.",
    ),
    (
        HO3, 10, "Section I – Exclusions", "Water Damage",
        "exclusion", "HODwellingCov",
        ["flood", "sewer", "backup", "back-up", "drain", "sump", "surface water", "groundwater"],
        "We do not insure for loss caused directly or indirectly by Water Damage, meaning: "
        "a. Flood, surface water, waves, tidal water, overflow of a body of water, or spray from "
        "any of these, whether or not driven by wind; b. Water or water-borne material which backs "
        "up through sewers or drains or which overflows or is discharged from a sump, sump pump or "
        "related equipment; or c. Water or water-borne material below the surface of the ground.",
        "The base policy does not cover water that comes from outside the home: flood and surface "
        "water, water that backs up through sewers or drains, water discharged from a sump pump, "
        "and water that comes up from under the ground. An endorsement can add some of this back.",
    ),
    (
        HO3, 9, "Section I – Exclusions", "Earth Movement",
        "exclusion", "HODwellingCov",
        ["earthquake", "sinkhole", "landslide", "earth movement", "tremor"],
        "We do not insure for loss caused directly or indirectly by Earth Movement, meaning "
        "earthquake including land shock waves or tremors before, during or after a volcanic "
        "eruption; landslide; mudslide; mudflow; subsidence; sinkhole; or any other earth movement "
        "including earth sinking, rising or shifting.",
        "Earthquakes, landslides, sinkholes and any other movement of the ground are not covered by "
        "this policy. Earthquake cover is bought separately.",
    ),
    (
        HO3, 15, "Section I – Property Coverages", "Limited Fungi, Wet Or Dry Rot, Or Bacteria Coverage",
        "limit", "HODwellingCov",
        ["mold", "mould", "fungi", "rot", "bacteria", "damp"],
        "The most we will pay for loss or costs payable under this Additional Coverage is $10,000 "
        "in the aggregate during the policy period, regardless of the number of locations insured "
        "or the number of claims made.",
        "Mould and rot are covered only in a limited way, and only up to $10,000 for the whole "
        "policy year however many claims you make.",
    ),
    (
        HO3, 13, "Section I – Conditions", "Your Duties After Loss",
        "condition", "",
        ["what do i do", "report", "duties", "after a loss", "notify", "proof of loss"],
        "In case of a loss to covered property, you must see that the following are done: "
        "a. Give prompt notice to us or our agent; b. Notify the police in case of loss by theft; "
        "c. Protect the property from further damage; d. Cooperate with us in the investigation of "
        "a claim; e. Send to us, within 60 days after our request, your signed, sworn proof of loss.",
        "After any loss you must tell us promptly, call the police if something was stolen, stop "
        "further damage where you safely can, keep any damaged property so it can be looked at, and "
        "send us a signed proof of loss within 60 days of us asking.",
    ),
    # ── The endorsement that makes the demo question interesting ────────
    (
        BACKUP, 1, "Coverage", "Water Back-Up And Sump Discharge Or Overflow",
        "endorsement", "HOWaterBackupCov",
        ["sewer backup", "sewer back-up", "drain backup", "sump", "basement", "backs up"],
        "We insure, up to the limit shown in the Schedule, for direct physical loss, not caused by "
        "the negligence of an insured, to property covered under Section I caused by water, or "
        "water-borne material, which: 1. Backs up through sewers or drains; or 2. Overflows or is "
        "discharged from a sump, sump pump or related equipment, even if such overflow or discharge "
        "results from mechanical breakdown.",
        "This endorsement puts sewer and drain back-up back into your cover. If water backs up "
        "through a sewer or a drain, or overflows from your sump pump, the damage it does to your "
        "home and belongings is covered up to the limit shown on this endorsement.",
    ),
    (
        BACKUP, 2, "Limit and Deductible", "Limit Of Liability And Deductible",
        "limit", "HOWaterBackupCov",
        ["back-up limit", "backup deductible", "sewer backup limit", "sump limit"],
        "The limit of liability shown in the Schedule for this endorsement is the most we will pay "
        "in any one loss, regardless of the number of claims or the amount of loss. A separate "
        "deductible, as shown in the Schedule, applies to each loss under this endorsement. This "
        "coverage does not increase the limits of liability that apply to the property covered.",
        "There is a separate limit and a separate deductible for back-up losses, both shown on your "
        "declarations page. They do not add to your other limits.",
    ),
    (
        BACKUP, 2, "Exclusions", "What This Endorsement Does Not Cover",
        "exclusion", "HOWaterBackupCov",
        ["flood", "surface water", "storm surge", "rising water"],
        "This endorsement does not cover loss caused by flood, surface water, waves, tidal water, "
        "overflow of a body of water or spray from any of these, whether or not driven by wind. "
        "The Water Damage exclusion in the policy is otherwise unchanged.",
        "This endorsement covers back-up only. Water that arrives as a flood or as surface water "
        "from outside is still not covered; that needs separate flood insurance.",
    ),
    (
        SCHEDULED, 1, "Coverage", "Scheduled Personal Property",
        "endorsement", "HOScheduledPropertyCov",
        ["jewellery", "jewelry", "ring", "schedule", "appraisal", "valuable"],
        "We cover the classes of personal property described and for which a limit of liability is "
        "shown, for risks of direct physical loss, subject to the exclusions in this endorsement. "
        "Each item is insured for the amount shown in the Schedule and no deductible applies.",
        "Anything listed on this schedule — a named ring or watch, for example — is covered for its "
        "own listed amount, with no deductible, instead of falling under the $1,500 special theft "
        "limit for jewellery.",
    ),
    (
        WIND, 1, "Deductible", "Windstorm Or Hail Percentage Deductible",
        "limit", "HODwellingCov",
        ["wind", "hail", "hurricane", "storm", "deductible", "named storm"],
        "The windstorm or hail deductible shown in the Schedule is a percentage of the Coverage A "
        "limit of liability and applies to loss caused by windstorm or hail. This deductible "
        "replaces any other deductible for loss caused by the peril of windstorm or hail.",
        "Wind and hail damage has its own deductible, worked out as a percentage of your Coverage A "
        "limit rather than as a flat dollar amount. It replaces your normal deductible for that "
        "kind of damage, so it is usually larger.",
    ),
    (
        TX_AMEND, 3, "Special Provisions", "Texas – Appraisal And Notice Of Claim",
        "condition", "",
        ["texas", "appraisal", "dispute", "deadline", "notice"],
        "Paragraph F. Appraisal under Section I – Conditions is replaced by the following: If you "
        "and we fail to agree on the amount of loss, either party may make written demand for an "
        "appraisal. Each party will select a competent, independent appraiser within 20 days of "
        "receiving a written request from the other.",
        "In Texas, if you and the carrier cannot agree on how much a loss is worth, either side can "
        "ask for an appraisal. Both sides then pick their own appraiser within 20 days.",
    ),
    # ── Generic product wording, so the ranking has something to beat ───
    (
        HO3, 1, "Product guide", "Homeowners product guide – water losses",
        "definition", "",
        ["water", "guidance", "product"],
        "General product guidance: homeowners policies distinguish between water that escapes "
        "inside the home, water that backs up from sewers or drains, and water that arrives from "
        "outside as flood or surface water. Each is treated differently and the endorsements "
        "attached to the individual policy govern.",
        "In general, homeowners policies treat inside water, backed-up water and flood water as "
        "three different things. What your own policy says depends on the endorsements attached "
        "to it.",
    ),
]


# The rest of the jacket — definitions, perils, exclusions and the
# exceptions to them. Kept in its own module because it is long, appended
# here because it is the same wording and the seeder reads one list.
#
# Imported at the bottom to avoid a circular import: the long module
# names the form tuples defined above.
from data_seed.sources.forms_home_long import LONG_CLAUSES  # noqa: E402

CLAUSES = CLAUSES + LONG_CLAUSES
