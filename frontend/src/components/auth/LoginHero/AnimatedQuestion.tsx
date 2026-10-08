import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';

const QUESTIONS = [
  'Is water backup covered under this policy?',
  'Which endorsement excludes flood damage?',
  'What is the wind and hail deductible?',
];

export function AnimatedQuestion() {
  const [questionIndex, setQuestionIndex] = useState(0);
  const [typedText, setTypedText] = useState('');
  const [isFadingOut, setIsFadingOut] = useState(false);
  const [isReducedMotion, setIsReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setIsReducedMotion(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setIsReducedMotion(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    if (isReducedMotion) {
      setTypedText(QUESTIONS[0]);
      setIsFadingOut(false);
      return;
    }

    let isCancelled = false;
    let timerId: ReturnType<typeof setTimeout> | null = null;

    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        timerId = setTimeout(resolve, ms);
      });

    async function runSequence() {
      setIsFadingOut(false);
      setTypedText('');

      await wait(500);
      if (isCancelled) return;

      // Type question letter by letter
      const currentQ = QUESTIONS[questionIndex % QUESTIONS.length];
      for (let i = 1; i <= currentQ.length; i++) {
        if (isCancelled) return;
        setTypedText(currentQ.slice(0, i));
        await wait(36);
      }

      // Display question for 3.5 seconds
      await wait(3500);
      if (isCancelled) return;

      // Fade out and advance to next question
      setIsFadingOut(true);
      await wait(600);
      if (isCancelled) return;

      setQuestionIndex((prev) => prev + 1);
    }

    runSequence();

    return () => {
      isCancelled = true;
      if (timerId) clearTimeout(timerId);
    };
  }, [questionIndex, isReducedMotion]);

  return (
    <div className="w-full max-w-[560px]">
      <div
        className={`flex items-center gap-3 bg-white/[0.07] border border-[#F97316]/60 rounded-full px-5 py-3 text-[14px] sm:text-[15px] lg:text-[16px] text-[#f1f5f9] min-h-[48px] sm:min-h-[52px] animate-pill-glow shadow-sm backdrop-blur-[2px] transition-opacity duration-500 ${
          isFadingOut ? 'opacity-0' : 'opacity-100'
        }`}
      >
        <Search className="w-4 h-4 text-[#F97316] shrink-0" strokeWidth={2.2} aria-hidden="true" />
        <span className="flex items-center font-sans tracking-tight overflow-hidden text-ellipsis whitespace-nowrap">
          <span className="text-slate-100 font-normal">{typedText}</span>
          <i
            className="inline-block w-[2px] h-[16px] bg-[#FDBA74] ml-[3px] align-[-2px] animate-caret-blink shrink-0"
            aria-hidden="true"
          />
        </span>
      </div>
    </div>
  );
}

export default AnimatedQuestion;
