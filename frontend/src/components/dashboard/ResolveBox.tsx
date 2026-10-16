import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronDown, Loader2, Sparkles, X } from 'lucide-react';
import { analyzeAttention, resolveAttention } from '../../services/api';
import { describeError } from '../../lib/explainer';
import { resolveView, suggestionNavigation } from '../../lib/resolveSuggestions';
import type {
  AttentionAnalysis,
  AttentionCandidate,
  AttentionItem,
  AttentionPassage,
  AttentionResolveResponse,
} from '../../types';

/** The evidence score at which retrieval keeps a passage (ai-service attention_analysis.EVIDENCE_SCORE). */
const EVIDENCE_SCORE = 3;

function Tag({ kind }: { kind: 'AI' | 'CODE' }) {
  return (
    <span
      className={`mr-1.5 inline-block rounded px-1 py-px font-mono text-[9.5px] font-bold ${
        kind === 'AI' ? 'bg-[#F3E8FF] text-[#6D28D9]' : 'bg-slate-200 text-slate-700'
      }`}
    >
      {kind}
    </span>
  );
}

function passageRef(p: AttentionPassage): string {
  return [p.form_number, p.page ? `p.${p.page}` : null].filter(Boolean).join(' ');
}

/** "Show how we got this": only values that are stored; any line not stored is left out. */
function HowWeGotThis({ original, analysis, candidate }: { original: string; analysis: AttentionAnalysis; candidate: AttentionCandidate }) {
  const search = analysis.original_search;
  const passages = candidate.passages || [];
  return (
    <ul className="mt-2 space-y-1.5 rounded-lg border border-border bg-white px-3 py-2 text-[11.5px] leading-relaxed text-[#334155]">
      {search && (search.clauses_searched !== undefined || search.query_terms?.length) && (
        <li>
          <Tag kind="CODE" />
          Original search: {search.coverages_searched ?? 0} coverages, {search.forms_searched ?? 0} forms and{' '}
          {search.clauses_searched ?? 0} clauses
          {search.query_terms?.length ? ` for ${search.query_terms.map((t) => `“${t}”`).join(', ')}` : ''}.
        </li>
      )}
      <li>
        <Tag kind="AI" />
        What changed: “{original}” → “{candidate.question}”{analysis.reason ? ` (${analysis.reason})` : ''}
      </li>
      <li>
        <Tag kind="CODE" />
        Search result: {passages.length} {passages.length === 1 ? 'passage' : 'passages'} found, top score{' '}
        {(candidate.top_score ?? 0).toFixed(1)} (evidence is kept at {EVIDENCE_SCORE} and above)
      </li>
      {passages.map((p, i) => (
        <li key={`${p.source_id}-${i}`}>
          <Tag kind="CODE" />
          {[p.form_number, p.edition ? `ed. ${p.edition}` : null, p.page ? `p.${p.page}` : null, p.section, p.heading]
            .filter(Boolean)
            .join(' · ')}{' '}
          (score {p.score.toFixed(1)})
          <blockquote className="mt-0.5 border-l-2 border-[#FDBA74] pl-2 font-serif text-[12px] text-espresso">“{p.quote}”</blockquote>
          {p.quote_verified !== null && p.quote_verified !== undefined && (
            <span className={`mt-0.5 block ${p.quote_verified ? 'text-emerald-700' : 'text-red-700'}`}>
              <Tag kind="CODE" />
              {p.quote_verified ? '✓ The quote appears word for word in the source.' : '✗ The quote does not match the source.'}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function SuggestionCard({
  original,
  analysis,
  candidate,
  recommended,
  busy,
  onAsk,
}: {
  original: string;
  analysis: AttentionAnalysis;
  candidate: AttentionCandidate;
  recommended: boolean;
  busy: boolean;
  onAsk: () => void;
}) {
  const [open, setOpen] = useState(false);
  const first = candidate.passages?.[0];
  const hasPassages = Boolean(candidate.passages && candidate.passages.length > 0);
  return (
    <li className={`rounded-lg border bg-white px-3 py-2.5 ${recommended ? 'border-orange-btn' : 'border-border'}`}>
      {recommended && (
        <span className="mb-1 inline-block rounded bg-orange-btn px-1.5 py-px text-[9.5px] font-bold tracking-wider text-white">
          RECOMMENDED
        </span>
      )}
      <button
        type="button"
        onClick={onAsk}
        disabled={busy}
        className="block w-full text-left text-[13px] font-semibold text-espresso hover:text-[#C2410C] disabled:opacity-60"
        title="Ask this question in the chatbot"
      >
        {candidate.question} <span className="text-orange-btn">→</span>
      </button>
      {hasPassages && (
        <p className="mt-1 text-[11.5px] text-emerald-700">
          ✓ {candidate.passages.length} {candidate.passages.length === 1 ? 'passage' : 'passages'} found
          {first ? ` · ${passageRef(first)}` : ''}
        </p>
      )}
      {candidate.relation === 'related' && candidate.note && (
        <p className="mt-1 text-[11.5px] text-[#9A3D09]">Related question. {candidate.note}</p>
      )}
      {hasPassages && (
        <>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-muted-foreground hover:text-espresso"
          >
            Show how we got this <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
          </button>
          {open && <HowWeGotThis original={original} analysis={analysis} candidate={candidate} />}
        </>
      )}
    </li>
  );
}

/** A closing action that needs a reason in the log: Mark resolved, or Dismiss. */
function CloseWithReason({
  label,
  placeholder,
  busy,
  onConfirm,
}: {
  label: string;
  placeholder: string;
  busy: boolean;
  onConfirm: (reason: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-[12px] font-semibold text-muted-foreground hover:text-espresso"
      >
        {label}
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          <textarea
            aria-label={`Reason: ${label}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder={placeholder}
            className="w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] focus:border-orange-btn focus:outline-none"
          />
          <button
            type="button"
            onClick={() => onConfirm(reason.trim())}
            disabled={busy || !reason.trim()}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-3 py-1 text-[12px] font-semibold text-espresso hover:border-espresso disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />} {label}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * The Resolve box. What it shows is decided by resolveView: an unverified customer or a missing
 * policy shows no suggestions; otherwise exactly two suggestions from the stored analysis. Clicking a
 * suggestion (or an edited question) opens a new chat conversation of the employee with the verified
 * policy and asks it through the normal pipeline. The item stays flagged until the employee marks it
 * resolved or dismisses it, each with a reason. Nobody else is involved.
 */
export function ResolveBox({
  item,
  onClosed,
}: {
  item: AttentionItem;
  onClosed: (result: AttentionResolveResponse, summary: string) => void;
}) {
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<AttentionAnalysis | null>(item.analysis ?? null);
  const [analyzing, setAnalyzing] = useState(false);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edited, setEdited] = useState(item.question);
  const [showEdit, setShowEdit] = useState(false);

  const view = resolveView(item, analysis);
  const canAsk = view.mode !== 'customer_not_found' && view.mode !== 'policy_context_missing' && view.mode !== 'out_of_scope';

  const analyze = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      setAnalysis(await analyzeAttention(item.analysis_entry_id || item.latest_entry_id));
    } catch (err) {
      setError(describeError(err).message);
    } finally {
      setAnalyzing(false);
    }
  };

  // Asks in the chat; the flagged item is not resolved by this.
  const askInChat = (question: string) => {
    const { path, state } = suggestionNavigation(item, question);
    navigate(path, { state });
  };

  const close = async (action: 'dismissed' | 'resolved', reason: string, summary: string) => {
    setClosing(true);
    setError(null);
    try {
      onClosed(await resolveAttention({ entry_id: item.latest_entry_id, action, reason }), summary);
    } catch (err) {
      setError(describeError(err).message);
      setClosing(false);
    }
  };

  return (
    <div className="rounded-xl border border-[#FDC9A0] bg-[#FFFBF7] p-4 text-[13px] leading-relaxed text-espresso">
      <h5 className="mb-2 text-[10.5px] font-semibold tracking-[0.08em] text-orange-btn">RESOLVE</h5>

      {view.mode === 'customer_not_found' && (
        <div role="alert" className="mb-3 rounded-lg border border-[#FCA5A5] bg-[#FEF2F2] p-3 text-[12.5px] text-[#991B1B]">
          <h6 className="text-[11px] font-bold tracking-[0.08em] text-[#B91C1C]">CUSTOMER NOT FOUND · VERIFICATION FAILED</h6>
          <p className="mt-1 font-medium">{item.detail || 'No matching customer was found in the customer records.'}</p>
          <p className="mt-1.5 text-[11.5px] text-[#7F1D1D]">
            No questions are suggested: there is no verified customer or policy to base them on. To verify the customer:
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[11.5px] text-[#7F1D1D]">
            <li>Check the spelling of the customer&apos;s full name against the customer records.</li>
            <li>Ask again using a supported identifier: policy number, account number, claim number, email or phone.</li>
          </ul>
        </div>
      )}

      {view.mode === 'policy_context_missing' && (
        <div className="mb-3 rounded-lg bg-white px-3 py-2 text-[12.5px] text-[#334155]">
          <p className="font-semibold text-espresso">Policy not identified</p>
          <p className="text-[12px] text-muted-foreground">
            No single verified policy is linked to this question, so no questions are suggested. Ask again with the policy
            number (or another supported identifier) to give it a policy context.
          </p>
        </div>
      )}

      {view.mode === 'not_ready' && (
        <div className="mb-3 rounded-lg bg-white px-3 py-2 text-[12.5px] text-[#334155]">
          <p className="font-semibold text-espresso">Suggestions not ready</p>
          <p className="text-[12px] text-muted-foreground">
            {analysis?.status === 'failed'
              ? analysis.reason || 'The analysis could not be completed.'
              : 'This question has not been analysed yet.'}
          </p>
          <button
            type="button"
            onClick={analyze}
            disabled={analyzing}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-orange-btn bg-white px-2.5 py-1 text-[12px] font-semibold text-orange-btn hover:bg-[#FFF1E6] disabled:opacity-60"
          >
            {analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {analysis?.status === 'failed' ? 'Try again' : 'Analyze now'}
          </button>
        </div>
      )}

      {view.mode === 'out_of_scope' && (
        <div className="mb-3">
          <h6 className="text-[11px] font-bold tracking-[0.08em] text-[#A12A2A]">NO EVIDENCE CAN EXIST</h6>
          <p className="mt-0.5 text-[12.5px] text-[#334155]">{analysis?.reason}</p>
        </div>
      )}

      {(view.mode === 'suggestions' || view.mode === 'no_alternative') && analysis?.category === 'evidence_missing' && (
        <div className="mb-3">
          <h6 className="text-[11px] font-bold tracking-[0.08em] text-[#A12A2A]">EVIDENCE IS MISSING</h6>
          {analysis.missing && (
            <p className="mt-0.5 text-[12.5px] text-[#334155]">
              <b className="font-semibold text-espresso">What is missing: </b>
              {analysis.missing}
            </p>
          )}
          {analysis.type === 'missing_form_or_edition' && !analysis.upload_available && (
            <p className="mt-1 text-[11.5px] text-muted-foreground">The missing edition cannot be added here.</p>
          )}
        </div>
      )}

      {view.mode === 'suggestions' && (
        <div className="mb-3">
          <h6 className="mb-1.5 text-[11px] font-bold tracking-[0.08em] text-espresso">{view.heading}</h6>
          <ul className="space-y-2">
            {view.candidates.map((c, i) => (
              <SuggestionCard
                key={c.question}
                original={item.question}
                analysis={analysis as AttentionAnalysis}
                candidate={c}
                recommended={i === 0}
                busy={closing}
                onAsk={() => askInChat(c.question)}
              />
            ))}
          </ul>
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            A suggestion opens in a new chat. This item stays in the queue until you mark it resolved.
          </p>
        </div>
      )}

      {view.mode === 'no_alternative' && (
        <div className="mb-3 rounded-lg bg-white px-3 py-2">
          <p className="text-[12.5px] font-semibold text-espresso">No answerable alternative found</p>
          {analysis?.reason && <p className="text-[12px] text-muted-foreground">{analysis.reason}</p>}
        </div>
      )}

      {error && <p className="mb-2 text-[12px] text-red-700">{error}</p>}

      <div className="space-y-2 border-t border-[#FDC9A0] pt-3">
        {canAsk && (
          <div>
            <button
              type="button"
              onClick={() => setShowEdit((v) => !v)}
              aria-expanded={showEdit}
              className="text-[12px] font-semibold text-espresso hover:text-[#C2410C]"
            >
              Edit and ask yourself
            </button>
            {showEdit && (
              <div className="mt-1.5 space-y-1.5">
                <textarea
                  aria-label="Question to ask"
                  value={edited}
                  onChange={(e) => setEdited(e.target.value)}
                  rows={2}
                  maxLength={500}
                  className="w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] focus:border-orange-btn focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => askInChat(edited.trim())}
                  disabled={!edited.trim()}
                  className="inline-flex items-center gap-1 rounded-lg border border-orange-btn bg-orange-btn px-3 py-1 text-[12px] font-semibold text-white hover:bg-[#C2410C] disabled:opacity-60"
                >
                  <Check className="h-3.5 w-3.5" /> Ask in chat
                </button>
              </div>
            )}
          </div>
        )}
        <CloseWithReason
          label="Mark resolved"
          placeholder="How the original issue was resolved (required)"
          busy={closing}
          onConfirm={(reason) => close('resolved', reason, 'Marked resolved')}
        />
        <CloseWithReason
          label={view.mode === 'out_of_scope' || view.mode === 'no_alternative' ? 'Dismiss' : 'Dismiss as out of scope'}
          placeholder="Why this needs no answer (required)"
          busy={closing}
          onConfirm={(reason) => close('dismissed', reason, 'Dismissed as out of scope')}
        />
      </div>
    </div>
  );
}
