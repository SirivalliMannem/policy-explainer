"""Messy-question benchmark: how employees actually type, and what each question must find.

Each retrieval case names the policy it is asked against and the evidence that must appear in the
top results; each name case names the policyholder or policy number that must be recognised.
Shared by the automated tests (rules only, deterministic) and the benchmark script (all modes).
"""

HOME = "HO-2847-1193"  # Margaret Chen, homeowners, current term
AUTO = "PA-5518-0042"  # Daniel Ortiz, personal auto, open claim

# (question, policy, expectation) — expectation keys: form, heading, title_contains, section
RETRIEVAL_CASES = [
    ("whats the deductable", HOME, {"title_contains": "Deductible"}),
    ("does it cover sewr backup", HOME, {"form": "HO 04 95", "heading": "Water Back-Up And Sump Discharge Or Overflow"}),
    ("is sewage backing up thru the drains coverd", HOME, {"form": "HO 04 95"}),
    ("my basement got flooded from the drain, am i covered", HOME, {"form": "HO 04 95"}),
    ("can i stay in a hotel while they fix the house", HOME, {"form": "HO 00 03", "heading": "Coverage D – Loss Of Use"}),
    ("where do they live if the house burns down and they cant stay there", HOME, {"form": "HO 00 03", "heading": "Coverage D – Loss Of Use"}),
    ("someone stole my wifes necklace", HOME, {"form": "HO 00 03", "heading": "Special Limits Of Liability"}),
    ("how much do i get if my jewelery is stolen", HOME, {"form": "HO 00 03", "heading": "Special Limits Of Liability"}),
    ("a pipe burst in the kitchen, is that covered", HOME, {"title_contains": "Accidental Discharge"}),
    ("wats my wind n hail deductable", HOME, {"form": "HO 03 12", "heading": "Windstorm Or Hail Percentage Deductible"}),
    ("a tree fell on the roof during a storm", HOME, {"title_contains": "Windstorm"}),
    ("which endorsment gives me the water back up cover", HOME, {"form": "HO 04 95"}),
    ("what does ocurrence mean in this policy", HOME, {"heading": '"Occurrence"'}),
    ("will they pay for a rental car while mine is in the shop", AUTO, {"form": "PP 00 01", "heading": "Transportation Expenses"}),
    ("am i coverd if i drive for uber", AUTO, {"form": "PP 00 01", "heading": "Exclusions – Public Or Livery Conveyance"}),
    ("is a cracked windsheild covered", AUTO, {"form": "PP 00 01", "heading": "Other Than Collision"}),
    ("the other driver had no insurance, what now", AUTO, {"section": "Part C – Uninsured Motorists Coverage"}),
    ("hit and run, does my policy help", AUTO, {"section": "Part C – Uninsured Motorists Coverage"}),
    ("i hit a deer on the highway", AUTO, {"title_contains": "Other Than Collision"}),
    ("whats the collison deductable", AUTO, {"title_contains": "Collision"}),
    ("whats happening with the claim", AUTO, {"title_contains": "Claim"}),
]

# (question, expected policyholders (any of), expected policy number or None)
NAME_CASES = [
    ("does margret chen have water backup", ["Margaret Chen"], None),
    ("is margaret chens house covered for sewer backup", ["Margaret Chen"], None),
    ("wat about priya raghvan", ["Priya Raghavan"], None),
    ("does danial ortiz have collision", ["Daniel Ortiz"], None),
    ("elena moreu's jewelry coverage", ["Elena Moreau"], None),
    ("does chen have water backup", ["Margaret Chen", "David Chen"], None),
    ("whats the deductable for ho 2847 1193", [], "HO-2847-1193"),
    ("ho28471193 deductible", [], "HO-2847-1193"),
    ("pa 5518-0042 rental", [], "PA-5518-0042"),
]

# Names that must NOT be turned into a customer.
NO_NAME_CASES = [
    "how many policies does John Smith have",
    "what does the policy say about mold",
    "when does it renew",
]


def matches(item, expectation: dict) -> bool:
    """Whether a retrieved evidence item satisfies an expectation."""
    if "form" in expectation and item.form_number != expectation["form"]:
        return False
    if "heading" in expectation and (item.heading or "") != expectation["heading"]:
        return False
    if "section" in expectation and (item.section or "") != expectation["section"]:
        return False
    if "title_contains" in expectation:
        text = f"{item.heading or ''} {item.title or ''}".lower()
        if expectation["title_contains"].lower() not in text:
            return False
    return True
