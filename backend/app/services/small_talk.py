"""Conversational replies for greetings, thanks, goodbyes and questions about the assistant itself.

Rule-based on purpose: these messages are not policy questions, so no language model is called,
nothing is retrieved and nothing is written to the evidence ledger. A message counts as small talk
only when it is made entirely of such phrases ("hi", "hi, how are you?", "thanks!"); "hi, what is
the deductible on HO-2847-1193?" is a policy question and goes through the normal pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Words that may follow a phrase without changing it ("hi there", "thanks again").
_TAIL = r"(?:\s+(?:there|team|all|everyone|again|today|so\s+much|very\s+much|a\s+lot|for\s+now|policy\s+explainer|bot|assistant))*"

# Most specific first: "hi, what can you do" is a request for help, not a greeting.
_PHRASES: list[tuple[str, str]] = [
    ("help", r"help(?:\s+me)?|what\s+can\s+you\s+do|what\s+do\s+you\s+do|who\s+are\s+you|what\s+are\s+you|"
             r"how\s+does\s+this\s+work|how\s+do\s+i\s+use\s+(?:this|you)|what\s+can\s+i\s+ask(?:\s+you)?|"
             r"what\s+should\s+i\s+ask"),
    ("how_are_you", r"how\s+are\s+you(?:\s+doing)?|how\s+(?:is|s)\s+it\s+going|hows\s+it\s+going|what\s*s\s+up|whats\s+up|sup"),
    ("thanks", r"thanks|thank\s+you|thank\s+u|thx|ty|cheers|much\s+appreciated|appreciate\s+it|that\s+helps|that\s+helped"),
    ("goodbye", r"bye|bye\s+bye|goodbye|good\s+bye|see\s+you|see\s+ya|that\s*s\s+all|that\s+is\s+all|good\s+night"),
    ("greeting", r"hi+|hello|hey+|hiya|howdy|greetings|yo|good\s+(?:morning|afternoon|evening|day)"),
    ("acknowledge", r"ok|okay|k|cool|great|nice|got\s+it|alright|all\s+right|sounds\s+good|perfect|awesome|"
                    r"understood|sure|fine|noted"),
]
_PRIORITY = [kind for kind, _ in _PHRASES]
_PATTERNS = [(kind, re.compile(rf"(?:{pattern}){_TAIL}\b")) for kind, pattern in _PHRASES]
_MAX_WORDS = 10


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", text)).strip()


def classify(text: str) -> Optional[str]:
    """The kind of small talk, or None when the message is (or contains) anything else."""
    if re.search(r"\d", text):  # policy numbers, amounts, dates: a real question
        return None
    rest = _normalise(text)
    if not rest or len(rest.split()) > _MAX_WORDS:
        return None
    kinds: list[str] = []
    while rest:
        for kind, pattern in _PATTERNS:
            match = pattern.match(rest)
            if match and match.end() > 0:
                kinds.append(kind)
                rest = rest[match.end():].strip()
                break
        else:
            return None  # something that is not small talk
    return min(kinds, key=_PRIORITY.index)


@dataclass
class PolicyRef:
    policy_number: str
    customer_name: str


@dataclass
class Reply:
    text: str
    suggestions: list[str] = field(default_factory=list)


def suggestions_for(active: Optional[PolicyRef], examples: list[PolicyRef]) -> list[str]:
    """Example questions built from real policies: the active one, else the employee's recent ones."""
    if active:
        n = active.policy_number
        return [f"What is the deductible on {n}?", f"What forms are attached to {n}?", f"Are there any claims on {n}?"]
    if not examples:
        return []
    first = examples[0]
    out = [f"What does policy {first.policy_number} cover?", f"How many policies does {first.customer_name} have?"]
    second = examples[1] if len(examples) > 1 else first
    out.append(f"What is the billing status of {second.policy_number}?")
    return out


def _next_step(active: Optional[PolicyRef]) -> str:
    if active:
        return f"We're looking at {active.customer_name}'s policy {active.policy_number}. What would you like to know about it?"
    return "Which policy would you like to look at? Give me a policy number or a policyholder's name."


def reply_for(
    kind: str,
    first_name: Optional[str],
    active: Optional[PolicyRef],
    examples: list[PolicyRef],
    has_history: bool = False,
) -> Reply:
    """A friendly reply for a kind of small talk, with example questions to continue."""
    name = f", {first_name}" if first_name else ""
    suggestions = suggestions_for(active, examples)
    if kind == "help":
        text = (
            "Here's what I can do:\n"
            "• Explain what a policy covers, its limits and deductibles\n"
            "• List the forms and endorsements attached to a policy\n"
            "• Show the claims and billing on a policy\n"
            "• Answer customer questions, such as how many policies someone has\n"
            "Every answer cites the policy wording, is checked by guardrails and is recorded in The Record. "
            + _next_step(active)
        )
    elif kind == "how_are_you":
        text = f"Doing well, thanks for asking{name}! " + _next_step(active)
    elif kind == "thanks":
        tail = f"Anything else about {active.policy_number}, or another policy?" if active else "Is there another policy you'd like to check?"
        text = f"You're welcome{name}! {tail}"
    elif kind == "goodbye":
        text = (
            f"Goodbye{name}! You can pick this conversation up again from Recent conversations."
            if has_history
            else f"Goodbye{name}! Come back any time you need a policy explained."
        )
        suggestions = []
    elif kind == "acknowledge":
        text = f"Great. What would you like to know next about {active.policy_number}?" if active else "Great. " + _next_step(None)
    else:  # greeting
        text = (
            f"Hi{name}! I'm your policy assistant. I can explain a policy's coverage, limits, deductibles, forms, "
            "claims and billing, always citing the policy wording. " + _next_step(active)
        )
    return Reply(text=text, suggestions=suggestions)


def off_topic_reply(active: Optional[PolicyRef], examples: list[PolicyRef]) -> Reply:
    """For messages the question interpreter judged unrelated to insurance policies."""
    return Reply(
        text=(
            "I can only help with insurance policies: coverage, limits, deductibles, forms, claims and billing. "
            + _next_step(active)
        ),
        suggestions=suggestions_for(active, examples),
    )
