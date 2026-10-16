import { ChevronLeft, ChevronRight } from 'lucide-react';
import { pageWindow } from '../../lib/pagination';

/** "Showing 11–20 of 87", previous / page numbers / next. Renders nothing when there is no row. */
export function Pagination({
  total,
  offset,
  pageSize,
  onChange,
  noun = 'rows',
  disabled = false,
}: {
  total: number;
  offset: number;
  pageSize: number;
  onChange: (offset: number) => void;
  noun?: string;
  disabled?: boolean;
}) {
  if (total <= 0) return null;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(pages, Math.floor(offset / pageSize) + 1);
  const from = offset + 1;
  const to = Math.min(offset + pageSize, total);
  const go = (page: number) => onChange((page - 1) * pageSize);
  const button =
    'inline-flex h-8 min-w-8 items-center justify-center rounded-lg border px-2 text-[12.5px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-btn disabled:cursor-not-allowed disabled:opacity-40';
  return (
    <nav aria-label={`${noun} pages`} className="flex flex-wrap items-center justify-between gap-3 text-[12.5px] text-muted-foreground">
      <span>
        Showing {from}–{to} of {total} {noun}
      </span>
      {pages > 1 && (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => go(current - 1)}
            disabled={disabled || current === 1}
            aria-label="Previous page"
            className={`${button} border-border bg-white text-espresso hover:border-espresso`}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          {pageWindow(current, pages).map((page, i) =>
            page === null ? (
              <span key={`gap-${i}`} className="px-1 text-muted-foreground" aria-hidden="true">
                …
              </span>
            ) : (
              <button
                key={page}
                type="button"
                onClick={() => go(page)}
                disabled={disabled}
                aria-current={page === current ? 'page' : undefined}
                aria-label={`Page ${page}`}
                className={`${button} ${
                  page === current ? 'border-orange-btn bg-orange-btn text-white' : 'border-border bg-white text-espresso hover:border-espresso'
                }`}
              >
                {page}
              </button>
            )
          )}
          <button
            type="button"
            onClick={() => go(current + 1)}
            disabled={disabled || current === pages}
            aria-label="Next page"
            className={`${button} border-border bg-white text-espresso hover:border-espresso`}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </nav>
  );
}
