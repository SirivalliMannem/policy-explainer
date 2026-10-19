import React, { useEffect, useRef, useState } from 'react';

interface HeroSectionProps {
  onExploreClick: () => void;
}

export function HeroSection({ onExploreClick }: HeroSectionProps) {
  const heroRef = useRef<HTMLElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    // Check prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setIsPlaying(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsPlaying(true);
        }
      },
      { threshold: 0.25 }
    );

    if (heroRef.current) {
      observer.observe(heroRef.current);
    }

    // Safety fallback: ensure play class is activated shortly after mount
    const timer = setTimeout(() => setIsPlaying(true), 150);

    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, []);

  return (
    <header
      ref={heroRef}
      className={`agent-hub-hero ${isPlaying ? 'play' : ''}`}
      id="hero"
    >
      <div className="gridbg" aria-hidden="true" />

      {/* Concentric spinning and pulsing orbit rings */}
      <div className="agent-orbit" aria-hidden="true">
        <i className="r" />
        <i className="r r2" />
        <i className="r r3" />
        <i className="pulse" />
        <i className="pulse p2" />
      </div>

      <p className="eb">AN AGENTIC LAYER FOR P&amp;C CARRIERS · BY FEUJI</p>

      <h1 className="bh">
        <span className="w">
          <span>FI</span>
        </span>
        <span className="w">
          <span>360</span>
        </span>
      </h1>

      <h2 className="tag">
        The <b>AI workforce</b> for modern P&amp;C insurance carriers
      </h2>

      <p className="lead">
        FI360 puts specialized AI agents to work across claims, underwriting, customer service and
        compliance, handling the repetitive work, handing every decision to your people, and
        recording every step.
      </p>

      <div className="btns">
        <button
          type="button"
          className="agent-hub-pill big cursor-pointer"
          onClick={onExploreClick}
        >
          Explore the agents
        </button>
      </div>

      <div className="cue" aria-hidden="true">
        Scroll ↓
      </div>
    </header>
  );
}
