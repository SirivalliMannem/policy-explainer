"""Messy-question benchmark across modes.

    python -m tests.messy_benchmark            # raw, rules and llm (llm uses the configured provider)
    python -m tests.messy_benchmark rules      # deterministic modes only, no model calls

raw    the question as typed, no understanding step (behaviour before this change)
rules  spelling, names, policy numbers and synonyms — no model call
llm    rules plus the language model's constrained rewrite
"""

import sys
import time

from app.db.database import SessionLocal
from app.models.policy import CorePolicy
from app.services.retrieval.evidence_retriever import EvidenceRetriever
from app.services.understanding import QueryInterpreter
from tests.messy_questions import NAME_CASES, NO_NAME_CASES, RETRIEVAL_CASES, matches

TOP_K = 8


def _policy_id(db, number: str) -> str:
    return (
        db.query(CorePolicy)
        .filter(CorePolicy.policy_number == number)
        .order_by(CorePolicy.status != "in_force", CorePolicy.term_number.desc())
        .first()
        .id
    )


def run(modes: list[str], pause: float = 0.0) -> dict:
    db = SessionLocal()
    scores = {}
    try:
        for mode in modes:
            hits, rows = 0, []
            for question, number, expectation in RETRIEVAL_CASES:
                search = question
                if mode != "raw":
                    search = QueryInterpreter.interpret(question, db, mode="auto" if mode == "llm" else "rules").search_text
                    time.sleep(pause if mode == "llm" else 0)
                evidence = EvidenceRetriever.retrieve(search, _policy_id(db, number), db, limit=TOP_K)
                rank = next((i + 1 for i, e in enumerate(evidence) if matches(e, expectation)), None)
                hits += rank is not None
                rows.append((rank, question))

            names_ok = 0
            for question, holders, number in NAME_CASES:
                if mode == "raw":
                    found_holders, found_numbers = [], []
                else:
                    interp = QueryInterpreter.interpret(question, db, mode="auto" if mode == "llm" else "rules")
                    found_holders, found_numbers = interp.policyholders, interp.policy_numbers
                    time.sleep(pause if mode == "llm" else 0)
                ok = (not holders or any(h in found_holders for h in holders)) and (not number or number in found_numbers)
                names_ok += ok

            false_names = 0
            if mode != "raw":
                for question in NO_NAME_CASES:
                    false_names += bool(QueryInterpreter.interpret(question, db, mode="rules").policyholders)

            scores[mode] = {
                "retrieval": (hits, len(RETRIEVAL_CASES)),
                "names": (names_ok, len(NAME_CASES)),
                "false_names": false_names,
                "rows": rows,
            }
    finally:
        db.close()
    return scores


def main() -> None:
    modes = ["raw", "rules"] if (len(sys.argv) > 1 and sys.argv[1] == "rules") else ["raw", "rules", "llm"]
    scores = run(modes, pause=1.0)
    for mode, s in scores.items():
        h, n = s["retrieval"]
        nh, nn = s["names"]
        print(f"{mode:6} retrieval {h}/{n}   names & policy numbers {nh}/{nn}   wrong names {s['false_names']}")
    print()
    for i, (question, _, _) in enumerate(RETRIEVAL_CASES):
        cells = "  ".join(f"{m}={'#' + str(scores[m]['rows'][i][0]) if scores[m]['rows'][i][0] else 'MISS':6}" for m in modes)
        print(f"{cells}  {question}")


if __name__ == "__main__":
    main()
