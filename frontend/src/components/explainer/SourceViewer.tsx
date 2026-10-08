import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, FileText, FileX2, Loader2, X } from 'lucide-react';
import { getSource } from '../../services/api';
import type { SourceDocument, SourcePassage, SourceTarget } from '../../types';
import { describeError } from '../../lib/explainer';

interface SourceViewerProps {
  target: SourceTarget | null;
  onClose: () => void;
}

const SCOPE_LABEL: Record<string, string> = {
  customer_form: "Insured's own attached form",
  product_wording: 'Generic product wording',
  policy_record: "Policy's declarations / records",
};

// Passages scoring above this word overlap restate each other (measured on the form library:
// restatements 0.50-0.75, distinct clauses 0.20 or less).
const RESTATEMENT_OVERLAP = 0.4;

function wordSet(text: string): Set<string> {
  return new Set(text.toLowerCase().match(/[a-z]+/g) ?? []);
}

function overlap(a: Set<string>, b: Set<string>): number {
  let shared = 0;
  a.forEach((w) => b.has(w) && shared++);
  const union = a.size + b.size - shared;
  return union ? shared / union : 0;
}

/** Split passages into those to show and those that only restate a shown (or the cited) passage. */
function splitRestatements(passages: SourcePassage[]): { shown: SourcePassage[]; similar: SourcePassage[] } {
  const ordered = [...passages.filter((p) => p.is_cited), ...passages.filter((p) => !p.is_cited)];
  const shownSets: Set<string>[] = [];
  const shownIds = new Set<string>();
  const similar: SourcePassage[] = [];
  for (const passage of ordered) {
    const words = wordSet(passage.text);
    if (!passage.is_cited && shownSets.some((s) => overlap(words, s) >= RESTATEMENT_OVERLAP)) {
      similar.push(passage);
    } else {
      shownSets.push(words);
      shownIds.add(passage.source_id);
    }
  }
  return { shown: passages.filter((p) => shownIds.has(p.source_id)), similar };
}

function Meta({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">{label}</dt>
      <dd className="mt-0.5 truncate text-[12.5px] font-semibold text-[#0F2A43]" title={value ? String(value) : undefined}>
        {value || '—'}
      </dd>
    </div>
  );
}

