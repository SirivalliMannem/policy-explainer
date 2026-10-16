// Page numbers to show for a paged list: the first, the last, and the current page with its
// neighbours; null marks a gap ("…"). Pure, so `node --test` can load it.

/** Rows per page in the dashboard's Needs attention queue and the Audit Log. */
export const PAGE_SIZE = 10;

export function pageWindow(current: number, pages: number): (number | null)[] {
  if (pages <= 7) return Array.from({ length: pages }, (_, i) => i + 1);
  const shown = new Set([1, pages, current - 1, current, current + 1].filter((p) => p >= 1 && p <= pages));
  const sorted = [...shown].sort((a, b) => a - b);
  const out: (number | null)[] = [];
  sorted.forEach((page, i) => {
    if (i > 0 && page - sorted[i - 1] > 1) out.push(null);
    out.push(page);
  });
  return out;
}
