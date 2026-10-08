"""Personal auto wording for the synthetic book. Same shape as forms_home."""

PP1 = ("PP 00 01", "06 98", "Personal Auto Policy", "base", 14)
RENTAL = ("PP 03 06", "06 98", "Extended Transportation Expenses", "endorsement", 1)
TX_AMEND = ("PP 01 89", "12 15", "Texas Amendment Of Policy Provisions", "amendatory", 4)

FORMS = [PP1, RENTAL, TX_AMEND]

CLAUSES = [
    (
        PP1, 2, "Part A – Liability Coverage", "Insuring Agreement",
        "coverage", "PALiabilityCov",
        ["liability", "at fault", "other driver", "damage i cause", "injury i cause"],
        "We will pay damages for bodily injury or property damage for which any insured becomes "
        "legally responsible because of an auto accident. We will settle or defend, as we consider "
        "appropriate, any claim or suit asking for these damages.",
        "If you are legally responsible for injuring someone or damaging their property in a car "
        "accident, this part pays what you owe them, up to your liability limit, and pays for your "
        "defence.",
    ),
    (
        PP1, 3, "Part A – Liability Coverage", "Exclusions – Public Or Livery Conveyance",
        "exclusion", "PALiabilityCov",
        ["uber", "lyft", "rideshare", "delivery", "livery", "passengers for money"],
        "We do not provide Liability Coverage for any insured: 5. For that insured's liability "
        "arising out of the ownership or operation of a vehicle while it is being used as a public "
        "or livery conveyance. This exclusion does not apply to a share-the-expense car pool.",
        "Driving for money — carrying paying passengers or making deliveries for a service — is not "
        "covered by the standard policy. Sharing the cost of a journey with someone you were "
        "driving anyway is fine.",
    ),
    (
        PP1, 7, "Part C – Uninsured Motorists Coverage", "Insuring Agreement",
        "coverage", "PAUninsuredMotoristsCov",
        ["uninsured", "hit and run", "no insurance", "underinsured"],
        "We will pay compensatory damages which an insured is legally entitled to recover from the "
        "owner or operator of an uninsured motor vehicle because of bodily injury sustained by an "
        "insured and caused by an accident.",
        "If someone with no insurance, or not enough insurance, injures you, this part pays what "
        "they should have paid, up to your uninsured motorists limit.",
    ),
    (
        PP1, 9, "Part D – Coverage For Damage To Your Auto", "Insuring Agreement",
        "coverage", "PACollisionCov",
        ["collision", "crash", "hit", "repair my car", "damage to my car"],
        "We will pay for direct and accidental loss to your covered auto or any non-owned auto, "
        "including its equipment, minus any applicable deductible shown in the Declarations. "
        "Collision means the upset of your covered auto or its impact with another vehicle or "
        "object.",
        "This pays to repair or replace your own car after a crash, minus your collision "
        "deductible. Collision means your car hit something or turned over.",
    ),
    (
        PP1, 9, "Part D – Coverage For Damage To Your Auto", "Other Than Collision",
        "coverage", "PAComprehensiveCov",
        ["comprehensive", "theft", "stolen", "hail", "glass", "windshield", "animal", "fire", "vandalism"],
        "Loss caused by the following is considered other than collision: missiles or falling "
        "objects; fire; theft or larceny; explosion or earthquake; windstorm; hail, water or flood; "
        "malicious mischief or vandalism; riot or civil commotion; contact with bird or animal; or "
        "breakage of glass.",
        "Damage that is not a crash — theft, fire, hail, a cracked windscreen, hitting a deer, "
        "vandalism, flood — falls under comprehensive, and your comprehensive deductible applies.",
    ),
    (
        PP1, 10, "Part D – Coverage For Damage To Your Auto", "Transportation Expenses",
        "coverage", "PARentalCov",
        ["rental car", "hire car", "courtesy car", "while my car is repaired", "transportation"],
        "We will pay, without application of a deductible, up to a maximum of $600, for "
        "transportation expenses incurred by you in the event of a loss to your covered auto. "
        "Payment begins 48 hours after the loss for a theft, and 24 hours after the loss for any "
        "other covered loss. We will pay only expenses incurred during the period beginning after "
        "the loss and ending when your covered auto is returned to use or we pay for its loss.",
        "While your car is off the road after a covered loss, the policy pays towards a hire car "
        "and other travel, up to $600 in total. It starts 24 hours after the loss, or 48 hours "
        "after a theft, and stops when your car is back or paid for.",
    ),
    (
        RENTAL, 1, "Coverage", "Extended Transportation Expenses",
        "endorsement", "PARentalCov",
        ["rental reimbursement", "rental car", "extended", "daily limit"],
        "The limit shown in the Schedule replaces the $600 maximum for transportation expenses in "
        "Part D. We will pay up to the daily amount shown, for no more than the maximum number of "
        "days shown in the Schedule.",
        "If you bought this endorsement, your hire-car cover is the daily amount and number of days "
        "shown on your declarations page instead of the standard $600 total.",
    ),
    (
        TX_AMEND, 2, "Amendments", "Texas – Prompt Payment Of Claims",
        "condition", "",
        ["texas", "how long", "deadline", "payment", "prompt"],
        "In Texas, we will notify you in writing of the acceptance or rejection of a claim not "
        "later than the 15th business day after we receive all items, statements and forms "
        "required to secure final proof of loss.",
        "In Texas, once we have everything we asked for, we must tell you in writing whether the "
        "claim is accepted or rejected within 15 business days.",
    ),
    (
        PP1, 1, "Product guide", "Personal auto product guide – deductibles",
        "definition", "",
        ["deductible", "guidance", "product"],
        "General product guidance: collision and other-than-collision each carry their own "
        "deductible, shown separately on the declarations page. Liability coverage has no "
        "deductible.",
        "Your car's own damage cover has deductibles — one for crashes, one for everything else. "
        "Liability cover, which pays other people, has no deductible.",
    ),
]