export function SourceViewer({ target, onClose }: SourceViewerProps) {
  const [doc, setDoc] = useState<SourceDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'text' | 'pdf'>('text');
  const [showSimilar, setShowSimilar] = useState(false);
  const citedRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!target) return;
    let active = true;
    setDoc(null);
    setError(null);
    setTab('text');
    setShowSimilar(false);
    setLoading(true);
    getSource(target.sourceType, target.sourceId)
      .then((d) => active && setDoc(d))
      .catch((err) => active && setError(describeError(err).message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [target]);

  useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [target, onClose]);

  useEffect(() => {
    if (doc && tab === 'text') citedRef.current?.scrollIntoView({ block: 'nearest' });
  }, [doc, tab]);

  if (!target) return null;

  const evidence = target.evidence;
  const formNumber = doc?.form_number || evidence?.form_number;
  const title = doc?.form_title || evidence?.title || 'Policy source';
  const page = doc?.page ?? evidence?.page;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F2A43]/50 p-3 backdrop-blur-[2px] sm:p-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Source ${formNumber || ''}`}
        onClick={(e) => e.stopPropagation()}
        className="modal-in flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-[#E2E8F0] px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-[#F97316]">Policy source</span>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {formNumber && <h2 className="font-mono text-lg font-bold text-[#0F2A43]">{formNumber}</h2>}
              <p className="text-sm font-semibold text-[#0F2A43]">{title}</p>
            </div>
            {doc?.scope && (
              <p className="mt-1 text-[11px] text-[#64748B]">
                {SCOPE_LABEL[doc.scope] || doc.scope}
                {doc.policy_number && <span className="font-mono"> · {doc.policy_number}</span>}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
            aria-label="Close source viewer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Metadata */}
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-b border-[#E2E8F0] bg-[#F8FAFC] px-5 py-3.5 sm:grid-cols-4 sm:px-6">
          <Meta label="Edition" value={doc?.edition || evidence?.edition} />
          <Meta label="Page" value={page ? (doc?.page_count ? `${page} of ${doc.page_count}` : page) : null} />
          <Meta label="Section" value={doc?.section || evidence?.section} />
          <Meta label="Heading" value={doc?.heading || evidence?.heading} />
        </dl>

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-[#E2E8F0] px-5 sm:px-6">
          {(['pdf', 'text'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`-mb-px border-b-2 px-3 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer ${
                tab === t ? 'border-[#F97316] text-[#0F2A43]' : 'border-transparent text-[#64748B] hover:text-[#0F2A43]'
              }`}
            >
              {t === 'pdf' ? 'PDF' : 'Text'}
            </button>
          ))}
          <div className="ml-auto">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-xs font-semibold text-[#0F2A43] transition-colors hover:border-[#F97316] hover:text-[#EA580C] cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="min-h-[220px] flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-16 text-xs text-[#64748B]">
              <Loader2 className="h-4 w-4 animate-spin text-[#F97316]" /> Loading source…
            </div>
          )}
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <AlertCircle className="mt-px h-4 w-4 shrink-0" />
              <span>
                The source record could not be loaded: {error}
                {evidence?.content && ' The retrieved evidence text is shown below.'}
              </span>
            </div>
          )}

          {!loading && tab === 'pdf' && (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[#CBD5E1] bg-[#F8FAFC] px-6 py-12 text-center">
              <FileX2 className="h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-semibold text-[#0F2A43]">No PDF on file for this form</p>
              <p className="mt-1 max-w-md text-xs leading-relaxed text-[#64748B]">
                The synthetic carrier library stores {formNumber || 'this form'} as structured clause text — form, edition,
                page, section and heading — rather than as a PDF document. Use the Text tab to read the exact cited wording.
              </p>
              <button
                type="button"
                onClick={() => setTab('text')}
                className="mt-4 rounded-lg bg-[#0F2A43] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#16385A] cursor-pointer"
              >
                View source text
              </button>
            </div>
          )}

          {!loading && tab === 'text' && (doc || evidence) && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-[10.5px] text-[#64748B]">
                <FileText className="h-3.5 w-3.5 text-[#F97316]" />
                <span>
                  Synthetic source representation · structured text from the carrier form library
                  {page ? ` · page ${page}` : ''}
                </span>
              </div>

              {doc && Object.keys(doc.record_fields).length > 0 && (
                <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {Object.entries(doc.record_fields).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2">
                      <dt className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">{k}</dt>
                      <dd className="mt-0.5 text-[12.5px] font-semibold text-[#0F2A43]">{v}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {doc && doc.passages.length > 0 ? (
                <div className="space-y-3">
                  {doc.source_type === 'coverage' && (
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
                      Governing wording in {doc.form_number}
                    </p>
                  )}
                  {(() => {
                    const { shown, similar } = splitRestatements(doc.passages);
                    const renderPassage = (p: SourcePassage) => (
                    <div
                      key={p.source_id}
                      ref={p.is_cited ? citedRef : undefined}
                      className={`rounded-lg border px-4 py-3 ${
                        p.is_cited
                          ? 'border-[#FDBA74] border-l-4 border-l-[#F97316] bg-[#FFF7ED]'
                          : 'border-[#E2E8F0] bg-white'
                      }`}
                    >
                      <div className="mb-1.5 flex flex-wrap items-center gap-2">
                        <span className="text-[12px] font-bold text-[#0F2A43]">{p.heading}</span>
                        {p.section && <span className="text-[10.5px] text-[#64748B]">{p.section}</span>}
                        {p.page && <span className="font-mono text-[10.5px] text-[#64748B]">p.{p.page}</span>}
                        {p.is_cited && (
                          <span className="rounded bg-[#F97316] px-1.5 py-px text-[9.5px] font-bold uppercase tracking-wider text-white">
                            Cited
                          </span>
                        )}
                      </div>
                      <p className={`font-serif text-[13.5px] leading-relaxed ${p.is_cited ? 'text-[#1E293B]' : 'text-[#475569]'}`}>
                        {p.text}
                      </p>
                      {p.is_cited && p.plain_language && (
                        <div className="mt-2.5 border-t border-[#FDBA74]/60 pt-2">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-[#C2410C]">
                            Approved plain-language explanation
                          </span>
                          <p className="mt-0.5 text-[12.5px] leading-relaxed text-[#334155]">{p.plain_language}</p>
                        </div>
                      )}
                    </div>
);
                    return (
                      <>
                        {shown.map(renderPassage)}
                        {similar.length > 0 && (
                          <div>
                            <button
                              type="button"
                              onClick={() => setShowSimilar(!showSimilar)}
                              className="flex items-center gap-1 text-[11.5px] font-semibold text-[#64748B] hover:text-[#0F2A43] cursor-pointer"
                              aria-expanded={showSimilar}
                            >
                              {showSimilar ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                              Similar wording on this page ({similar.length})
                            </button>
                            {showSimilar && <div className="mt-2 space-y-3 opacity-90">{similar.map(renderPassage)}</div>}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              ) : (
                (doc?.text || evidence?.content) && (
                  <div className="rounded-lg border border-[#FDBA74] border-l-4 border-l-[#F97316] bg-[#FFF7ED] px-4 py-3">
                    <p className="font-serif text-[13.5px] leading-relaxed text-[#1E293B]">
                      {evidence?.content || doc?.text}
                    </p>
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
