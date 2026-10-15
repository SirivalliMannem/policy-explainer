import { useState } from 'react';
import { Check, ChevronDown, Loader2, Sparkles, X } from 'lucide-react';
import { analyzeAttention, resolveAttention } from '../../services/api';
import { describeError } from '../../lib/explainer';
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
        Search result: {candidate.passages.length} {candidate.passages.length === 1 ? 'passage' : 'passages'} found, top score{' '}
        {candidate.top_score.toFixed(1)} (evidence is kept at {EVIDENCE_SCORE} and above)
      </li>
      {candidate.passages.map((p, i) => (
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
  const first = candidate.passages[0];
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
        title="Ask this as a new question; the flagged item closes"
      >
        {candidate.question} <span className="text-orange-btn">→</span>
      </button>
      <p className="mt-1 text-[11.5px] text-emerald-700">
        ✓ {candidate.passages.length} {candidate.passages.length === 1 ? 'passage' : 'passages'} found
        {first ? ` · ${passageRef(first)}` : ''}
      </p>
      {candidate.relation === 'related' && candidate.note && (
        <p className="mt-1 text-[11.5px] text-[#9A3D09]">Related question. {candidate.note}</p>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-muted-foreground hover:text-espresso"
      >
        Show how we got this <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <HowWeGotThis original={original} analysis={analysis} candidate={candidate} />}
    </li>
  );
}

const HEADINGS: Record<string, string> = {
  typo: 'WRONG WORDING · TRY THESE',
  vague_wording: 'WRONG WORDING · TRY THESE',
  definition: 'TRY THESE INSTEAD',
};

/**
 * The Resolve box: verified suggestions from the stored analysis. Asking one (or an edited question)
 * runs it as a new question and closes the item; Dismiss closes it with a reason. Nobody else is involved.
 */
export function ResolveBox({
  item,
  onClosed,
}: {
  item: AttentionItem;
  onClosed: (result: AttentionResolveResponse, summary: string) => void;
}) {
  const [analysis, setAnalysis] = useState<AttentionAnalysis | null>(item.analysis ?? null);
  const [analyzing, setAnalyzing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [edited, setEdited] = useState(item.question);
  const [showEdit, setShowEdit] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [reason, setReason] = useState('');

  const ready = analysis?.status === 'ready';
  const candidates = ready ? analysis?.candidates ?? [] : [];
  const outOfScope = ready && analysis?.category === 'out_of_scope';
  const missingEvidence = ready && analysis?.category === 'evidence_missing';
  const noAlternative = ready && !outOfScope && candidates.length === 0 && Boolean(analysis?.type);

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

  const ask = async (action: 'asked_suggestion' | 'edited_and_asked', question: string) => {
    setBusy(question);
    setError(null);
    try {
      const result = await resolveAttention({ entry_id: item.latest_entry_id, action, question });
      onClosed(result, `Asked “${question}”`);
    } catch (err) {
      setError(describeError(err).message);
      setBusy(null);
    }
  };

  const dismiss = async () => {
    if (!reason.trim()) return;
    setBusy('dismiss');
    setError(null);
    try {
      const result = await resolveAttention({ entry_id: item.latest_entry_id, action: 'dismissed', reason: reason.trim() });
      onClosed(result, 'Dismissed as out of scope');
    } catch (err) {
      setError(describeError(err).message);
      setBusy(null);
    }
  };

  return (
    <div className="rounded-xl border border-[#FDC9A0] bg-[#FFFBF7] p-4 text-[13px] leading-relaxed text-espresso">
      <h5 className="mb-2 text-[10.5px] font-semibold tracking-[0.08em] text-orange-btn">RESOLVE</h5>

      {!ready && (
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
            Analyze now
          </button>
        </div>
      )}

      {ready && outOfScope && (
        <div className="mb-3">
          <h6 className="text-[11px] font-bold tracking-[0.08em] text-[#A12A2A]">NO EVIDENCE CAN EXIST</h6>
          <p className="mt-0.5 text-[12.5px] text-[#334155]">{analysis?.reason}</p>
        </div>
      )}

      {ready && missingEvidence && (
        <div className="mb-3">
          <h6 className="text-[11px] font-bold tracking-[0.08em] text-[#A12A2A]">EVIDENCE IS MISSING</h6>
          {analysis?.missing && (
            <p className="mt-0.5 text-[12.5px] text-[#334155]">
              <b className="font-semibold text-espresso">What is missing: </b>
              {analysis.missing}
            </p>
          )}
          {analysis?.type === 'missing_form_or_edition' && !analysis.upload_available && (
            <p className="mt-1 text-[11.5px] text-muted-foreground">The missing edition cannot be added here.</p>
          )}
        </div>
      )}

      {ready && !outOfScope && !analysis?.type && analysis?.reason && (
        <p className="mb-3 text-[12.5px] text-[#334155]">{analysis.reason}</p>
      )}

      {candidates.length > 0 && (
        <div className="mb-3">
          <h6 className="mb-1.5 text-[11px] font-bold tracking-[0.08em] text-espresso">
            {missingEvidence ? 'ASK THIS INSTEAD' : HEADINGS[analysis?.type ?? ''] ?? 'TRY THESE'}
          </h6>
          <ul className="space-y-2">
            {candidates.map((c, i) => (
              <SuggestionCard
                key={c.question}
                original={item.question}
                analysis={analysis as AttentionAnalysis}
                candidate={c}
                recommended={i === 0}
                busy={busy !== null}
                onAsk={() => ask('asked_suggestion', c.question)}
              />
            ))}
          </ul>
        </div>
      )}

      {noAlternative && (
        <div className="mb-3 rounded-lg bg-white px-3 py-2">
          <p className="text-[12.5px] font-semibold text-espresso">No answerable alternative found</p>
          {analysis?.reason && <p className="text-[12px] text-muted-foreground">{analysis.reason}</p>}
        </div>
      )}

      {busy && busy !== 'dismiss' && (
        <p className="mb-2 flex items-center gap-1.5 text-[12px] text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-orange-btn" /> Asking “{busy}” as a new question…
        </p>
      )}
      {error && <p className="mb-2 text-[12px] text-red-700">{error}</p>}

      <div className="space-y-2 border-t border-[#FDC9A0] pt-3">
        {!outOfScope && !noAlternative && (
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
                  onClick={() => ask('edited_and_asked', edited.trim())}
                  disabled={busy !== null || !edited.trim()}
                  className="inline-flex items-center gap-1 rounded-lg border border-orange-btn bg-orange-btn px-3 py-1 text-[12px] font-semibold text-white hover:bg-[#C2410C] disabled:opacity-60"
                >
                  <Check className="h-3.5 w-3.5" /> Ask
                </button>
              </div>
            )}
          </div>
        )}
        <div>
          <button
            type="button"
            onClick={() => setDismissing((v) => !v)}
            aria-expanded={dismissing}
            className="text-[12px] font-semibold text-muted-foreground hover:text-espresso"
          >
            {outOfScope || noAlternative ? 'Dismiss' : 'Dismiss as out of scope'}
          </button>
          {dismissing && (
            <div className="mt-1.5 space-y-1.5">
              <textarea
                aria-label="Reason for dismissing"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Why this needs no answer (required)"
                className="w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-[12.5px] focus:border-orange-btn focus:outline-none"
              />
              <button
                type="button"
                onClick={dismiss}
                disabled={busy !== null || !reason.trim()}
                className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-3 py-1 text-[12px] font-semibold text-espresso hover:border-espresso disabled:opacity-60"
              >
                {busy === 'dismiss' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />} Dismiss
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
