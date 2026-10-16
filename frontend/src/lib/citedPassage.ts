/**
 * Narrowing a cited page of an uploaded document to the detail an answer sentence relies on:
 * the passage the answer cited, and inside it the sentences that share the sentence's words.
 */

const STOP = new Set(
  'the a an and or of to in on for by with from as at is are was were be been it its this that these those which who whom what when where how not no any all can may will shall would should could has have had do does did your you our we they their them there such than then also into under over up out about per each other only if but so'.split(
    ' '
  )
);

export const MAX_HIGHLIGHTS = 3;

export interface PageParagraph {
  text: string;
  cited: boolean;
}

export interface PassageSentence {
  text: string;
  match: boolean;
}

function normalize(text: string): string {
  return text.replace(/\s+/g, ' ').trim().toLowerCase();
}

function words(text: string): Set<string> {
  return new Set((text.toLowerCase().match(/[a-z0-9$][a-z0-9$,.]*[a-z0-9]|[a-z0-9]/g) ?? []).filter((w) => w.length > 2 && !STOP.has(w)));
}

/** The page's paragraphs, each marked if it is part of the cited passage. */
export function pageParagraphs(pageText: string, passage: string): PageParagraph[] {
  const cited = normalize(passage);
  return pageText
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((text) => {
      const n = normalize(text);
      // A paragraph inside the passage, or a long paragraph the passage was cut from.
      return { text, cited: Boolean(cited) && (cited.includes(n) || n.includes(cited)) };
    });
}

/** The passage as sentences, the ones that share most words with the answer's sentence marked. */
export function passageSentences(passage: string, claim?: string | null): PassageSentence[] {
  const sentences = passage
    .split(/(?<=[.;!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const claimWords = words((claim ?? '').replace(/\[E\d{1,2}\]/g, ''));
  if (claimWords.size === 0) return sentences.map((text) => ({ text, match: false }));
  const scores = sentences.map((s) => {
    let shared = 0;
    words(s).forEach((w) => claimWords.has(w) && shared++);
    return shared;
  });
  const best = Math.max(0, ...scores);
  // Two shared words at least, and close to the best match; never more than a few sentences.
  const floor = Math.max(2, Math.ceil(best * 0.6));
  const keep = new Set(
    scores
      .map((score, i) => ({ score, i }))
      .filter((s) => s.score >= floor)
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_HIGHLIGHTS)
      .map((s) => s.i)
  );
  return sentences.map((text, i) => ({ text, match: keep.has(i) }));
}

/** The words of an answer line that a chip sits in, without its references or markup. */
export function claimText(line: string): string {
  return line.replace(/\[E\d{1,2}\]/g, '').replace(/\*\*/g, '').replace(/\s+/g, ' ').trim();
}
