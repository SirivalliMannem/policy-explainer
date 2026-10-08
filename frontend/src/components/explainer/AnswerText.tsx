import { Fragment, ReactNode } from 'react';
import { FileText } from 'lucide-react';
import type { EvidenceItem } from '../../types';
import { evidenceByIndex, evidenceChipLabel } from '../../lib/explainer';

interface AnswerTextProps {
  text: string;
  evidence: EvidenceItem[];
  onOpenSource: (item: EvidenceItem) => void;
}

const TOKEN = /(\*\*[^*]+\*\*|(?:\[E\d{1,2}\])+)/g;
const REF = /\[E(\d{1,2})\]/g;
const BULLET = /^\s*(?:[-*•])\s+/;

export function SourceChip({
  item,
  onOpen,
  size = 'sm',
}: {
  item: EvidenceItem;
  onOpen: (item: EvidenceItem) => void;
  size?: 'sm' | 'md';
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(item)}
      title={`Open source: ${item.title || evidenceChipLabel(item)}`}
      className={`source-chip inline-flex items-center gap-1 align-baseline rounded-md border border-[#FDBA74] bg-[#FFF7ED] font-mono font-semibold text-[#C2410C] hover:bg-[#F97316] hover:text-white hover:border-[#F97316] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#F97316]/40 transition-colors cursor-pointer whitespace-nowrap ${
        size === 'md' ? 'px-2 py-1 text-[11px]' : 'mx-0.5 px-1.5 py-px text-[10.5px]'
      }`}
    >
      <FileText className={size === 'md' ? 'w-3 h-3' : 'w-2.5 h-2.5'} />
      {evidenceChipLabel(item)}
    </button>
  );
}

function renderInline(text: string, evidence: EvidenceItem[], onOpenSource: AnswerTextProps['onOpenSource']): ReactNode[] {
  return text.split(TOKEN).map((part, i) => {
    if (!part) return null;
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-[#0F2A43]">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('[E')) {
      // One chip per distinct source label: [E1][E3] often point at the same form page.
      const seen = new Set<string>();
      const chips: ReactNode[] = [];
      for (const match of part.matchAll(REF)) {
        const item = evidenceByIndex(evidence, Number(match[1]));
        if (!item) continue;
        const label = evidenceChipLabel(item);
        if (seen.has(label)) continue;
        seen.add(label);
        chips.push(<SourceChip key={`${i}-${match[1]}`} item={item} onOpen={onOpenSource} />);
      }
      return <Fragment key={i}>{chips}</Fragment>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

/** Renders a grounded answer: paragraphs, "- " bullets, **bold** amounts and inline source chips. */
export function AnswerText({ text, evidence, onOpenSource }: AnswerTextProps) {
  const blocks: { type: 'p' | 'ul'; lines: string[] }[] = [];
  for (const raw of text.split(/\n+/)) {
    const line = raw.trim();
    if (!line) continue;
    if (BULLET.test(line)) {
      const last = blocks[blocks.length - 1];
      const content = line.replace(BULLET, '');
      if (last?.type === 'ul') last.lines.push(content);
      else blocks.push({ type: 'ul', lines: [content] });
    } else {
      blocks.push({ type: 'p', lines: [line] });
    }
  }

  return (
    <div className="space-y-2 text-[13.5px] leading-relaxed text-[#1E293B]">
      {blocks.map((block, i) =>
        block.type === 'ul' ? (
          <ul key={i} className="space-y-1.5 pl-1">
            {block.lines.map((line, j) => (
              <li key={j} className="flex gap-2">
                <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-[#F97316]" />
                <span>{renderInline(line, evidence, onOpenSource)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>{renderInline(block.lines[0], evidence, onOpenSource)}</p>
        )
      )}
    </div>
  );
}
