import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Search, X, CheckCircle2, Clock, Sparkles } from 'lucide-react';
import { VALUE_STREAMS, ALL_AGENTS, type AgentRecord } from '../../data/agents';
import { AgentCard } from './AgentCard';

interface AgentCatalogueProps {
  onSelectAgent: (agent: AgentRecord) => void;
}

export function AgentCatalogue({ onSelectAgent }: AgentCatalogueProps) {
  const treeRef = useRef<HTMLDivElement | null>(null);
  const [isInView, setIsInView] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStreamId, setSelectedStreamId] = useState<string>('ALL');
  const [modalAgent, setModalAgent] = useState<AgentRecord | null>(null);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setIsInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true);
        }
      },
      { threshold: 0.1 }
    );

    if (treeRef.current) {
      observer.observe(treeRef.current);
      const rect = treeRef.current.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        setIsInView(true);
      }
    }

    return () => observer.disconnect();
  }, []);

  // Handle modal keyboard dismiss (Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && modalAgent) {
        setModalAgent(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [modalAgent]);

  // Handle agent click
  const handleAgentClick = (agent: AgentRecord) => {
    if (agent.status === 'live') {
      onSelectAgent(agent);
    } else {
      setModalAgent(agent);
    }
  };

  // Filter streams and agents based on search query and stream filter
  const filteredStreams = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return VALUE_STREAMS.map((stream) => {
      // Check stream filter
      if (selectedStreamId !== 'ALL' && stream.id !== selectedStreamId) {
        return { ...stream, agents: [] };
      }

      if (!query) {
        return stream;
      }

      const matchingAgents = stream.agents.filter(
        (agent) =>
          agent.id.toLowerCase().includes(query) ||
          agent.name.toLowerCase().includes(query) ||
          agent.description.toLowerCase().includes(query)
      );

      return {
        ...stream,
        agents: matchingAgents,
      };
    });
  }, [searchQuery, selectedStreamId]);

  const totalMatchingAgents = useMemo(() => {
    return filteredStreams.reduce((acc, stream) => acc + stream.agents.length, 0);
  }, [filteredStreams]);

  return (
    <section className="agent-hub-agents" id="agents" aria-label="FI360 Agent Catalogue">
      <div className="agent-hub-wrap">
        {/* Header */}
        <div className="agent-hub-head">
          <p className="eb">MEET THE AGENTS</p>
          <h2>One platform. Six solutions.</h2>
          <p className="l">
            Every agent sits under the solution it serves. Click an agent to open it. Policy
            Explainer (A02) is live.
          </p>

          {/* Search & Stream Filter Controls */}
          <div className="mt-8 max-w-2xl mx-auto space-y-4">
            <div className="relative">
              <Search
                className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#94a3b8]"
                aria-hidden="true"
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search 26 agents by name, ID (e.g., A02, FNOL, Underwriting)…"
                aria-label="Search agents"
                className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-[#cbd5e1] bg-white text-[14px] text-[#0F2A43] placeholder-[#94a3b8] shadow-sm transition-all focus:border-[#EA580C] focus:outline-none focus:ring-2 focus:ring-[#EA580C]/20"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear search"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#94a3b8] hover:text-[#0F2A43] p-1"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            {/* Value stream pills */}
            <div
              className="flex items-center justify-center gap-1.5 flex-wrap text-[12.5px]"
              role="tablist"
              aria-label="Filter by solution"
            >
              <button
                type="button"
                role="tab"
                aria-selected={selectedStreamId === 'ALL'}
                onClick={() => setSelectedStreamId('ALL')}
                className={`px-3 py-1 rounded-full font-medium transition-colors cursor-pointer ${
                  selectedStreamId === 'ALL'
                    ? 'bg-[#0F2A43] text-white shadow-xs'
                    : 'bg-white text-[#475569] border border-[#e2e8f0] hover:bg-[#f8fafc]'
                }`}
              >
                All Solutions ({ALL_AGENTS.length})
              </button>
              {VALUE_STREAMS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  role="tab"
                  aria-selected={selectedStreamId === s.id}
                  onClick={() => setSelectedStreamId(s.id)}
                  className={`px-3 py-1 rounded-full font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                    selectedStreamId === s.id
                      ? 'bg-[#EA580C] text-white shadow-xs'
                      : 'bg-white text-[#475569] border border-[#e2e8f0] hover:bg-[#f8fafc]'
                  }`}
                >
                  <span>{s.icon}</span>
                  <span>{s.shortName}</span>
                </button>
              ))}
            </div>

            {searchQuery && (
              <p className="text-[13px] text-[#64748B]">
                Showing {totalMatchingAgents} of {ALL_AGENTS.length} agents
              </p>
            )}
          </div>
        </div>

        {/* Tree Ecosystem Layout */}
        <div ref={treeRef} className={`tree ${isInView ? 'in' : ''}`}>
          {/* Tree Root */}
          <div className="root">
            <div className="rb">
              FI <b>360</b>
              <small>26 agents · 6 solutions</small>
            </div>
            <div className="rl" aria-hidden="true" />
          </div>

          {/* 6 Value Stream Branches */}
          <div className="branches">
            {filteredStreams.map((stream, k) => {
              const accent = k % 2 ? '#2563EB' : '#F97316';
              return (
                <div
                  key={stream.id}
                  className="br"
                  style={
                    {
                      '--c': accent,
                      '--k': k,
                    } as React.CSSProperties
                  }
                >
                  {/* Solution Box Header */}
                  <div className="sb">
                    <div className="ic" style={{ background: stream.tagColor }}>
                      {stream.icon}
                    </div>
                    <span className="id">{stream.id}</span>
                    <b>{stream.name}</b>
                    <small>{stream.executive}</small>
                  </div>

                  {/* Agent Cards */}
                  <div className="al">
                    {stream.agents.length === 0 ? (
                      <p className="text-[12px] text-[#94a3b8] italic py-3">No matching agents</p>
                    ) : (
                      stream.agents.map((agent, i) => (
                        <AgentCard
                          key={agent.id}
                          agent={agent}
                          index={i}
                          accentColor={accent}
                          onClick={handleAgentClick}
                        />
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Agent Detail Modal (for non-live agents preview) */}
      {modalAgent && (
        <div
          className="agent-modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModalAgent(null);
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="agent-modal-title"
        >
          <div className="agent-modal-card">
            <button
              type="button"
              className="agent-modal-close"
              onClick={() => setModalAgent(null)}
              aria-label="Close dialog"
            >
              ✕
            </button>

            <div className="flex items-center gap-2 mb-1">
              <span className="cd">{modalAgent.id}</span>
              <span className="text-[#94a3b8]">·</span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                <Clock className="h-3 w-3" />
                Coming Soon
              </span>
            </div>

            <h3 id="agent-modal-title">{modalAgent.name}</h3>

            <p className="msl">
              <strong>{modalAgent.streamId} {modalAgent.streamName}</strong>
              <br />
              <span className="text-[12.5px] text-[#64748B]">Sponsor: {modalAgent.executive}</span>
            </p>

            <p className="desc">{modalAgent.description}</p>

            <div className="mt-4 pt-4 border-t border-[#f1f5f9]">
              <h4 className="text-[12.5px] font-bold uppercase tracking-wider text-[#64748B] mb-2.5">
                Core Autonomous Capabilities
              </h4>
              <ul className="space-y-1.5 text-[13px] text-[#334155]">
                {modalAgent.capabilities.map((cap) => (
                  <li key={cap} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-[#EA580C] shrink-0 mt-0.5" />
                    <span>{cap}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="mt-6 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[12px] text-[#64748B]">
                <Sparkles className="h-3.5 w-3.5 text-[#F97316]" />
                <span>Roadmap delivery Phase 2</span>
              </div>
              <button
                type="button"
                onClick={() => setModalAgent(null)}
                className="px-4 py-2 rounded-xl bg-[#0F2A43] text-white text-[13px] font-semibold hover:bg-[#16385A] transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
