const VALUES = [
  { word: 'Clarity.', tone: 'animated-white-text' },
  { word: 'Evidence.', tone: 'animated-white-text' },
  { word: 'Confidence.', tone: 'animated-orange-text' },
];

/**
 * Three words that rise in one after another, hold together, leave in the same order,
 * and repeat. They carry the same moving gradient as "One conversation, connected."
 * The loop is pure CSS (see .hero-value in index.css); reduced motion shows them still.
 */
export function HeroValues() {
  return (
    <p
      className="font-serif font-bold text-[30px] sm:text-[36px] lg:text-[40px] xl:text-[44px] leading-[1.12] tracking-normal"
      aria-label="Clarity. Evidence. Confidence."
    >
      {VALUES.map(({ word, tone }, i) => (
        <span key={word} className="block overflow-hidden pb-1" aria-hidden="true">
          <span className="hero-value block" style={{ animationDelay: `${1.2 + i * 0.6}s` }}>
            <span className={tone}>{word}</span>
          </span>
        </span>
      ))}
    </p>
  );
}

export default HeroValues;
