// When one question is answered for each of a customer's matching policies, the conversation stores
// one question per policy. Reopening it should show the question once, then each labelled answer.
// Kept free of runtime imports so `node --test` can load it directly.

export interface StoredQuestion {
  question: string;
  policy_id?: string | null;
  created_at: string;
  asked_by?: { employee_id: string } | null;
}

/** Answers asked together arrive within moments of each other; a later re-ask is a new question. */
const SAME_ASK_MS = 5 * 60 * 1000;

function stamp(iso: string): number {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`).getTime();
}

/**
 * For each stored question: whether it starts a new user message, and whether it is one of a group
 * of answers to the same question for different policies (and so is labelled with its policy).
 */
export function groupPolicyAnswers<T extends StoredQuestion>(records: T[]): { record: T; startsQuestion: boolean; inGroup: boolean }[] {
  const out: { record: T; startsQuestion: boolean; inGroup: boolean }[] = [];
  let groupStart = -1;
  records.forEach((record, i) => {
    const first = groupStart >= 0 ? records[groupStart] : null;
    const sameAsk =
      first !== null &&
      record.question.trim() === first.question.trim() &&
      Boolean(record.policy_id) &&
      // A different policy each time: the same policy twice is the employee asking again.
      !records.slice(groupStart, i).some((r) => r.policy_id === record.policy_id) &&
      (record.asked_by?.employee_id ?? null) === (first.asked_by?.employee_id ?? null) &&
      stamp(record.created_at) - stamp(first.created_at) <= SAME_ASK_MS;
    if (sameAsk) {
      out[groupStart].inGroup = true;
      out.push({ record, startsQuestion: false, inGroup: true });
    } else {
      groupStart = i;
      out.push({ record, startsQuestion: true, inGroup: false });
    }
  });
  return out;
}
