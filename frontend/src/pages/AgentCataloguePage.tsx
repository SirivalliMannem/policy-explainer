import React from 'react';
import { AgentHubPage } from './AgentHubPage';

/**
 * Dedicated Agent Catalogue page route (/agents) displaying the FI360
 * 26-agent ecosystem with search and filtering automatically focused.
 */
export function AgentCataloguePage() {
  return <AgentHubPage defaultSection="agents" />;
}

export default AgentCataloguePage;
