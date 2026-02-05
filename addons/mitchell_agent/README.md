# Mitchell/ShopKey "Computer-Using" Agent (Add-on)

This add-on is a Playwright-driven automation agent that:

1. Connects to Autotech AI (on hp6) via the Mitchell API endpoints
2. Polls for pending technical queries from auto shop users
3. Uses a Mitchell/ShopKey Pro web session to retrieve requested technical content
4. Posts results back to Autotech AI, which ingests them into the RAG system

This project assumes the operator has valid portal credentials and permission to automate access.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Autotech AI (hp6)                               │
│                 https://automotive.aurora-sentient.net              │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │   Chat/LLM UI   │──│  Mitchell API   │──│  RAG Vector Store   │ │
│  │  (users ask Qs) │  │  /api/v1/mitchell│  │  (Q&A ingestion)    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
│                              ▲                                      │
│                              │ HTTPS (Cloudflare)                   │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ Mitchell Agent│      │ Mitchell Agent│      │ Mitchell Agent│
│  (Shop A PC)  │      │  (Shop B PC)  │      │  (Shop C PC)  │
│  Windows/Mac  │      │  Windows/Mac  │      │  Windows/Mac  │
└───────────────┘      └───────────────┘      └───────────────┘
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  ShopKeyPro   │      │  ShopKeyPro   │      │  ShopKeyPro   │
│   Browser     │      │   Browser     │      │   Browser     │
└───────────────┘      └───────────────┘      └───────────────┘
```

### Communication Flow (Pull Model)

1. **User asks question** in Autotech AI chat (e.g., "What's the torque spec for 2018 F-150 head bolts?")
2. **Autotech AI** creates a query via `POST /api/v1/mitchell/queries`
3. **Mitchell Agent** (on client PC) polls for work via `GET /api/v1/mitchell/queries/pending`
4. **Mitchell Agent** logs into ShopKeyPro, selects vehicle, searches, extracts content
5. **Mitchell Agent** posts result via `POST /api/v1/mitchell/queries/{id}/result`
6. **Autotech AI** ingests the Q&A into the RAG vector store for future reference
7. **User receives** the technical information (either directly or via RAG retrieval)

## What this includes (and does not)

- Includes: session reuse via Playwright `storage_state`, rate-limited navigation, retries/backoff for network calls.
- Includes: proper logout to avoid leaving sessions open
- Includes: human-like typing and delays to avoid bot detection
- Does **not** include: any attempt to bypass access controls, MFA/CAPTCHA, or "stealth"/bot-evasion tactics.

## Setup

### Python environment

Use the existing `open-webui` conda env on this machine.

### Install dependencies

The main repo already pins Playwright in `backend/requirements.txt`. For local installs:

```bash
pip install -r backend/requirements.txt
playwright install chromium
```

### Configure

Copy the example env file and edit as needed:

```bash
cp addons/mitchell_agent/.env.example addons/mitchell_agent/.env
```

At minimum you must set:

- `MITCHELL_BASE_URL`
- `MITCHELL_LOGIN_URL`
- `MITCHELL_USERNAME`
- `MITCHELL_PASSWORD`
- `AUTOTECH_API_URL` (default: https://automotive.aurora-sentient.net)
- `AGENT_NAME` (e.g., "Mitchell Agent - Joe's Auto Shop")
- Login selectors (see `.env.example`)

Selector discovery:

- By default `AUTO_DISCOVER_SELECTORS=true`, so if vehicle/search/content selectors are missing the agent will attempt to discover them from the live DOM after login and save them to `SELECTORS_PROFILE_PATH`.
- For the first run, set `PLAYWRIGHT_HEADLESS=false` so you can watch the flow and confirm it's on the expected page.

### Run

**Service mode (recommended for production):**
```bash
# Start the agent service that polls Autotech AI for work
./addons/mitchell_agent/start_service.sh --name "Joe's Auto Shop"
```

**Legacy poll loop:**
```bash
python -m addons.mitchell_agent.agent
```

- Single poll cycle then exit: `python -m addons.mitchell_agent.agent --once`
- Run a single local task JSON (no Aurora poll/submit): `python -m addons.mitchell_agent.agent --task-json path/to/task.json`
- Run with logout (for tests): `python -m addons.mitchell_agent.agent --task-json path/to/task.json --logout`

Example `task.json` shape:

```json
{
	"Job_ID": "local-001",
	"Year": "2020",
	"Make": "Toyota",
	"Model": "Camry",
	"Engine": "2.5L",
	"Technical_Query": "starter removal"
}
```

## API Endpoints (Autotech AI Server)

The Mitchell router on Autotech AI provides these endpoints:

### Agent Management
- `POST /api/v1/mitchell/agents/register` - Register a new agent
- `POST /api/v1/mitchell/agents/heartbeat` - Agent heartbeat
- `GET /api/v1/mitchell/agents` - List registered agents (admin)

### Query Management
- `POST /api/v1/mitchell/queries` - Create a new query (from chat)
- `GET /api/v1/mitchell/queries/pending?agent_id=xxx` - Get pending work
- `POST /api/v1/mitchell/queries/{id}/result` - Submit query result
- `GET /api/v1/mitchell/queries/{id}` - Get query status
- `GET /api/v1/mitchell/queries` - List queries (admin)

## Notes

- Session persistence: writes `addons/mitchell_agent/storage_state.json`.
- Output payload: HTML + metadata + downloaded asset file paths (relative to `addons/mitchell_agent/artifacts/{Job_ID}`)
- RAG ingestion: Completed queries are automatically ingested into the `mitchell_automotive_qa` collection
