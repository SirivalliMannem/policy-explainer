import { KeyboardEvent, MutableRefObject, useEffect, useId, useRef, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import { searchPolicyContext } from '../../services/api';
import type { PolicyContextCandidate } from '../../types';
import { lineLabel, statusLabel } from '../../lib/explainer';

interface QuestionInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder: string;
  inputRef: MutableRefObject<HTMLInputElement | null>;
}

// The policy-number fragment being typed at the caret: "HO-28", "ho 28", "pa6120-77", or bare digits "2847".
// A prefix needs a separator or a digit after it, so typing "how" or "pay" does not open the list.
const FRAGMENT_AT_CARET = /(?:^|[\s(,])((?:ho|pa)(?:[-\s]\d{0,4}|\d{1,4})(?:[-\s]?\d{0,4})?|\d{3,8})$/i;

interface Fragment {
  start: number;
  end: number;
  query: string;
  compact: string;
}

/** Turn what was typed into the stored format: "ho 28" -> "HO-28", "28471193" -> "2847-1193". */
function toSearchQuery(raw: string): { query: string; compact: string } {
  const compact = raw.toUpperCase().replace(/[\s-]/g, '');
  const m = compact.match(/^(HO|PA)?(\d{0,4})(\d{0,4})$/);
  if (!m) return { query: raw.trim(), compact };
  const [, prefix = '', first, second] = m;
  const digits = second ? `${first}-${second}` : first;
  return { query: prefix ? (digits ? `${prefix}-${digits}` : `${prefix}-`) : digits, compact };
}

function fragmentAt(text: string, caret: number): Fragment | null {
  const before = text.slice(0, caret);
  const match = before.match(FRAGMENT_AT_CARET);
  if (!match) return null;
  const typed = match[1];
  const { query, compact } = toSearchQuery(typed);
  return { start: caret - typed.length, end: caret, query, compact };
}

/** One row per policy number: its in-force term, or the latest term when none is in force. */
function currentTerms(candidates: PolicyContextCandidate[], compact: string): PolicyContextCandidate[] {
  const byNumber = new Map<string, PolicyContextCandidate>();
  for (const c of candidates) {
    if (!c.policy_number.replace(/-/g, '').includes(compact)) continue;
    const best = byNumber.get(c.policy_number);
    const better =
      !best ||
      (c.status === 'in_force' && best.status !== 'in_force') ||
      (c.status === best.status && c.effective_date > best.effective_date);
    if (better) byNumber.set(c.policy_number, c);
  }
  return [...byNumber.values()].sort((a, b) => a.policy_number.localeCompare(b.policy_number));
}

/**
 * The question box. While a policy number is being typed, a list of matching policies opens above it;
 * choosing one replaces the partial number with the full one. The question is not sent.
 */
export function QuestionInput({ value, onChange, disabled, placeholder, inputRef }: QuestionInputProps) {
  const listId = useId();
  const [fragment, setFragment] = useState<Fragment | null>(null);
  const [matches, setMatches] = useState<PolicyContextCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const requestRef = useRef(0);

  const open = Boolean(fragment) && !dismissed && !disabled && (loading || matches.length > 0);

  // Look up matches for the fragment at the caret, debounced; stale responses are ignored.
  useEffect(() => {
    if (!fragment || dismissed) {
      setMatches([]);
      setLoading(false);
      return;
    }
    const request = ++requestRef.current;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const found = currentTerms(await searchPolicyContext(fragment.query), fragment.compact);
        if (request === requestRef.current) {
          setMatches(found);
          setActive(0);
        }
      } catch {
        if (request === requestRef.current) setMatches([]);
      } finally {
        if (request === requestRef.current) setLoading(false);
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [fragment?.query, fragment?.compact, dismissed]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = (text: string, caret: number | null) => {
    const next = caret === null ? null : fragmentAt(text, caret);
    if (!next || next.query !== fragment?.query) setDismissed(false);
    setFragment(next);
  };

  const choose = (policy: PolicyContextCandidate) => {
    if (!fragment) return;
    const after = value.slice(fragment.end);
    const insert = policy.policy_number + (after.startsWith(' ') ? '' : ' ');
    const next = value.slice(0, fragment.start) + insert + after;
    const caret = fragment.start + insert.length;
    onChange(next);
    setFragment(null);
    setMatches([]);
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(caret, caret);
    });
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open || matches.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((i) => (i + 1) % matches.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((i) => (i - 1 + matches.length) % matches.length);
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      // Choosing a policy must not submit the question.
      e.preventDefault();
      choose(matches[active]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setDismissed(true);
    }
  };

  return (
    <div className="relative min-w-0 flex-1">
      {open && (
        <div className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border border-[#E2E8F0] bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-[#F1F5F9] px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-[#64748B]">
            <span>Matching policies</span>
            <span className="font-normal normal-case tracking-normal text-[#94A3B8]">↑↓ to move · Enter to choose · Esc to close</span>
          </div>
          {loading && matches.length === 0 ? (
            <div className="flex items-center gap-2 px-3 py-3 text-[12px] text-[#64748B]">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[#F97316]" /> Searching policies…
            </div>
          ) : (
            <ul id={listId} role="listbox" aria-label="Matching policies" className="max-h-60 overflow-y-auto py-1">
              {matches.map((policy, i) => (
                <li
                  key={policy.policy_number}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseDown={(e) => {
                    e.preventDefault(); // keep focus in the input
                    choose(policy);
                  }}
                  onMouseEnter={() => setActive(i)}
                  className={`flex cursor-pointer items-center gap-3 px-3 py-2 ${i === active ? 'bg-[#FFF7ED]' : ''}`}
                >
                  <FileText className={`h-3.5 w-3.5 shrink-0 ${i === active ? 'text-[#F97316]' : 'text-[#94A3B8]'}`} />
                  <span className="font-mono text-[12.5px] font-bold text-[#0F2A43]">{policy.policy_number}</span>
                  <span className="min-w-0 flex-1 truncate text-[12px] text-[#475569]">{policy.customer_name}</span>
                  <span className="hidden shrink-0 rounded border border-[#FDBA74] bg-[#FFF7ED] px-1.5 py-px text-[10px] font-semibold uppercase text-[#C2410C] sm:inline">
                    {lineLabel(policy.line_of_business)}
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-2 py-px text-[10px] font-semibold ring-1 ${
                      policy.status === 'in_force'
                        ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                        : 'bg-slate-100 text-slate-600 ring-slate-200'
                    }`}
                  >
                    {statusLabel(policy.status)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          refresh(e.target.value, e.target.selectionStart);
        }}
        onKeyDown={onKeyDown}
        onKeyUp={(e) => {
          if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) refresh(value, e.currentTarget.selectionStart);
        }}
        onClick={(e) => refresh(value, e.currentTarget.selectionStart)}
        onBlur={() => setFragment(null)}
        placeholder={placeholder}
        disabled={disabled}
        aria-label="Policy question"
        role="combobox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={open && matches.length ? `${listId}-${active}` : undefined}
        autoComplete="off"
        className="w-full rounded-xl border border-[#CBD5E1] bg-white px-4 py-3 text-[13.5px] text-[#0F2A43] placeholder-[#94A3B8] transition-all focus:border-[#F97316] focus:outline-none focus:ring-2 focus:ring-[#F97316]/20 disabled:opacity-60"
      />
    </div>
  );
}
