# Autotech AI Addons Architecture

This document provides a comprehensive overview of the addon system in Autotech AI. Addons extend the core Open WebUI platform with specialized automotive data retrieval capabilities.

## Table of Contents

- [Overview](#overview)
- [Addon Architecture](#addon-architecture)
- [Mitchell Agent](#mitchell-agent)
  - [System Architecture](#system-architecture)
  - [Component Breakdown](#component-breakdown)
  - [Data Flow](#data-flow)
  - [AI Navigation System](#ai-navigation-system)
  - [Scaling Modes](#scaling-modes)
- [AutoDB Agent](#autodb-agent-operation-charm)
- [AI Portal](#ai-portal)
- [Adding New Addons](#adding-new-addons)

---

## Overview

Autotech AI uses a modular addon system to integrate external automotive data sources. Each addon follows a consistent pattern:

1. **Open WebUI Tool** - User-facing interface (Python class pasted into Open WebUI's Tools UI)
2. **Server API** - FastAPI endpoints for request queuing and result handling
3. **Remote Agent** - Background service that performs actual data retrieval
4. **AI Navigator** - LLM-powered autonomous navigation (where applicable)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Autotech AI Platform                               │
│                     https://automotive.aurora-sentient.net                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────┐    ┌─────────────────────────────────────────────────┐   │
│   │    Open WebUI   │    │                   Addons                        │   │
│   │    Chat + LLM   │◄──►│  ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │   │
│   │                 │    │  │  Mitchell   │ │   Autodb    │ │ AI Portal │  │   │
│   └─────────────────┘    │  │    Agent    │ │    Tool     │ │           │  │   │
│                          │  └─────────────┘ └─────────────┘ └───────────┘  │   │
│                          └─────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Addon Architecture

### Directory Structure

```
addons/
├── __init__.py              # Package initialization
├── README.md                # This file
│
├── mitchell_agent/          # ShopKeyPro integration (modern vehicles)
│   ├── agent/               # Remote polling agent
│   ├── ai_navigator/        # Autonomous LLM navigation
│   ├── browser/             # Browser automation utilities
│   ├── server/              # FastAPI queue endpoints
│   ├── openwebui_tool.py    # Open WebUI tool definition
│   └── ...
│
├── autodb_agent/            # Operation CHARM integration (classic vehicles 1982-2014)
│   ├── config.py            # Configuration with dotenv support
│   ├── navigator.py         # AI-powered navigation orchestrator
│   ├── llm_client.py        # Gemini/Ollama LLM calls
│   ├── page_parser.py       # HTTP/HTML parsing
│   ├── models.py            # Data models
│   ├── tools.py             # Click/extract/go_back tools
│   ├── logging_config.py    # File logging setup
│   └── openwebui_tool.py    # Open WebUI tool
│
└── ai_portal/               # Future AI data portal
    ├── adapters/            # Data source adapters
    └── tools/               # Tool implementations
```

---

## Mitchell Agent

The Mitchell Agent is the primary addon, providing access to ShopKeyPro/Mitchell automotive technical data. It implements a "remote polling" architecture where agents run at customer sites and poll the central server for work.

### System Architecture

```
┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────────────────┐
│   Open WebUI        │     │  Autotech AI Server  │     │  Customer Site              │
│   (User Query)      │     │  (Request Queue)     │     │  (AI Employee)              │
│                     │     │                      │     │                             │
│  "Get fluid specs   │────►│  POST /mitchell      │     │  ┌─────────────────────┐   │
│   for my F-150"     │     │       /request       │     │  │ Polling Agent       │   │
│                     │     │                      │◄────│  │  GET /pending       │   │
│                     │     │                      │     │  └──────────┬──────────┘   │
│                     │     │                      │     │             │              │
│                     │     │                      │     │  ┌──────────▼──────────┐   │
│                     │     │                      │     │  │ AI Navigator        │   │
│                     │     │                      │     │  │ (Gemini/Ollama)     │   │
│                     │     │                      │     │  └──────────┬──────────┘   │
│                     │     │                      │     │             │              │
│                     │◄────│  GET /mitchell/wait  │◄────│  ┌──────────▼──────────┐   │
│  "Oil: 8.8 qts..."  │     │                      │     │  │ Chrome + Playwright │   │
│                     │     │  POST /mitchell      │◄────│  │ → ShopKeyPro        │   │
│                     │     │       /result        │     │  └─────────────────────┘   │
└─────────────────────┘     └──────────────────────┘     └─────────────────────────────┘
```

### Component Breakdown

#### Server Side (`server/`)

| File | Purpose |
|------|---------|
| `router.py` | FastAPI endpoints for request queue management |
| `queue.py` | In-memory request/result queue (swap for Redis in production) |
| `models.py` | Pydantic models: `MitchellRequest`, `MitchellResult`, `VehicleInfo` |
| `navigation.py` | Server-side navigation decision helpers |

**Key Endpoints:**
- `POST /api/mitchell/request` - Create new request (tool calls this)
- `GET /api/mitchell/pending/{shop_id}` - Get pending requests (agent polls this)
- `POST /api/mitchell/claim/{request_id}` - Claim request for processing
- `POST /api/mitchell/result/{request_id}` - Submit result
- `GET /api/mitchell/wait/{request_id}` - Long-poll for result

#### Agent Side (`agent/`)

| File | Purpose |
|------|---------|
| `pooled_agent.py` | Main agent service with worker pool support |
| `worker_pool.py` | Chrome worker lifecycle management |
| `config.py` | Configuration loading from `.env` |
| `request_handler.py` | Request processing logic |
| `service.py` | Legacy single-worker service |

**Scaling Modes:**
- `single` - One Chrome instance, requests queue up
- `pool` - Fixed pool of N workers with auto-scaling
- `ondemand` - Spawn Chrome per request, destroy when done

#### AI Navigator (`ai_navigator/`)

The autonomous navigation system uses LLMs to navigate ShopKeyPro intelligently:

| File | Purpose |
|------|---------|
| `an_navigator.py` | Main navigator class |
| `an_models.py` | LLM model interactions (Gemini, Ollama) |
| `an_prompts.py` | System prompt and user message builders |
| `an_tools.py` | Tool implementations (click, extract, capture_diagram) |
| `an_config.py` | Configuration and API keys |
| `element_extractor.py` | DOM element extraction for AI visibility |

**Supported Models:**
- Gemini: `gemini-2.5-flash` (default), `gemini-2.5-pro`
- Ollama: `llama3.1:8b`, `qwen3:8b`

**AI Navigation Philosophy:**
> "The AI is just a brain. We provide: Eyes (page state), Fingers (tools), Memory (path taken)."

The navigator doesn't build "fences" to prevent bad actions—instead, it provides rich context so the AI makes good decisions naturally.

#### Browser Automation (`browser/`)

| File | Purpose |
|------|---------|
| `vehicle_selector.py` | Vehicle selection UI automation |
| `auth.py` | Login/logout handling |
| `context.py` | Browser context management |
| `extraction.py` | Data extraction from pages |
| `modal.py` | Modal dialog handling |

### Data Flow

1. **User Query** → Chat sends query to LLM with Mitchell tool available
2. **Tool Invocation** → LLM calls `query_autonomous(vehicle, goal)` 
3. **Request Created** → Tool posts to `/api/mitchell/request`
4. **Agent Claims** → Polling agent gets work via `/api/mitchell/pending`
5. **AI Navigation** → Navigator uses LLM to find and extract data
6. **Result Submitted** → Agent posts to `/api/mitchell/result`
7. **Response Returned** → Tool receives data, formats for user

### AI Navigation System

The autonomous navigator gives an LLM (Gemini/Ollama) full control over browser navigation:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        Autonomous Navigation Loop                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌────────────────┐     ┌─────────────────┐     ┌─────────────────────────┐   │
│   │ Page State     │────►│ Build User      │────►│ LLM (Gemini/Ollama)     │   │
│   │ - Elements     │     │ Message         │     │ - System Prompt         │   │
│   │ - Modal status │     │ - Visible items │     │ - Navigation paths      │   │
│   │ - Page text    │     │ - Path taken    │     │ - Tool definitions      │   │
│   └────────────────┘     └─────────────────┘     └───────────┬─────────────┘   │
│                                                              │                  │
│   ┌────────────────┐     ┌─────────────────┐                │                  │
│   │ Execute Tool   │◄────│ Parse Response  │◄───────────────┘                  │
│   │ - click()      │     │ - Extract tool  │                                   │
│   │ - extract()    │     │ - Validate args │                                   │
│   │ - capture()    │     └─────────────────┘                                   │
│   │ - done()       │                                                           │
│   └────────────────┘                                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Available Tools:**
| Tool | Purpose |
|------|---------|
| `click(element_id, reason)` | Click numbered element |
| `click_text(text, reason)` | Click by text match |
| `extract(data)` | Extract and return data (exits loop) |
| `capture_diagram(description)` | Capture SVG diagrams as images |
| `expand_all()` | Expand collapsed tree items |
| `prior_page()` | Navigate back |
| `collect(label, data)` | Store item for multi-step collection |
| `done(summary)` | Return all collected items |

### Scaling Modes

The agent supports three scaling modes via `MITCHELL_SCALING_MODE`:

#### Single Mode (Default)
```
┌─────────────────────────────────┐
│     Single Chrome Worker        │
│                                 │
│  Request 1 ──► [Processing]     │
│  Request 2 ──► [Queued]         │
│  Request 3 ──► [Queued]         │
│                                 │
└─────────────────────────────────┘
```
- One Chrome instance
- Requests queue up
- Lowest memory usage
- Best for development

#### Pool Mode
```
┌─────────────────────────────────────────────────────┐
│              Worker Pool (min=1, max=3)             │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │  Worker 1   │  │  Worker 2   │  │  Worker 3   │ │
│  │  Port 9222  │  │  Port 9223  │  │  Port 9224  │ │
│  │  [Request1] │  │  [Request2] │  │  [Idle]     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                     │
│  - Workers stay warm (fast response)                │
│  - Scale up/down based on demand                    │
│  - Higher memory usage (500MB-1GB per worker)       │
└─────────────────────────────────────────────────────┘
```

#### On-Demand Mode (Recommended for Production)
```
┌─────────────────────────────────────────────────────┐
│              On-Demand Workers                      │
│                                                     │
│  Request arrives:                                   │
│    1. Spawn Chrome worker                           │
│    2. Login to ShopKeyPro                           │
│    3. Process request                               │
│    4. Return result                                 │
│    5. Logout and destroy worker                     │
│                                                     │
│  - No idle resource usage                           │
│  - Cold start penalty (~10-15s for login)           │
│  - Best for variable/low traffic                    │
└─────────────────────────────────────────────────────┘
```

---

## AutoDB Agent (Operation CHARM)

The AutoDB Agent provides AI-powered access to Operation CHARM - a collection of classic automotive service manuals covering vehicles from 1982-2014. It uses an autonomous LLM navigator to find and extract technical specifications, procedures, and diagrams.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AutoDB Agent Architecture                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────┐     ┌──────────────────────────────────────────────────┐ │
│   │ Open WebUI Tool │────►│              AutoDB Navigator                    │ │
│   │                 │     │                                                  │ │
│   │ autodb(         │     │  ┌─────────────┐    ┌─────────────────────────┐ │ │
│   │   year, make,   │     │  │ Page Parser │◄──►│ Operation CHARM Server  │ │ │
│   │   model, query) │     │  │ (HTTP/HTML) │    │ /autodb/* static pages  │ │ │
│   └─────────────────┘     │  └─────────────┘    └─────────────────────────┘ │ │
│                           │         │                                        │ │
│                           │  ┌──────▼──────┐    ┌─────────────────────────┐ │ │
│                           │  │ LLM Client  │───►│ Ollama (qwen2.5:7b)     │ │ │
│                           │  │             │    │ or Gemini 2.0 Flash     │ │ │
│                           │  └─────────────┘    └─────────────────────────┘ │ │
│                           │                                                  │ │
│                           └──────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Differences from Mitchell Agent

| Aspect | Mitchell Agent | AutoDB Agent |
|--------|---------------|--------------|
| Data Source | ShopKeyPro (live portal) | Operation CHARM (static HTML) |
| Authentication | Required (browser cookies) | None (public data) |
| Execution | Remote polling agent | Direct HTTP from server |
| Browser | Chrome + Playwright | None (HTML parsing) |
| Coverage | Modern vehicles (2024+) | Classic vehicles (1982-2014) |

### Components

| File | Purpose |
|------|---------|
| `config.py` | Configuration loading from `.env` with dotenv support |
| `navigator.py` | Main navigation orchestrator |
| `llm_client.py` | LLM API calls (Gemini, Ollama) with retry logic |
| `page_parser.py` | HTTP fetching and HTML parsing |
| `models.py` | Data models (Vehicle, PageState, NavigationResult) |
| `tools.py` | Tool implementations (click, extract, go_back) |
| `prompts.py` | System prompt and message builders |
| `logging_config.py` | File logging setup (/tmp/autodb_agent.log) |
| `openwebui_tool.py` | Open WebUI tool definition |

### Configuration

Create `.env` in the `autodb_agent/` directory:

```bash
# LLM Settings
AUTODB_MODEL=qwen2.5:7b-instruct    # or gemini-2.0-flash-lite

# Ollama Settings (for local LLM)
AUTODB_OLLAMA_URL=http://localhost:11434
AUTODB_OLLAMA_NUM_CTX=12000
AUTODB_OLLAMA_NUM_PREDICT=1024

# LLM Parameters
AUTODB_LLM_TEMPERATURE=0.1
AUTODB_LLM_MAX_RETRIES=3
AUTODB_LLM_RETRY_BASE_DELAY=2.0
AUTODB_LLM_DELAY=0.2

# Navigation
AUTODB_MAX_STEPS=15
AUTODB_MAX_LINKS=50
```

### Deployment Notes

**Critical (important)**: The Open WebUI tool code is stored in the **database**, not automatically reloaded from the filesystem. Each *tool* (addon) has its own `tool` row in the DB (for example, `id = 'autodb'` for the Autodb addon). When you change an `openwebui_tool.py` file you must update the corresponding DB row and restart the service.

**Safe update workflow (recommended)**

1. **Back up the database first** (do this before any edits):

```bash
cp backend/data/webui.db backend/data/webui.db.$(date +%Y%m%dT%H%M%S).bak
```

2. **List tools in DB** to find the `id` you need to update:

```bash
sqlite3 backend/data/webui.db "SELECT id, name FROM tool;"
```

3. **Update the specific tool** from the addon file (example for `autodb`):

```python
import sqlite3
with open('addons/autodb_agent/openwebui_tool.py', 'r') as f:
    content = f.read()
conn = sqlite3.connect('backend/data/webui.db')
cursor = conn.cursor()
# Confirm which tool id you plan to update
print(cursor.execute("SELECT id, name FROM tool WHERE id = ?", ('autodb',)).fetchone())
cursor.execute('UPDATE tool SET content = ? WHERE id = ?', (content, 'autodb'))
conn.commit()
conn.close()
```

4. **Verify** the update by re-querying the DB and/or inspecting the tool in the Open WebUI Tool Editor.

5. **Restart** the `autotech_ai` service (or the tool host) to ensure the new code is loaded.

**Batch updates**: If you have many addons each with their own `openwebui_tool.py`, you can script an update that iterates over addon folders and updates the DB row for each known tool id. Always back up the DB before running a batch update.

**Why this matters**: If you edit the filesystem `openwebui_tool.py` but forget to update the DB, the UI will continue to execute the old code stored in the DB — this is a common source of "it works locally but not in the UI" bugs.

**Rollback**: If something breaks, restore from the backup created above and restart the service:

```bash
cp backend/data/webui.db.YOUR_BACKUP backend/data/webui.db
systemctl restart autotech_ai || ./restart.sh
```

Then re-open the Open WebUI tool editor to verify restored behavior.


### Logging

Logs are written to `/tmp/autodb_agent.log`:
- Navigation steps and LLM decisions
- Timing breakdown (LLM calls, HTTP fetches)
- Token usage and billing records
- Errors and retries

```bash
tail -f /tmp/autodb_agent.log
```

### Token Billing

AutoDB tracks token usage and records it to the user's account via `record_usage_event()` with `token_source="autodb_navigator"`.

---

## AI Portal

The AI Portal addon (under development) provides a unified interface for multiple automotive data sources.

### Directory Structure

```
ai_portal/
├── adapters/              # Data source adapters
│   └── __pycache__/       # (implementations pending)
└── tools/                 # Tool implementations
    └── __pycache__/       # (implementations pending)
```

### Planned Features

- Unified query interface across multiple data sources
- Adapter pattern for easy source integration
- Caching and deduplication
- Source priority and fallback logic

---

## Adding New Addons

### Step 1: Create Directory Structure

```bash
mkdir -p addons/new_addon/{agent,server,browser}
touch addons/new_addon/__init__.py
touch addons/new_addon/openwebui_tool.py
```

### Step 2: Define Models (`server/models.py`)

```python
from pydantic import BaseModel, Field
from typing import Optional

class NewAddonRequest(BaseModel):
    """Request model for new addon."""
    query: str
    vehicle_year: Optional[int] = None
    # ... additional fields

class NewAddonResult(BaseModel):
    """Result model for new addon."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
```

### Step 3: Create Server Endpoints (`server/router.py`)

```python
from fastapi import APIRouter
from .models import NewAddonRequest, NewAddonResult

router = APIRouter(prefix="/api/new_addon", tags=["new_addon"])

@router.post("/request")
async def create_request(payload: NewAddonRequest):
    """Create new request."""
    # Implementation
    pass
```

### Step 4: Create Open WebUI Tool (`openwebui_tool.py`)

```python
"""
title: New Addon Tool
author: autotech-ai
version: 1.0.0
description: Description of the new addon.
"""

from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        API_BASE_URL: str = Field(default="https://automotive.aurora-sentient.net")
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def query(self, query: str) -> str:
        """Query the new addon."""
        # Implementation
        pass
```

### Step 5: Register with Server

Add router to main application in `backend/open_webui/main.py`:

```python
from addons.new_addon.server.router import router as new_addon_router
app.include_router(new_addon_router)
```

### Step 6: Documentation

Create `README.md` in addon directory with:
- Purpose and capabilities
- Configuration options
- Usage examples
- Architecture diagrams

---

## Configuration

### Environment Variables

All addons use environment variables for configuration. Key variables:

```bash
# Mitchell Agent
MITCHELL_SHOP_ID=your_shop_id
MITCHELL_USERNAME=shopkeypro_user
MITCHELL_PASSWORD=shopkeypro_pass
MITCHELL_SCALING_MODE=ondemand  # single|pool|ondemand
MITCHELL_HEADLESS=true          # Run Chrome headless

# AI Navigator
GEMINI_API_KEY=your_gemini_key  # Or use ~/gary_gemini_api_key file
AN_MODEL=gemini-2.5-flash       # Default model

# Autodb
AUTODB_BASE_URL=http://automotive.aurora-sentient.net/autodb
```

### Systemd Service

For production, run addons as systemd services:

```ini
# /etc/systemd/system/mitchell-agent.service
[Unit]
Description=Mitchell Agent
After=network.target

[Service]
Type=simple
User=drawson
WorkingDirectory=/prod/autotech_ai
Environment=DISPLAY=:99
ExecStartPre=/bin/bash -c 'if ! pgrep -x Xvfb > /dev/null; then Xvfb :99 -screen 0 1920x1080x24 & sleep 2; fi'
ExecStart=/home/drawson/anaconda3/bin/conda run -n open-webui --no-capture-output python -m addons.mitchell_agent.agent.pooled_agent
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Debugging

### Logs

| Component | Log Location |
|-----------|-------------|
| Mitchell Agent | journalctl -u mitchell-agent |
| AI Navigator | `/tmp/ai_navigator.log` |
| Navigator Debug | `/tmp/navigator_debug.log` |
| Screenshots | `/tmp/navigator_screenshots/` |

### Testing

```bash
# Test end-to-end chat flow
python addons/mitchell_agent/test_chat_e2e.py

# Test autonomous navigation
python -m addons.mitchell_agent.ai_navigator.autonomous_navigator "fluid capacities"

# Test with specific model
python -m addons.mitchell_agent.ai_navigator -m gemini-2.5-flash "oil capacity"
```

---

## Security Considerations

1. **Credentials** - Never commit credentials. Use `.env` files (gitignored).
2. **Session Management** - Always logout after tasks to prevent session accumulation.
3. **Rate Limiting** - Implement delays between requests to avoid detection.
4. **Legal Classification** - Agents are "AI Employees" using customer credentials locally.

---

## Future Development

- [ ] Redis-backed queue for distributed deployments
- [ ] Additional data source adapters (AllData, MOTOR, etc.)
- [ ] Caching layer for repeated queries
- [ ] Usage analytics and billing integration
- [ ] Multi-tenant support with isolated worker pools
