const POLICY_NUMBER_PATTERN = /\b((?:HO|PA)[-\s]?\d{3,4}(?:[-\s]\d{3,4})?)\b/i;
const COVERAGE_PATTERN = /\b(Coverage\s+[A-Za-z0-9]+)\b/i;

function toTitleCase(str: string): string {
  return str.replace(/\b[a-z]/g, (c) => c.toUpperCase());
}

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Generates a concise, meaningful, human-readable title based on initial question and policy context.
 */
export function formatConversationTitle(
  firstQuestionOrTitle: string,
  customerName?: string | null,
  policyNumber?: string | null
): string {
  const text = (firstQuestionOrTitle || '').replace(/\s+/g, ' ').trim();
  if (!text) return 'New Conversation';

  // 1. Book-wide portfolio inquiries: "What policies do we have?" -> "Policy Overview"
  if (
    /^\s*(?:what|which|list|show)\s+(?:kind\s+of\s+|type\s+of\s+)?(?:all\s+)?(?:our\s+)?policies\s+do\s+(?:we|i)\s+have[?.]*\s*$/i.test(text) ||
    /^\s*what\s+policies\s+do\s+(?:we|i)\s+have[?.]*\s*$/i.test(text) ||
    /^\s*(?:what|which)\s+policies\s+are\s+(?:in\s+force|on\s+file)[?.]*\s*$/i.test(text)
  ) {
    return 'Policy Overview';
  }

  // 2. Customer policies:
  // "What policies does Elena Moreau have?" -> "Elena Moreau — Policies"
  // "What are David Chen's policies?" -> "David Chen — Policies"
  const custMatch1 = text.match(/\bwhat\s+policies\s+does\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s+have\b/i);
  if (custMatch1) {
    return `${toTitleCase(custMatch1[1])} — Policies`;
  }
  const custMatch2 = text.match(/\bwhat\s+are\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)(?:'s|’s)\s+policies\b/i);
  if (custMatch2) {
    return `${toTitleCase(custMatch2[1])} — Policies`;
  }
  const custMatch3 = text.match(/\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)(?:'s|’s)\s+policies\b/i);
  if (custMatch3) {
    return `${toTitleCase(custMatch3[1])} — Policies`;
  }
  if (customerName && /\bpolicies\b/i.test(text) && !/\b(?:Coverage|HO|PA)\b/i.test(text)) {
    if (new RegExp(`\\b${escapeRegExp(customerName)}\\b`, 'i').test(text)) {
      return `${customerName} — Policies`;
    }
  }

  // 3. Policy Number references:
  // "What does HO-9021-4477 cover?" -> "HO-9021-4477 — Coverage Details"
  // "HO-908-023 limits and deductibles" -> "HO-908-023 — Limits & Deductibles"
  const polMatch = text.match(POLICY_NUMBER_PATTERN);
  const polNum = polMatch
    ? polMatch[1].toUpperCase().replace(/\s+/g, '-')
    : policyNumber && text.toUpperCase().includes(policyNumber.toUpperCase())
    ? policyNumber
    : null;
  if (polNum) {
    if (/\b(?:limits?\s+and\s+deductibles?|deductibles?\s+and\s+limits?)\b/i.test(text)) {
      return `${polNum} — Limits & Deductibles`;
    }
    if (/\bdeductibles?\b/i.test(text)) {
      return `${polNum} — Deductible`;
    }
    if (/\blimits?\b/i.test(text)) {
      return `${polNum} — Limits`;
    }
    if (/\b(?:cover|covers|covered|coverage)\b/i.test(text)) {
      return `${polNum} — Coverage Details`;
    }
    if (/\bclaims?\b/i.test(text)) {
      return `${polNum} — Claims`;
    }
    if (/\b(?:forms?|endorsements?)\b/i.test(text)) {
      return `${polNum} — Forms & Endorsements`;
    }
    if (/\b(?:billing|premium)\b/i.test(text)) {
      return `${polNum} — Billing`;
    }
    return `${polNum} — Policy Details`;
  }

  // 4. Coverage letters / items:
  // "What is the deductible for Coverage A?" -> "Coverage A — Deductible"
  const covMatch = text.match(COVERAGE_PATTERN);
  if (covMatch) {
    const covName = toTitleCase(covMatch[1]);
    if (/\b(?:limits?\s+and\s+deductibles?|deductibles?\s+and\s+limits?)\b/i.test(text)) {
      return `${covName} — Limits & Deductibles`;
    }
    if (/\bdeductibles?\b/i.test(text)) {
      return `${covName} — Deductible`;
    }
    if (/\blimits?\b/i.test(text)) {
      return `${covName} — Limits`;
    }
    if (/\b(?:cover|covers|covered|coverage)\b/i.test(text)) {
      return `${covName} — Coverage Details`;
    }
    return `${covName} — Details`;
  }

  // 5. "Explain this policy" -> "Policy Explanation"
  if (
    /^\s*(?:please\s+)?(?:explain|summarize)\s+(?:this\s+|the\s+|our\s+)?policy[?.]*\s*$/i.test(text) ||
    /\bexplain\s+this\s+policy\b/i.test(text)
  ) {
    return 'Policy Explanation';
  }

  // Fallback to clean truncation at word boundary
  if (text.length <= 40) return text;
  const cut = text.slice(0, 40).lastIndexOf(' ') > 0 ? text.slice(0, text.slice(0, 40).lastIndexOf(' ')) : text.slice(0, 40);
  return cut.replace(/[,.;:-]+$/, '') + '…';
}
