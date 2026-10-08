"""The rest of the homeowners jacket.

A real HO-3 with endorsements runs forty to seventy pages. Ours ran two,
and retrieval that finds the right clause in two pages has proved almost
nothing — the depth of the document *is* the test.

These are the parts that were missing and that coverage questions
actually turn on: the definitions, the perils, the exclusions, and — most
of all — the **exceptions to the exclusions**, which is where the right
answer usually hides. "Water damage is excluded" is the wrong answer to
"is my sewer back-up covered" precisely because of the exception three
lines further down.

Written for the demo in the register real ISO forms use. Nothing here is
a filed form and every page says so.
"""

from data_seed.sources.forms_home import BACKUP, HO3, SCHEDULED, TX_AMEND, WIND

# form, page, section, heading, clause_type, pattern_code, keywords, text, plain
LONG_CLAUSES = [
    # ── Definitions ──
    (
        HO3, 1, "Definitions", "\"Bodily injury\"", "definition", "",
        ["bodily injury", "hurt", "sickness", "disease", "injury"],
        "\"Bodily injury\" means bodily harm, sickness or disease, including required care, loss "
        "of services and death that results.",
        "Bodily injury means someone was physically hurt or made ill — including what it costs "
        "to care for them, and death if it comes to that.",
    ),
    (
        HO3, 1, "Definitions", "\"Occurrence\"", "definition", "",
        ["occurrence", "accident", "one event", "how many claims"],
        "\"Occurrence\" means an accident, including continuous or repeated exposure to "
        "substantially the same general harmful conditions, which results, during the policy "
        "period, in bodily injury or property damage.",
        "An occurrence is one accident. Damage that keeps happening from the same cause counts "
        "as one occurrence, not several — which matters, because the limit applies per "
        "occurrence.",
    ),
    (
        HO3, 2, "Definitions", "\"Residence premises\"", "definition", "",
        ["residence premises", "where I live", "my address", "the home"],
        "\"Residence premises\" means the one family dwelling where you reside, the part of any "
        "other building where you reside, and which is shown as the residence premises in the "
        "Declarations.",
        "The residence premises is the home on your declarations page that you actually live in. "
        "A property you own but do not live in is not covered by this policy.",
    ),
    (
        HO3, 2, "Definitions", "\"Business\"", "definition", "",
        ["business", "trade", "side job", "work from home", "airbnb", "rental"],
        "\"Business\" means a trade, profession or occupation engaged in on a full-time, "
        "part-time or occasional basis, or any other activity engaged in for money or other "
        "compensation, except one from which the total compensation received during the twelve "
        "months before the policy period was less than $2,000.",
        "Business means anything you do for money, full-time or occasional. Earning under $2,000 "
        "in the year before the policy started does not count — above that it does, and business "
        "activity changes what is covered.",
    ),

    # ── Section I additional coverages ──
    (
        HO3, 6, "Section I – Property Coverages", "Coverage D – Loss Of Use",
        "coverage", "HOLossOfUseCov",
        ["loss of use", "hotel", "somewhere to stay", "additional living expense", "rent"],
        "If a loss covered under Section I makes that part of the residence premises where you "
        "reside not fit to live in, we cover the Additional Living Expense, meaning any necessary "
        "increase in living expenses incurred by you so that your household can maintain its "
        "normal standard of living. Payment will be for the shortest time required to repair or "
        "replace the damage or, if you permanently relocate, the shortest time required for your "
        "household to settle elsewhere.",
        "If a covered loss makes your home unfit to live in, we pay the extra cost of living "
        "somewhere else — the difference, not the whole bill. It runs for as long as the repair "
        "reasonably takes, not indefinitely.",
    ),
    (
        HO3, 8, "Section I – Additional Coverages", "Debris Removal",
        "additional", "",
        ["debris", "clear up", "removal", "tree down", "rubble"],
        "We will pay your reasonable expense for the removal of debris of covered property if a "
        "Peril Insured Against causes the loss. This expense is included in the limit of "
        "liability that applies to the damaged property. If the amount to be paid for the actual "
        "damage plus the debris removal expense is more than the limit, an additional 5% of that "
        "limit is available for debris removal expense.",
        "Clearing up after a covered loss is included in the same limit — with a further 5% "
        "available if the damage plus the clear-up goes over it.",
    ),
    (
        HO3, 9, "Section I – Additional Coverages", "Reasonable Repairs",
        "additional", "",
        ["emergency repair", "board up", "tarp", "stop further damage", "temporary"],
        "In the event that covered property is damaged by an applicable Peril Insured Against, we "
        "will pay the reasonable cost incurred by you for necessary measures taken solely to "
        "protect that property from further damage.",
        "If you spend money stopping a covered loss getting worse — boarding up a window, "
        "tarping a roof — we pay that. Keep the receipt.",
    ),

    # ── Perils ──
    (
        HO3, 11, "Section I – Perils Insured Against", "Coverage A and B – Open Perils",
        "peril", "",
        ["what is covered", "perils", "open perils", "all risk", "special form"],
        "We insure against risk of direct physical loss to property described in Coverages A and "
        "B. We do not insure, however, for loss excluded under Section I – Exclusions or "
        "otherwise excluded in this Section.",
        "The house and other structures are covered against anything that physically damages "
        "them, unless the policy specifically excludes it. That is what a Special Form means — "
        "the exclusions do the work, not a list of covered causes.",
    ),
    (
        HO3, 13, "Section I – Perils Insured Against", "Coverage C – Named Perils",
        "peril", "",
        ["belongings", "personal property", "named perils", "what damages are covered"],
        "We insure for direct physical loss to the property described in Coverage C caused by a "
        "peril listed below, unless the loss is excluded in Section I – Exclusions: fire or "
        "lightning; windstorm or hail; explosion; riot or civil commotion; aircraft; vehicles; "
        "smoke; vandalism or malicious mischief; theft; falling objects; weight of ice, snow or "
        "sleet; accidental discharge or overflow of water or steam; sudden and accidental tearing "
        "apart of a heating or air conditioning system; freezing; and sudden and accidental damage "
        "from artificially generated electrical current.",
        "Your belongings are covered against a specific list of causes rather than everything. "
        "If the cause is not on the list, Coverage C does not respond — this is different from "
        "the house itself.",
    ),

    # ── Exclusions, and the exceptions that matter ──
    (
        HO3, 15, "Section I – Exclusions", "Water Damage",
        "exclusion", "",
        ["flood", "water", "sewer", "drain", "sump", "backup", "surface water", "groundwater"],
        "We do not insure for loss caused directly or indirectly by Water Damage, meaning: "
        "a. Flood, surface water, waves, tidal water, overflow of a body of water, or spray from "
        "any of these, whether or not driven by wind; "
        "b. Water which backs up through sewers or drains or which overflows from a sump; or "
        "c. Water below the surface of the ground, including water which exerts pressure on or "
        "seeps or leaks through a building, sidewalk, driveway, foundation, swimming pool or "
        "other structure. "
        "Direct loss by fire, explosion or theft resulting from water damage is covered.",
        "Water that comes from outside the home is not covered by the base policy: flood, surface "
        "water, water backing up through a sewer or drain, water overflowing a sump, and water "
        "coming up from under the ground. If that water then causes a fire, explosion or theft, "
        "that part is covered. An endorsement can add back the sewer and sump part.",
    ),
    (
        HO3, 16, "Section I – Exclusions", "Earth Movement",
        "exclusion", "",
        ["earthquake", "landslide", "sinkhole", "subsidence", "ground moving", "mine"],
        "We do not insure for loss caused directly or indirectly by Earth Movement, meaning "
        "earthquake including land shock waves or tremors before, during or after a volcanic "
        "eruption; landslide; mudslide; mudflow; subsidence; sinkhole; or any other earth "
        "movement including earth sinking, rising or shifting. Direct loss by fire, explosion or "
        "theft resulting from earth movement is covered.",
        "The ground moving is not covered — earthquakes, landslides, sinkholes and subsidence. "
        "Earthquake cover is bought separately. If the ground movement starts a fire, the fire "
        "damage is covered.",
    ),
    (
        HO3, 17, "Section I – Exclusions", "Neglect",
        "exclusion", "",
        ["neglect", "did not maintain", "failed to protect", "left it"],
        "We do not insure for loss caused by neglect, meaning your neglect to use all reasonable "
        "means to save and preserve property at and after the time of a loss.",
        "If you could reasonably have stopped the damage getting worse and did not, that part is "
        "not covered.",
    ),
    (
        HO3, 18, "Section I – Exclusions", "Wear and Tear, Deterioration",
        "exclusion", "",
        ["wear and tear", "old", "deterioration", "rust", "rot", "gradual", "maintenance"],
        "We do not insure for loss to property described in Coverages A and B caused by wear and "
        "tear, marring, deterioration; inherent vice, latent defect, mechanical breakdown; smog, "
        "rust or other corrosion; smoke from agricultural smudging or industrial operations; "
        "settling, shrinking, bulging or expansion of pavements, patios, foundations, walls, "
        "floors, roofs or ceilings; or birds, vermin, rodents or insects. If any of these cause "
        "water to escape from a plumbing, heating or air conditioning system, we cover the loss "
        "caused by that water.",
        "The policy pays for sudden accidents, not for things wearing out. Rust, rot, settling, "
        "vermin and mechanical breakdown are maintenance. But if one of them makes a pipe leak, "
        "the water damage from that leak is covered.",
    ),
    (
        HO3, 19, "Section I – Exclusions", "Mold, Fungus or Wet Rot",
        "exclusion", "",
        ["mold", "mould", "fungus", "damp", "wet rot", "mildew"],
        "We do not insure for loss caused by mold, fungus or wet rot. This exclusion does not "
        "apply when mold, fungus or wet rot is hidden within the walls or ceilings or beneath the "
        "floors or above the ceilings of a structure and results from the accidental discharge or "
        "overflow of water or steam from a plumbing system. In that event the most we will pay is "
        "$10,000 for the total of all loss during the policy period.",
        "Mould and rot are generally not covered. The exception is mould hidden inside the "
        "structure caused by a plumbing leak — and there the most we pay is $10,000 for the whole "
        "policy year, however many claims you make.",
    ),
    (
        HO3, 20, "Section I – Exclusions", "Ordinance or Law",
        "exclusion", "",
        ["building code", "ordinance", "upgrade", "code compliance", "permit"],
        "We do not insure for loss resulting from the enforcement of any ordinance or law "
        "regulating the construction, repair or demolition of a building or other structure, "
        "unless specifically provided under this policy.",
        "If the building code has changed since your home was built, the cost of bringing it up "
        "to current code is not covered unless you bought that cover separately. We pay to put it "
        "back as it was.",
    ),

    # ── Section I conditions ──
    (
        HO3, 22, "Section I – Conditions", "Your Duties After Loss",
        "condition", "",
        ["what do i do", "report", "duties", "proof of loss", "deadline", "notify"],
        "In case of a loss to covered property, you must see that the following are done: give "
        "prompt notice to us or our agent; notify the police in case of loss by theft; protect the "
        "property from further damage; prepare an inventory of damaged personal property; and, "
        "within 60 days after our request, send to us your signed, sworn proof of loss.",
        "After a loss: tell us promptly, call the police if anything was stolen, stop it getting "
        "worse, list what was damaged, and send us a signed proof of loss within 60 days of us "
        "asking.",
    ),
    (
        HO3, 23, "Section I – Conditions", "Loss Settlement",
        "condition", "",
        ["how much will you pay", "replacement cost", "actual cash value", "depreciation"],
        "Covered property losses are settled as follows: personal property and structures that "
        "are not buildings at actual cash value at the time of loss but not more than the amount "
        "required to repair or replace; buildings under Coverage A or B at replacement cost "
        "without deduction for depreciation, provided that at the time of loss the amount of "
        "insurance is 80% or more of the full replacement cost of the building immediately before "
        "the loss.",
        "The building is paid at what it costs to rebuild, provided you insured it for at least "
        "80% of that. Your belongings are paid at what they were worth at the time — their age "
        "comes off — unless you bought replacement cost cover for them.",
    ),
    (
        HO3, 24, "Section I – Conditions", "Appraisal",
        "condition", "",
        ["disagree", "dispute", "appraisal", "how much it is worth", "second opinion"],
        "If you and we fail to agree on the amount of loss, either may demand an appraisal of the "
        "loss. In this event, each party will choose a competent and impartial appraiser within "
        "20 days after receiving a written request from the other. The two appraisers will choose "
        "an umpire. A decision agreed to by any two will set the amount of loss.",
        "If we cannot agree on how much the damage is worth, either of us can ask for an "
        "appraisal. You pick an appraiser, we pick one, and they pick an umpire. Two of the three "
        "agreeing settles the amount.",
    ),
    (
        HO3, 25, "Section I – Conditions", "Suit Against Us",
        "condition", "",
        ["sue", "time limit", "deadline to sue", "legal action", "statute"],
        "No action can be brought against us unless there has been full compliance with all of "
        "the terms under Section I of this policy and the action is started within two years "
        "after the date of loss.",
        "If you want to take us to court over a claim, you have two years from the date of the "
        "loss, and you must have done what the policy asks of you first.",
    ),

    # ── Section II ──
    (
        HO3, 27, "Section II – Liability Coverages", "Coverage E – Personal Liability",
        "coverage", "HOPersonalLiabilityCov",
        ["liability", "sued", "someone hurt", "my fault", "damage to others"],
        "If a claim is made or a suit is brought against an insured for damages because of bodily "
        "injury or property damage caused by an occurrence to which this coverage applies, we "
        "will pay up to our limit of liability for the damages for which an insured is legally "
        "liable, and provide a defense at our expense by counsel of our choice, even if the suit "
        "is groundless, false or fraudulent.",
        "If someone is hurt or their property is damaged and you are legally responsible, we pay "
        "what you owe up to your limit — and we pay for a lawyer, even if the claim turns out to "
        "be nonsense.",
    ),
    (
        HO3, 28, "Section II – Liability Coverages", "Coverage F – Medical Payments To Others",
        "coverage", "HOMedPayCov",
        ["medical payments", "someone hurt at my house", "guest injured", "no fault"],
        "We will pay the necessary medical expenses that are incurred or medically ascertained "
        "within three years from the date of an accident causing bodily injury. This coverage "
        "does not apply to you or regular residents of your household.",
        "If a visitor is hurt at your home we pay their medical bills up to the Coverage F limit, "
        "whether or not it was your fault. It does not cover you or the people who live with you.",
    ),
    (
        HO3, 30, "Section II – Exclusions", "Business Activities",
        "exclusion", "",
        ["business", "work from home", "customer injured", "clients", "side job"],
        "Coverage E and Coverage F do not apply to bodily injury or property damage arising out "
        "of or in connection with a business conducted from an insured location or engaged in by "
        "an insured, whether or not the business is owned or operated by an insured or employs an "
        "insured. This exclusion does not apply to the rental of an insured location on an "
        "occasional basis for use only as a residence.",
        "Anything arising from a business is not covered by the liability part of this policy. "
        "Renting your home out occasionally as somewhere to live is the exception.",
    ),
    (
        HO3, 31, "Section II – Exclusions", "Motor Vehicle Liability",
        "exclusion", "",
        ["car", "vehicle", "driving", "auto", "motor"],
        "Coverage E and Coverage F do not apply to bodily injury or property damage arising out "
        "of the ownership, maintenance, occupancy, operation, use, loading or unloading of motor "
        "vehicles. This exclusion does not apply to a motor vehicle which is not subject to motor "
        "vehicle registration and is used solely to service an insured's residence, or designed "
        "to assist the handicapped.",
        "Anything involving a car is the car policy's business, not this one. A ride-on mower "
        "used only around your own home, or a mobility vehicle, is the exception.",
    ),

    # ── Endorsements, in proper depth ──
    (
        BACKUP, 1, "Water Back-Up and Sump Discharge or Overflow", "What is added",
        "coverage", "HOWaterBackupCov",
        ["sewer", "drain", "backup", "back up", "sump", "basement flooded"],
        "We insure, up to the limit shown in the Declarations for this endorsement, for direct "
        "physical loss to property covered under Section I caused by water, or waterborne "
        "material, which backs up through sewers or drains, or which overflows or is discharged "
        "from a sump, sump pump or related equipment, even if such overflow or discharge results "
        "from mechanical breakdown. The Water Damage exclusion in Section I – Exclusions does not "
        "apply to loss covered by this endorsement.",
        "This adds back the sewer and sump part of the water exclusion. If water backs up through "
        "a sewer or a drain, or overflows from your sump pump, it is covered up to the limit shown "
        "for this endorsement — including when the pump simply failed.",
    ),
    (
        BACKUP, 2, "Water Back-Up and Sump Discharge or Overflow", "What is still excluded",
        "exclusion", "",
        ["still not covered", "flood", "exclusion", "limits of this endorsement"],
        "This endorsement does not cover loss caused by flood, surface water, waves, tidal water, "
        "overflow of a body of water, or spray from any of these, whether or not driven by wind. "
        "It does not cover loss resulting from your failure to keep the sump pump or related "
        "equipment in proper working condition, or from the failure of any part of a system you "
        "knew to be defective.",
        "It does not turn this into flood cover. Water arriving from outside — a river, the sea, "
        "surface water after a storm — is still excluded, and so is damage from a pump you knew "
        "was broken and left.",
    ),
    (
        WIND, 1, "Windstorm or Hail Percentage Deductible", "How it is worked out",
        "condition", "HOWindDeductible",
        ["wind deductible", "hail deductible", "percentage", "hurricane", "storm"],
        "The Windstorm or Hail Deductible shown in the Declarations is a percentage of the "
        "Coverage A limit of liability. It applies to each loss caused by windstorm or hail and "
        "replaces any other deductible for that loss. It is calculated on the Coverage A limit in "
        "effect at the time of loss, not on the amount of the loss.",
        "For wind or hail, your deductible is a percentage of the Coverage A limit rather than a "
        "flat amount, and it replaces your normal deductible for that claim. It is worked out on "
        "the limit, not on how much the damage is.",
    ),
    (
        SCHEDULED, 1, "Scheduled Personal Property", "What a schedule does",
        "coverage", "HOScheduledCov",
        ["jewellery", "jewelry", "watch", "art", "scheduled", "valuables", "engagement ring"],
        "We cover the classes of personal property specifically listed in the Schedule for the "
        "amount shown. Coverage is against risk of direct physical loss, subject only to the "
        "exclusions stated in this endorsement. No deductible applies to loss to scheduled "
        "property. The special limits of liability under Coverage C do not apply to property "
        "specifically scheduled here.",
        "Anything on the schedule is covered for the amount shown against almost any cause, with "
        "no deductible — and the ordinary Coverage C caps on jewellery and similar items do not "
        "apply to it.",
    ),
    (
        TX_AMEND, 2, "Special Provisions – Texas", "Windstorm in a catastrophe area",
        "amendatory", "",
        ["texas", "coastal", "windstorm", "catastrophe area", "twia", "certificate"],
        "With respect to property located in a catastrophe area as designated by the Texas "
        "Department of Insurance, coverage for loss caused by windstorm or hail is excluded "
        "unless a certificate of compliance has been issued for the structure by the Texas "
        "Department of Insurance or the structure is otherwise eligible.",
        "On the Texas coast, wind and hail cover depends on the property having a certificate of "
        "compliance. Without one, wind damage is not covered by this policy.",
    ),
    (
        TX_AMEND, 4, "Special Provisions – Texas", "Prompt payment of claims",
        "amendatory", "",
        ["texas", "deadline", "how long", "prompt payment", "acknowledge", "statute"],
        "We will acknowledge receipt of a claim not later than the 15th day after we receive "
        "notice of the claim. We will notify you in writing of the acceptance or rejection of the "
        "claim not later than the 15th business day after we receive all items, statements and "
        "forms required. If we accept the claim, payment will be made not later than the 5th "
        "business day after notice of acceptance.",
        "In Texas we must acknowledge your claim within 15 days, tell you in writing whether it "
        "is accepted within 15 business days of getting everything we asked for, and pay within "
        "5 business days of accepting it.",
    ),
]
