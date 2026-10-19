import React, { useEffect, useRef, useState } from 'react';

const WHY_CARDS = [
  {
    n: 0,
    bg: 'linear-gradient(135deg,#FB923C,#EA580C)',
    fg: '#fff',
    x: '-33vw',
    y: '-24vh',
    r: '-8deg',
    title: 'Grounded in truth.',
    text: 'Every answer comes from your own data, not from hallucinated guesses. FI360 connects to the systems that define your business, keeping responses accurate and trustworthy.',
  },
  {
    n: 1,
    bg: 'linear-gradient(135deg,#3B82F6,#1D4ED8)',
    fg: '#fff',
    x: '2vw',
    y: '-32vh',
    r: '-2deg',
    title: 'Built for the real world.',
    text: 'AI doesn’t live in slides or sandboxes. FI360 was designed to handle real claims, real policies and real policyholders, without breaking when things get complex.',
  },
  {
    n: 2,
    bg: 'linear-gradient(135deg,#0F2A43,#2563EB)',
    fg: '#fff',
    x: '34vw',
    y: '-22vh',
    r: '4deg',
    title: 'Transparent by design.',
    text: 'You deserve to understand how your AI works. FI360’s logic is visible, reviewable and accountable, so you can always stay in control.',
  },
  {
    n: 3,
    bg: '#FFEDD5',
    bd: '#FDBA74',
    fg: '#0F2A43',
    x: '-35vw',
    y: '12vh',
    r: '3deg',
    title: 'Engineered for longevity.',
    text: 'FI360 isn’t built for trends. It’s built to be fast, modular and designed to evolve with how carriers support their customers in the next decade.',
  },
  {
    n: 4,
    bg: '#DBEAFE',
    bd: '#93B4FF',
    fg: '#0F2A43',
    x: '33vw',
    y: '24vh',
    r: '-5deg',
    title: 'Autonomy with responsibility.',
    text: 'Automation should serve people, not erase them. FI360 handles the routine, records every step, and involves humans when required.',
  },
];

export function ValueStreamSection() {
  const whyRef = useRef<HTMLElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [isPopped, setIsPopped] = useState(false);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setIsPopped(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsPopped(true);
        } else {
          setIsPopped(false);
        }
      },
      { threshold: 0.15 }
    );

    if (stageRef.current) {
      observer.observe(stageRef.current);
      const rect = stageRef.current.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        setIsPopped(true);
      }
    }

    const handleScroll = () => {
      if (!whyRef.current || !stageRef.current) return;
      const rect = whyRef.current.getBoundingClientRect();
      const progress = Math.min(1, Math.max(0, (window.innerHeight - rect.top) / (window.innerHeight + rect.height)));
      stageRef.current.style.setProperty('--p', String(progress));
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleScroll);
    handleScroll();

    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleScroll);
    };
  }, []);

  return (
    <section ref={whyRef} className="why" id="why" aria-label="Why FI360">
      <div ref={stageRef} className={`stage ${isPopped ? 'pop' : ''}`}>
        {/* Parallax floating geometric shapes */}
        <i className="fs fs1" aria-hidden="true" />
        <i className="fs fs2" aria-hidden="true" />
        <i className="fs fs3" aria-hidden="true" />
        <i className="fs fs4" aria-hidden="true" />

        {/* Large background "Why?" title */}
        <div className="wt" aria-hidden="true">
          Why?
        </div>

        {/* 5 Fanning Value Stream / Principle Cards */}
        {WHY_CARDS.map((card) => (
          <div
            key={card.n}
            className="wcard"
            style={
              {
                '--n': card.n,
                '--bg': card.bg,
                '--bd': card.bd || 'transparent',
                '--fg': card.fg,
                '--x': card.x,
                '--y': card.y,
                '--r': card.r,
              } as React.CSSProperties
            }
          >
            <h4>{card.title}</h4>
            <p>{card.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
