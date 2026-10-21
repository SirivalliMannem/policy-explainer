# Policy Explainer

This is the standalone **Policy Explainer** application — an enterprise insurance intelligence platform providing evidence-grounded policy answers, citations, and customer policy management.

---

## Architecture Overview

The system runs entirely via Docker Compose across 4 containerized services:

1. **`frontend`** (Port `5173`): React 18, Vite, TypeScript, and Tailwind CSS employee UI.
2. **`backend`** (Port `8000`): FastAPI application handling authorization, customer/policy data, conversation history, the Evidence Ledger, and routing to agent services.
3. **`policy-explainer`** (Port `8001`): The A02 Policy Explainer agent. FastAPI service for RAG retrieval, query interpretation, guardrails, and LLM answer generation. Each future agent is its own service under `agents/`.
4. **`postgres`** (Host Port `5436`, Container Port `5432`): PostgreSQL 16 database storing policies, attached forms, endorsements, schedules, claims, billing, and conversation audits.

Shared carrier models and agent codes live in `shared/` and are imported by the backend and every agent.

---

## Prerequisites

- **Docker Desktop** (or Docker Engine 24+ with Docker Compose v2+)
- **Git**
- Optional (for local non-container development only): Node.js 20+, Python 3.11+

---

## Quick Start (Docker Deployment)

On any developer laptop, clone the repository and start the complete application with Docker Compose. **No separate terminal running `npm run dev` is required.**

### 1. Environment Configuration

Copy the example environment configuration to create `.env`:

```bash
# On Linux/macOS
cp .env.example .env

# On Windows PowerShell
Copy-Item .env.example .env
```

Edit `.env` and set your preferred LLM provider API key (e.g. Groq):

```env
# Database (Docker container networking)
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/policy_explainer

# Agent services. AI_SERVICE_URL is the fallback for A02.
AI_SERVICE_URL=http://policy-explainer:8001
AGENT_A02_URL=http://policy-explainer:8001

# LLM Provider Configuration
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Frontend API URL (accessed from your host browser)
VITE_API_BASE_URL=http://localhost:8000
```

> **Note:** If no LLM API key is configured or if an external provider API limit is reached, the application automatically engages its deterministic `grounded-carrier-engine` fallback without crashing or interrupting service.

### 2. Build and Start the Application

Run Docker Compose to build images and launch all services in detached mode:

```bash
docker compose up -d --build
```

Docker Compose will automatically:
1. Initialize the PostgreSQL 16 container and wait until healthy.
2. Build and launch `policy-explainer` (agent A02) and wait until its healthcheck passes (`/health`).
3. Build and launch `backend`, execute database migrations and data seeding on startup, and wait until healthy (`/health`).
4. Build and launch `frontend` binding to `0.0.0.0:5173`.

### 3. Verify Container Health

Check that all four containers report `healthy`:

```bash
docker compose ps
```

Expected output:
```text
NAME                          IMAGE                             STATUS
policy-explainer-postgres     postgres:16-alpine                Up (healthy)
policy-explainer-a02          policy-explainer-policy-explainer   Up (healthy)
policy-explainer-backend      policy-explainer-backend             Up (healthy)
policy-explainer-frontend     policy-explainer-frontend         Up (healthy)
```

---

## Accessing the Application

- **Frontend Web UI**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Policy Explainer Health Check**: [http://localhost:8001/health](http://localhost:8001/health)
- **PostgreSQL Database**: `localhost:5436` (User: `postgres`, Password: `postgres`, DB: `policy_explainer`)

---

## Simulated Employee Login

For development and testing, use any of the simulated employee directory accounts:

| Email | Employee ID | Name | Role |
|---|---|---|---|
| `agent@feuji.com` | `EMP-1002` | Dev Service Agent | Customer Service (`csr`) |
| `manager@feuji.com` | `EMP-1001` | Dev Manager | Manager (`manager`) |
| `adjuster@feuji.com` | `EMP-1003` | Dev Claims Adjuster | Adjuster (`adjuster`) |
| `auditor@feuji.com` | `EMP-1004` | Dev Auditor | Auditor (`auditor`) |

*Password: Any non-empty string (e.g. `password123`).*

---

## Troubleshooting

### Port Conflicts
If any required host port is already bound on your system:
- **Port 5173 (Frontend)**: Ensure no orphaned `node` or `vite` dev processes are running on your host (`Get-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess | Stop-Process` on Windows PowerShell).
- **Port 8000 (Backend)** / **8001 (Policy Explainer)**: Check for background Python or Uvicorn instances.
- **Port 5436 (PostgreSQL Host Port)**: Configured intentionally as `5436:5432` to prevent conflicts with local PostgreSQL instances that run on default port 5432.

### Viewing Container Logs
To view live logs from any individual service:
```bash
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f policy-explainer
```

### Rebuilding an Individual Service
If you make code edits to the frontend, backend, or an agent:
```bash
docker compose up -d --build frontend
```

---

## Shutdown Commands

To stop all services:
```bash
docker compose down
```

To stop all services and delete database volumes (complete clean slate):
```bash
docker compose down -v
```
