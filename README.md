# Policy Explainer

This is the standalone **Policy Explainer** application.

## Architecture Overview
1. **backend**: Application and API layer.
2. **frontend**: Employee UI.
3. **data_seed**: One-time synthetic data import layer.
4. **PostgreSQL**: Application's database storing policies, forms, and households.

## Relationship with Manager Repository
The manager repository (`coverant-ai-marketing`) is solely the source of synthetic seed logic/data and is **NOT** a runtime dependency.

## LLM Provider Configuration

The Policy Explainer AI Service supports configurable LLM providers selected at runtime via environment variables.

### Current Provider: Groq
By default, the system uses Groq as the primary provider:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b
```

### Alternative Provider: Gemini
Gemini is supported as an alternative provider for future switching:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
```

### Configuration Rules
- Only the selected provider (`LLM_PROVIDER`) requires an API key.
- If `LLM_PROVIDER=groq`, only `GROQ_API_KEY` is required (`GEMINI_API_KEY` can remain empty).
- If `LLM_PROVIDER=gemini`, only `GEMINI_API_KEY` is required (`GROQ_API_KEY` can remain empty).
- Switching providers requires only changing `LLM_PROVIDER` in `.env` and restarting the AI service. No code changes are required.
- If no external API key is configured or if external API requests fail, the system engages its deterministic grounded carrier engine fallback without service interruption.

