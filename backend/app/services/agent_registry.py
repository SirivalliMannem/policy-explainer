"""Maps an agent code to the service that runs that agent."""

from fi360_shared.agents import POLICY_EXPLAINER

from app.core.config import settings

# Compose service name for each live agent. URLs come from the environment.
_SERVICE_NAMES = {
    POLICY_EXPLAINER: "policy-explainer",
}


def agent_base_url(agent_code: str) -> str:
    """Base URL of the service that runs this agent.

    A02 uses AGENT_A02_URL, then AI_SERVICE_URL, so existing local setups keep working.
    """
    if agent_code == POLICY_EXPLAINER:
        return (settings.AGENT_A02_URL or settings.AI_SERVICE_URL).rstrip("/")
    raise KeyError(f"No service is registered for agent {agent_code}")


def registered_agents() -> dict[str, str]:
    """Agent code to base URL for every agent that has a running service."""
    return {code: agent_base_url(code) for code in _SERVICE_NAMES}
