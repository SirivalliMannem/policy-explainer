import { useEffect, useState } from 'react';
import { AlertCircle, FileText, Loader2, X } from 'lucide-react';
import { getDocumentPages } from '../../services/api';
import type { DocumentInfo, DocumentText } from '../../types';
import { describeError } from '../../lib/explainer';

interface DocumentViewerProps {
  document: DocumentInfo | null;
  onClose: () => void;
}

/** The whole uploaded document, opened from its card in the chat: its extracted text, page by page. */
export function DocumentViewer({ document, onClose }: DocumentViewerProps) {
  const [text, setText] = useState<DocumentText | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!document) return;
    let active = true;
    setText(null);
    setError(null);
    getDocumentPages(document.document_id)
      .then((t) => active && setText(t))
      .catch((err) => active && setError(describeError(err).message));
    return () => {
      active = false;
    };
  }, [document]);

  useEffect(() => {
    if (!document) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [document, onClose]);

  if (!document) return null;
  const unit = document.unit === 'page' ? 'Page' : 'Section';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F2A43]/50 p-3 backdrop-blur-[2px] sm:p-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Document ${document.filename}`}
        onClick={(e) => e.stopPropagation()}
        className="modal-in flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#E2E8F0] px-5 py-4 sm:px-6">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#FFF7ED]">
              <FileText className="h-5 w-5 text-[#EA580C]" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <span className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-[#F97316]">Uploaded document</span>
              <h2 className="truncate text-[15px] font-bold text-[#0F2A43]" title={document.filename}>
                {document.filename}
              </h2>
              <p className="text-[11px] text-[#64748B]">
                {document.page_count} {unit.toLowerCase()}
                {document.page_count === 1 ? '' : 's'} · text extracted from the file · visible only to you
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
            aria-label="Close document"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-[220px] flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          {!text && !error && (
            <div className="flex items-center justify-center gap-2 py-16 text-xs text-[#64748B]">
              <Loader2 className="h-4 w-4 animate-spin text-[#F97316]" /> Opening the document…
            </div>
          )}
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <AlertCircle className="mt-px h-4 w-4 shrink-0" />
              <span>The document could not be opened: {error}</span>
            </div>
          )}
          {text && (
            <div className="space-y-4">
              {text.pages.map((p) => (
                <section key={p.page_id} aria-label={`${unit} ${p.page_number}`}>
                  <h3 className="mb-1.5 font-mono text-[10.5px] font-semibold uppercase tracking-wider text-[#64748B]">
                    {unit} {p.page_number}
                  </h3>
                  <p className="whitespace-pre-wrap rounded-lg border border-[#E2E8F0] bg-white px-4 py-3 font-serif text-[13px] leading-relaxed text-[#1E293B]">
                    {p.text.trim() || '(no text on this page)'}
                  </p>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
