import React from 'react';
import type { AgentRecord } from '../../data/agents';

interface AgentCardProps {
  agent: AgentRecord;
  index: number;
  accentColor: string;
  onClick: (agent: AgentRecord) => void;
}

export function AgentCard({ agent, index, accentColor, onClick }: AgentCardProps) {
  const isLive = agent.status === 'live';

  return (
    <button
      type="button"
      className={`ag ${isLive ? 'live' : ''}`}
      style={
        {
          '--i': index,
          '--c': accentColor,
        } as React.CSSProperties
      }
      onClick={() => onClick(agent)}
      aria-label={`${agent.id}: ${agent.name}${isLive ? ' (Live Agent)' : ' (Details)'}`}
      title={isLive ? `Launch ${agent.name} workspace` : `View details for ${agent.name}`}
    >
      <b>{agent.id}</b>
      <span>{agent.name}</span>
      {isLive && <i className="live-badge">LIVE</i>}
    </button>
  );
}
