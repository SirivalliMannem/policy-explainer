import React, { useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { HeroSection } from '../components/agent-hub/HeroSection';
import { EcosystemSection } from '../components/agent-hub/EcosystemSection';
import { ValueStreamSection } from '../components/agent-hub/ValueStreamSection';
import { AgentCatalogue } from '../components/agent-hub/AgentCatalogue';
import { getSession } from '../services/auth';
import type { AgentRecord } from '../data/agents';
import '../assets/agent-hub/agent-hub.css';

interface AgentHubPageProps {
  defaultSection?: 'hero' | 'agents' | 'why';
}

export function AgentHubPage({ defaultSection }: AgentHubPageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const containerRef = useRef<HTMLDivElement | null>(null);

  const session = getSession();
  const isLoggedIn = Boolean(session);

  // Scroll to section helper
  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Handle route hash or defaultSection on mount
  useEffect(() => {
    const targetId = defaultSection === 'agents' ? 'agents' : location.hash.replace('#', '');
    if (targetId) {
      setTimeout(() => {
        scrollToSection(targetId);
      }, 100);
    }
  }, [defaultSection, location.hash]);

  const handleSelectAgent = (agent: AgentRecord) => {
    if (agent.id === 'A02' || (agent.status === 'live' && agent.route)) {
      const destination = agent.route || '/app/explainer';
      // If user has an active session, open the workspace directly; otherwise go to login with return state
      if (getSession()) {
        navigate(destination);
      } else {
        navigate('/login', { state: { from: destination } });
      }
    }
  };

  return (
    <div
      ref={containerRef}
      className="agent-hub-root min-h-screen w-full relative"
    >
      {/* Sticky Navigation Bar */}
      <nav className="agent-hub-nav">
        <button
          type="button"
          onClick={() => scrollToSection('hero')}
          className="agent-hub-logo cursor-pointer"
          aria-label="FI360 by Feuji Home"
        >
          FI<b>360</b>
          <small>by Feuji</small>
        </button>

        <div className="agent-hub-nl">
          <button type="button" onClick={() => scrollToSection('why')}>
            Why FI360
          </button>
          <button type="button" onClick={() => scrollToSection('agents')}>
            Agents
          </button>
          {isLoggedIn ? (
            <button
              type="button"
              onClick={() => navigate('/app/explainer')}
              className="agent-hub-pill bg-[#EA580C] text-white font-bold cursor-pointer hover:bg-[#C2410C]"
            >
              Open Workspace →
            </button>
          ) : (
            <button
              type="button"
              onClick={() => navigate('/login', { state: { from: '/app/explainer' } })}
              className="agent-hub-pill bg-[#EA580C] text-white font-bold cursor-pointer hover:bg-[#C2410C]"
            >
              Sign In
            </button>
          )}
        </div>
      </nav>

      {/* Main Landing Page Site Content */}
      <main className="agent-hub-site">
        {/* Animated background ambient glow orbs */}
        <div className="bgfx" aria-hidden="true">
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
          <i />
        </div>

        {/* 1. Hero Section */}
        <HeroSection onExploreClick={() => scrollToSection('agents')} />

        {/* 2. 26 / 6 / 1,000 Ecosystem Statement Section */}
        <EcosystemSection />

        {/* 3. Why FI360 Section */}
        <ValueStreamSection />

        {/* 4. Complete 26 Agent Ecosystem Catalogue */}
        <AgentCatalogue onSelectAgent={handleSelectAgent} />
      </main>

      {/* Footer */}
      <footer className="agent-hub-foot">
        <b>FI 360</b> · An agentic layer for P&amp;C carriers · by Feuji
      </footer>
    </div>
  );
}

export default AgentHubPage;
