import { BookOpen, MessageSquareQuote } from 'lucide-react';
import type { CompanyGuidance } from '../../types';

/** Approved company articles for the question, kept apart from the policy answer. */
export function CompanyGuidanceBox({ guidance }: { guidance?: CompanyGuidance | null }) {
  const articles = guidance?.articles ?? [];
  if (!articles.length) return null;
  return (
    <section
      aria-label="Company guidance"
      className="mt-3.5 rounded-xl border border-[#BFDBFE] bg-[#F0F7FF] px-3.5 py-3"
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <BookOpen className="h-4 w-4 text-[#1D4ED8]" aria-hidden="true" />
        <span className="text-[12.5px] font-bold text-[#1E3A5F]">Company guidance</span>
        <span className="rounded border border-slate-300 bg-white px-1.5 py-px text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Not policy wording
        </span>
      </div>
      <ul className="space-y-3">
        {articles.map((a) => (
          <li key={a.document_id}>
            <div className="flex items-start gap-2">
              <span className="mt-px shrink-0 rounded-md border border-[#93C5FD] bg-white px-1.5 py-px font-mono text-[10.5px] font-semibold text-[#1D4ED8]">
                {a.ref}
              </span>
              <span className="text-[12.5px] font-semibold text-[#0F2A43]">{a.title}</span>
            </div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-[#334155]">{a.body}</p>
            {a.spoken && (
              <p className="mt-1.5 flex items-start gap-1.5 rounded-lg bg-white/70 px-2.5 py-1.5 text-[12px] leading-relaxed text-[#334155]">
                <MessageSquareQuote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#1D4ED8]" aria-hidden="true" />
                <span>
                  <span className="font-semibold text-[#1E3A5F]">Suggested wording: </span>“{a.spoken}”
                </span>
              </p>
            )}
            <p className="mt-1 text-[10.5px] text-[#64748B]">
              {a.collection} · version {a.version}
              {a.approved_by ? ` · approved by ${a.approved_by}` : ''}
            </p>
          </li>
        ))}
      </ul>
      <p className="mt-2.5 border-t border-[#BFDBFE] pt-2 text-[11px] text-[#475569]">
        Guidance only. If it differs from the policy form, the form applies.
      </p>
    </section>
  );
}
