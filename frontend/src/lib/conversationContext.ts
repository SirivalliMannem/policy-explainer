/**
 * The customer a conversation is about, and what a resolved question does to it.
 *
 * A conversation has a customer once one is identified: with one selected policy, or alone when the
 * customer has several ("What are Elena's policies?"). Follow-ups then need no name. A question about
 * a different customer never runs against the current one: it asks to switch first.
 */
import type { CustomerContext, PolicyContextCandidate, QuestionResolution } from '../types';

/** The conversation's customer: the selected policy's, else the one chosen without a policy. */
export function currentCustomer(
  policy: PolicyContextCandidate | null,
  customer: CustomerContext | null
): CustomerContext | null {
  if (policy) return { customer_id: policy.customer_id, customer_name: policy.customer_name };
  return customer;
}

export type ContextAction =
  /** Another customer than the conversation's: confirm the switch (or start a new conversation) first. */
  | { kind: 'switch'; target: CustomerContext; policy: PolicyContextCandidate | null }
  /** One policy: it becomes the conversation's policy (and its customer the conversation's customer). */
  | { kind: 'set_policy'; policy: PolicyContextCandidate }
  /** A customer with several policies, or a customer lookup: the customer becomes the context. */
  | { kind: 'set_customer'; target: CustomerContext }
  /** Nothing about the context changes. */
  | { kind: 'keep' };

/** The customer a resolution is about, if it is verified and unique. */
export function resolvedCustomer(resolution: QuestionResolution): CustomerContext | null {
  const c = resolution.customer;
  return c ? { customer_id: c.customer_id, customer_name: c.name } : null;
}

/** What a resolved question does to the conversation's context. */
export function contextAction(resolution: QuestionResolution, current: CustomerContext | null): ContextAction {
  const target = resolvedCustomer(resolution);
  const single = resolution.status === 'resolved' && resolution.policy ? resolution.policy : null;
  if (!target) return { kind: 'keep' };
  if (current && current.customer_id !== target.customer_id) {
    return { kind: 'switch', target, policy: single };
  }
  // A portfolio question about the book of business names no customer; it has no target above.
  if (resolution.intent === 'portfolio') {
    return single ? { kind: 'set_policy', policy: single } : current ? { kind: 'keep' } : { kind: 'set_customer', target };
  }
  if (resolution.status === 'ambiguous' && resolution.answer_all && !current) {
    return { kind: 'set_customer', target };
  }
  return { kind: 'keep' };
}

/** How a switch card describes one side: the policy, else how many policies the customer has. */
export function sideLabel(policy: PolicyContextCandidate | null | undefined, count?: number | null): string {
  if (policy) return policy.policy_number;
  if (count === undefined || count === null) return 'All policies';
  return count === 1 ? '1 policy' : `${count} policies`;
}
