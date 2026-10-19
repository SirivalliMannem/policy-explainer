import React, { useEffect, useRef, useState, useMemo } from 'react';
import { VALUE_STREAMS, VALUE_STREAM_COLORS } from '../../data/agents';

interface StatRowProps {
  targetNumber: number;
  label: string;
  subtitle: string;
  renderVisual: (isInView: boolean) => React.ReactNode;
}

function StatRow({ targetNumber, label, subtitle, renderVisual }: StatRowProps) {
  const rowRef = useRef<HTMLDivElement | null>(null);
  const [isInView, setIsInView] = useState(false);
  const [currentValue, setCurrentValue] = useState(targetNumber);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setIsInView(true);
      setCurrentValue(targetNumber);
      return;
    }

    // Start from 0 for animated count-up
    setCurrentValue(0);

    let animationFrameId: number;

    const startCount = () => {
      setIsInView(true);
      const startTime = performance.now();
      const duration = 1400; // 1.4 seconds

      const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(1, elapsed / duration);
        // Cubic ease-out
        const easedProgress = 1 - Math.pow(1 - progress, 3);
        const val = Math.round(targetNumber * easedProgress);
        setCurrentValue(val);

        if (progress < 1) {
          animationFrameId = requestAnimationFrame(animate);
        }
      };

      animationFrameId = requestAnimationFrame(animate);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          startCount();
        } else {
          setIsInView(false);
          setCurrentValue(0);
        }
      },
      { threshold: 0.1 }
    );

    if (rowRef.current) {
      observer.observe(rowRef.current);

      // Check if already in viewport
      const rect = rowRef.current.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        startCount();
      }
    }

    return () => {
      observer.disconnect();
      cancelAnimationFrame(animationFrameId);
    };
  }, [targetNumber]);

  return (
    <div ref={rowRef} className={`row rv ${isInView ? 'in' : ''}`}>
      <div>
        <p>
          <span className="n">{currentValue.toLocaleString('en-US')}</span> {label}
        </p>
        <small>{subtitle}</small>
      </div>
      {renderVisual(isInView)}
    </div>
  );
}

export function EcosystemSection() {
  // Pre-generate 80 deterministic dot properties for the 1k visualization
  const dots = useMemo(() => {
    return Array.from({ length: 80 }, (_, i) => ({
      i,
      delay: (((i * 37) % 300) / 100).toFixed(2),
      bg: i % 3 ? '#2563EB' : '#F97316',
    }));
  }, []);

  // 26 agent blocks
  const agentBlocks = useMemo(() => {
    let globalIndex = 0;
    return VALUE_STREAMS.flatMap((stream, streamIndex) =>
      stream.agents.map(() => {
        const itemIndex = globalIndex++;
        return {
          index: itemIndex,
          color: VALUE_STREAM_COLORS[streamIndex % VALUE_STREAM_COLORS.length],
        };
      })
    );
  }, []);

  const solutionBadges = ['Claims', 'Customer', 'Documents', 'Underwriting', 'Compliance', 'Fraud'];

  return (
    <section className="stmt" id="ecosystem" aria-label="Ecosystem metrics">
      <div className="wrap2">
        {/* Row 1: 26 agents */}
        <StatRow
          targetNumber={26}
          label="agents."
          subtitle="One specialist for every job."
          renderVisual={() => (
            <div className="viz v26" aria-hidden="true">
              {agentBlocks.map(({ index, color }) => (
                <i
                  key={index}
                  style={
                    {
                      '--i': index,
                      background: color,
                    } as React.CSSProperties
                  }
                />
              ))}
            </div>
          )}
        />

        {/* Row 2: 6 solutions */}
        <StatRow
          targetNumber={6}
          label="solutions."
          subtitle="Built around how carriers organise."
          renderVisual={() => (
            <div className="viz v6" aria-hidden="true">
              {solutionBadges.map((badgeName, index) => (
                <b
                  key={badgeName}
                  style={
                    {
                      '--i': index * 5,
                      background: VALUE_STREAM_COLORS[index % VALUE_STREAM_COLORS.length],
                    } as React.CSSProperties
                  }
                >
                  {badgeName}
                </b>
              ))}
            </div>
          )}
        />

        {/* Row 3: 1,000 possibilities */}
        <StatRow
          targetNumber={1000}
          label="possibilities."
          subtitle="Combine them to fit your workflow."
          renderVisual={() => (
            <div className="viz v1k" aria-hidden="true">
              {dots.map((dot) => (
                <i
                  key={dot.i}
                  style={
                    {
                      '--i': dot.i,
                      '--d': dot.delay,
                      background: dot.bg,
                    } as React.CSSProperties
                  }
                />
              ))}
            </div>
          )}
        />
      </div>
    </section>
  );
}
