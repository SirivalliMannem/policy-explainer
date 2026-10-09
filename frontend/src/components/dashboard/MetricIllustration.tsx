/**
 * Small spot illustrations for the dashboard metric cards, in the brand's navy and orange.
 * Rate cards draw a ring filled to the real value; the others are decorative. The card's
 * own number and label carry the meaning, so every illustration is hidden from assistive tech.
 */

const NAVY = '#0F2A43';
const ORANGE = '#F97316';
const LIGHT_ORANGE = '#FDBA74';
const TRACK = '#E2E8F0';
const PAPER = '#F8FAFC';

export type MetricIllustrationKind = 'answered' | 'resolution' | 'coverage' | 'lowConfidence';

function Ring({ value, children }: { value: number; children?: React.ReactNode }) {
  const r = 24;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <>
      <circle cx="32" cy="32" r={r} fill="none" stroke={TRACK} strokeWidth="6" />
      <circle
        cx="32"
        cy="32"
        r={r}
        fill="none"
        stroke={NAVY}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={`${(pct / 100) * c} ${c}`}
        transform="rotate(-90 32 32)"
        style={{ transition: 'stroke-dasharray 0.6s ease-out' }}
      />
      {children}
    </>
  );
}

export function MetricIllustration({ kind, value = 0 }: { kind: MetricIllustrationKind; value?: number }) {
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" aria-hidden="true" focusable="false" className="shrink-0">
      {kind === 'answered' && (
        <>
          {/* Question bubble */}
          <rect x="4" y="8" width="38" height="26" rx="8" fill={PAPER} stroke={NAVY} strokeWidth="2" />
          <path d="M14 34 l-2 8 l9 -8" fill={PAPER} stroke={NAVY} strokeWidth="2" strokeLinejoin="round" />
          <path d="M13 18 h20 M13 24 h13" stroke={NAVY} strokeWidth="2.5" strokeLinecap="round" opacity="0.35" />
          {/* Answer bubble with check */}
          <rect x="24" y="28" width="34" height="24" rx="8" fill={NAVY} />
          <path d="M48 52 l3 7 l-9 -7" fill={NAVY} />
          <path d="M33 40 l5 5 l10 -10" fill="none" stroke={ORANGE} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        </>
      )}

      {kind === 'resolution' && (
        <Ring value={value}>
          {/* Target at the centre */}
          <circle cx="32" cy="32" r="11" fill={PAPER} stroke={LIGHT_ORANGE} strokeWidth="2" />
          <circle cx="32" cy="32" r="5" fill={ORANGE} />
        </Ring>
      )}

      {kind === 'coverage' && (
        <Ring value={value}>
          {/* Cited document */}
          <rect x="24" y="21" width="16" height="21" rx="2.5" fill={PAPER} stroke={NAVY} strokeWidth="1.8" />
          <path d="M27.5 27 h9 M27.5 31 h9 M27.5 35 h6" stroke={NAVY} strokeWidth="1.6" strokeLinecap="round" opacity="0.45" />
          <circle cx="40" cy="40" r="6" fill={ORANGE} />
          <path d="M37.3 40 l1.9 1.9 l3.6 -3.6" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </Ring>
      )}

      {kind === 'lowConfidence' && (
        <>
          {/* Page under review */}
          <rect x="6" y="6" width="32" height="42" rx="4" fill={PAPER} stroke={NAVY} strokeWidth="2" />
          <path d="M12 16 h20 M12 23 h20 M12 30 h12" stroke={NAVY} strokeWidth="2.5" strokeLinecap="round" opacity="0.3" />
          {/* Magnifier */}
          <circle cx="38" cy="36" r="12" fill="#FFFFFF" stroke={NAVY} strokeWidth="3" />
          <path d="M47 45 l9 9" stroke={NAVY} strokeWidth="4.5" strokeLinecap="round" />
          {/* Caution mark inside the lens */}
          <path d="M38 29.5 v7" stroke="#D97706" strokeWidth="3" strokeLinecap="round" />
          <circle cx="38" cy="41.5" r="1.8" fill="#D97706" />
        </>
      )}
    </svg>
  );
}
