# Autotech AI Developer Guide

This guide provides comprehensive documentation for developers working on Autotech AI, with particular focus on the addon system and automotive data integration.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Server Environments](#server-environments)
   - [Production Server (poweredge1)](#production-server-poweredge1)
   - [Backup Server (poweredge2)](#backup-server-poweredge2)
   - [Legacy Server (hp6)](#legacy-server-hp6---deprecated)
   - [Development Server (localhost)](#development-server-localhost)
4. [Website Architecture](#website-architecture)
5. [Addons System](#addons-system)
   - [Mitchell Agent](#mitchell-agent-deep-dive)
   - [AutoDB Agent](#autodb-agent-operation-charm)
   - [AI Portal](#ai-portal)
6. [Development Setup](#development-setup)
7. [Testing](#testing)
8. [Deployment](#deployment)
9. [Debugging](#debugging)
10. [Best Practices](#best-practices)

---

## Project Overview

Autotech AI is a fork of Open WebUI customized for automotive technicians. It provides:

- **AI Chat Interface** - Conversational access to automotive technical data
- **Tool Integration** - LLM tools that retrieve live data from automotive portals
- **RAG System** - Stored automotive knowledge for quick retrieval
- **Billing System** - Usage-based billing for commercial operation

### Key Technologies

| Layer | Technology |
|-------|------------|
| Frontend | SvelteKit, TailwindCSS |
| Backend | FastAPI (Python 3.11) |
| Database | SQLite (dev), PostgreSQL (prod) |
| LLM Integration | Ollama, OpenAI, Google Gemini |
| Browser Automation | Playwright + Chrome CDP |
| AI Navigation | Gemini 2.5 Flash, Ollama |

---

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                AUTOTECH AI PLATFORM                                 │
│                         https://automotive.aurora-sentient.net                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐ │
│  │      Frontend       │    │       Backend       │    │        Addons          │ │
│  │     (SvelteKit)     │◄──►│      (FastAPI)      │◄──►│  ┌─────────────────┐   │ │
│  │                     │    │                     │    │  │ Mitchell Agent  │   │ │
│  │  - Chat UI          │    │  - /api/chat        │    │  ├─────────────────┤   │ │
│  │  - Model Selector   │    │  - /api/models      │    │  │ AutoDB Agent    │   │ │
│  │  - Knowledge Base   │    │  - /api/mitchell    │    │  ├─────────────────┤   │ │
│  │  - Admin Panel      │    │  - /api/billing     │    │  │ AI Portal       │   │ │
│  └─────────────────────┘    └─────────────────────┘    │  └─────────────────┘   │ │
│                                                         └─────────────────────────┘ │
│                                                                                     │
│                              ┌─────────────────────┐                               │
│                              │   External Services │                               │
│                              │  ┌───────────────┐  │                               │
│                              │  │ Ollama        │  │                               │
│                              │  │ Google Gemini │  │                               │
│                              │  │ OpenAI        │  │                               │
│                              │  │ Cloudflare    │  │                               │
│                              │  └───────────────┘  │                               │
│                              └─────────────────────┘                               │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

                                          │
                                          │ Cloudflare Tunnel
                                          ▼

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              REMOTE AGENT (Customer Site)                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐ │
│  │   Polling Agent     │───►│   AI Navigator      │───►│   Chrome + Playwright   │ │
│  │                     │    │   (Gemini/Ollama)   │    │                         │ │
│  │  GET /pending       │    │                     │    │  → ShopKeyPro Portal    │ │
│  │  POST /result       │    │  - click()          │    │  → Login & Navigate     │ │
│  │                     │    │  - extract()        │    │  → Extract Data         │ │
│  └─────────────────────┘    │  - capture_diagram()│    │  → Logout               │ │
│                              └─────────────────────┘    └─────────────────────────┘ │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow

```
User → Chat UI → LLM → Tool Call → Server Queue → Remote Agent → ShopKeyPro → Result → User
```

1. User asks: "What's the oil capacity for a 2018 Ford F-150 5.0L?"
2. LLM (Gemini Pro) decides to call `query_autonomous` tool
3. Tool creates request in server queue
4. Remote agent polls and claims request
5. AI Navigator opens ShopKeyPro, selects vehicle, extracts data
6. Agent posts result back to server
7. Tool returns formatted data to LLM
8. LLM presents answer to user

---

## Server Environments

### Production Server (poweredge1)

The production environment runs on a dedicated server nicknamed "poweredge1".

| Property | Value |
|----------|-------|
| **Hostname** | poweredge1 |
| **IP Address** | 192.168.50.66 |
| **Public URL** | https://automotive.aurora-sentient.net |
| **OS** | Ubuntu 24.04 LTS |
| **Code Path** | `/prod/autotech_ai` |
| **Conda Environment** | `open-webui` (Python 3.11) |

#### Production Services

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION SERVER (poweredge1)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Internet ──► Cloudflare Tunnel ──► Nginx (:80) ──┬──► Open WebUI (:8080)     │
│                                                    │    (FastAPI + SvelteKit)  │
│                                                    │                           │
│                                                    ├──► Autodb (:3001)         │
│                                                    │    (Operation Charm)      │
│                                                    │                           │
│                                                    └──► Mitchell Agent         │
│                                                         (Pooled browser agent) │
│                                                                                 │
│  ┌───────────────┬─────────────────────┬───────────────────────────────────┐   │
│  │ cloudflared   │ nginx               │ autotech_ai.service              │   │
│  │ Tunnel to CF  │ Reverse proxy       │ Main application (port 8080)     │   │
│  ├───────────────┼─────────────────────┼───────────────────────────────────┤   │
│  │ autodb        │ mitchell-agent.svc  │ redis-server                     │   │
│  │ Port 3001     │ Browser automation  │ Caching layer                    │   │
│  └───────────────┴─────────────────────┴───────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Systemd Services:**

| Service | Port | Description | Command |
|---------|------|-------------|---------|
| `autotech_ai.service` | 8080 | Main FastAPI application | `systemctl status autotech_ai` |
| `mitchell-agent.service` | - | Browser automation agent | `systemctl status mitchell-agent` |
| `nginx.service` | 80 | Reverse proxy | `systemctl status nginx` |
| `cloudflared.service` | - | Cloudflare tunnel | `systemctl status cloudflared` |
| `autodb.service` | 3001 | Operation Charm car manuals | `systemctl status autodb` |
| `redis-server.service` | 6379 | Caching | `systemctl status redis-server` |

**Cloudflare Tunnel Routing:**

```yaml
# /etc/cloudflared/config.yml
tunnel: 5a0ce0f3-7ab6-4c19-81ad-8746d1ec5b65
credentials-file: /etc/cloudflared/5a0ce0f3-7ab6-4c19-81ad-8746d1ec5b65.json

ingress:
  - hostname: aurora-sentient.net
    service: http://127.0.0.1:8081           # Parent company site
  - hostname: automotive.aurora-sentient.net
    path: /autodb*
    service: http://127.0.0.1:3001           # Operation Charm (USB drive)
  - hostname: automotive.aurora-sentient.net
    service: http://127.0.0.1:80             # Main app via nginx
  - service: http_status:404
```

**Environment Variables (`/etc/default/open-webui`):**

```bash
PYTHONPATH=/prod/autotech_ai/backend
STATIC_DIR=/prod/autotech_ai/backend/open_webui/static
```

### Backup Server (poweredge2)

The backup server is fully configured but with services disabled, ready for failover.

| Property | Value |
|----------|-------|
| **Hostname** | poweredge2 |
| **IP Address** | 192.168.50.122 |
| **Code Path** | `/prod/autotech_ai` |
| **Conda Environment** | `open-webui` (Python 3.11) |
| **Service Status** | All services installed but **disabled** |

To activate backup server in case of poweredge1 failure:

```bash
# Enable and start all services
ssh poweredge2 "sudo systemctl enable --now autotech_ai mitchell-agent nginx cloudflared autodb"

# Update Cloudflare tunnel config if needed
```

### Legacy Server (hp6) - Deprecated

The hp6 server is deprecated. All services have been disabled.

| Property | Value |
|----------|-------|
| **Hostname** | hp6 |
| **Status** | **DEPRECATED** - services disabled |
  - service: http_status:404
```

### Development Server (localhost)

Local development runs on a developer workstation.

| Property | Value |
|----------|-------|
| **Hostname** | localhost (msi) |
| **OS** | Ubuntu 24.04 LTS |
| **CPU** | 20 cores |
| **RAM** | 128 GB |
| **Code Path** | `/home/drawson/autotech_ai` |
| **Conda Environment** | `open-webui` |

#### Development Setup

```bash
# Terminal 1: Start Open WebUI backend
cd /home/drawson/autotech_ai
conda activate open-webui
./backend/start.sh

# Terminal 2: Start SvelteKit frontend
npm run dev

# Terminal 3: (Optional) Start Chrome for Mitchell testing
./launch_chrome_cdp_mode.sh

# Terminal 4: (Optional) Run Mitchell agent locally
cd addons/mitchell_agent
python -m agent.pooled_agent
```

**Development URLs:**

| Component | URL |
|-----------|-----|
| Frontend (Vite) | http://localhost:5173 |
| Backend (Uvicorn) | http://localhost:8080 |
| Chrome DevTools | http://localhost:9222 |

### SSH Access

```bash
# Connect to production
ssh poweredge1

# Connect to backup
ssh poweredge2

# Sync code to servers
./sync_to_servers.sh

# View production logs
ssh poweredge1 "journalctl -u autotech_ai -f"
ssh poweredge1 "journalctl -u mitchell-agent -f"

# Restart services
ssh poweredge1 "sudo systemctl restart autotech_ai"
ssh poweredge1 "sudo systemctl restart mitchell-agent"
```

---

## Website Architecture

The public-facing website is a separate React application that serves as the landing page for Autotech AI.

### Technology Stack

| Component | Technology |
|-----------|------------|
| Framework | React 19 with TypeScript |
| Bundler | Vite 6 |
| Routing | React Router v7 |
| Icons | Lucide React |
| Styling | TailwindCSS |

### Directory Structure

```
website/
├── dist/                   # Built files (served by nginx)
├── components/             # React components
│   ├── Hero.tsx           # Landing hero section
│   ├── Features.tsx       # Feature showcase
│   ├── Navigation.tsx     # Header navigation
│   └── Footer.tsx         # Site footer
├── pages/                  # Route pages
│   ├── Home.tsx           # Main landing page
│   └── Features.tsx       # Features detail page
├── public/                 # Static assets
│   └── images/            # Hero images, logos
├── App.tsx                # Main app with routing
├── index.tsx              # Entry point
├── index.html             # HTML template
├── vite.config.ts         # Vite configuration
├── nginx.conf             # Nginx config (template)
└── package.json           # Dependencies
```

### Build & Deploy

```bash
# Build website locally
cd website
npm install
npm run build   # Creates dist/ folder

# Deploy to production
./scripts/deploy-hp6.sh   # Includes website/dist/

# Rebuild on production (alternative)
ssh hp6 "cd /prod/autotech_ai/website && npm run build"
```

### Nginx Configuration

The website and Open WebUI application are served from the same nginx instance with path-based routing:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         NGINX ROUTING (port 80)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  REQUEST PATH              │  SERVED BY                                        │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  /                         │  website/dist/index.html (landing page)           │
│  /features                 │  website/dist/index.html (SPA routing)            │
│  /assets/*                 │  website/dist/assets/ (static JS/CSS)             │
│  /images/*                 │  website/dist/images/ (static images)             │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  /api/*                    │  proxy → localhost:8080 (FastAPI)                 │
│  /auth/*                   │  proxy → localhost:8080 (FastAPI)                 │
│  /chat/*                   │  proxy → localhost:8080 (Open WebUI app)          │
│  /admin/*                  │  proxy → localhost:8080 (Open WebUI app)          │
│  /workspace/*              │  proxy → localhost:8080 (Open WebUI app)          │
│  /_app/*                   │  proxy → localhost:8080 (SvelteKit assets)        │
│  /static/*                 │  proxy → localhost:8080 (static files)            │
│  /ws, /socket.io           │  proxy → localhost:8080 (WebSocket)               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Key Nginx Directives:**

```nginx
# Root for landing page
root /prod/autotech_ai/website/dist;

# Landing page routing
location = / {
    try_files /index.html =404;
}

# SPA routing for feature pages
location /features {
    try_files $uri /index.html;
}

# Proxy to Open WebUI
location /api {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    # ... headers ...
}

# WebSocket support
location /ws {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### Common Website Issues

#### 1. Website Shows Raw TSX Files

**Cause:** Nginx root pointing to `website/` instead of `website/dist/`

```bash
# Fix on production
ssh hp6 "sudo sed -i 's|/website;|/website/dist;|' /etc/nginx/sites-available/automotive"
ssh hp6 "sudo systemctl reload nginx"
```

#### 2. Website Changes Not Appearing

```bash
# Rebuild website
ssh hp6 "cd /prod/autotech_ai/website && npm run build"
ssh hp6 "sudo systemctl reload nginx"

# Clear browser cache (Ctrl+Shift+R)
```

#### 3. 404 on Feature Pages (After Refresh)

**Cause:** SPA routing not configured in nginx

```nginx
# Ensure this exists in nginx config
location /features {
    try_files $uri /index.html;
}
```

### Local Website Development

```bash
cd website

# Install dependencies
npm install

# Start dev server (hot reload)
npm run dev        # http://localhost:5173

# Build for production
npm run build

# Preview production build
npm run preview
```

**Note:** The website dev server (Vite) runs separately from the Open WebUI dev server. During local development:
- Website: http://localhost:5173 (Vite)
- Open WebUI: http://localhost:8080 (Uvicorn) or http://localhost:5174 (Vite)

---

## Addons System

Addons extend Autotech AI with specialized data retrieval capabilities. See [addons/README.md](../addons/README.md) for the full architecture documentation.

### Mitchell Agent Deep Dive

The Mitchell Agent is the most complex addon, implementing autonomous browser navigation powered by LLMs.

#### Directory Structure

```
addons/mitchell_agent/
├── .env                     # Configuration (gitignored)
├── .env.example             # Example configuration
├── openwebui_tool.py        # Tool pasted into Open WebUI
├── openwebui_tool_prod.py   # Production version
├── openwebui_tool_local.py  # Development version
│
├── agent/                   # Remote polling agent
│   ├── pooled_agent.py      # Main service (scaling support)
│   ├── worker_pool.py       # Chrome worker management
│   ├── config.py            # Configuration loading
│   ├── request_handler.py   # Request processing
│   └── service.py           # Legacy single-worker service
│
├── ai_navigator/            # Autonomous LLM navigation
│   ├── an_navigator.py      # Main navigator class
│   ├── an_models.py         # LLM interactions (Gemini, Ollama)
│   ├── an_prompts.py        # System prompt builder
│   ├── an_tools.py          # Tool implementations
│   ├── an_config.py         # Navigator configuration
│   ├── an_debug.py          # Debug logging
│   └── element_extractor.py # DOM element extraction
│
├── browser/                 # Browser automation
│   ├── vehicle_selector.py  # Vehicle selection UI
│   ├── auth.py              # Login/logout
│   ├── context.py           # Browser context
│   ├── extraction.py        # Data extraction
│   └── modal.py             # Modal handling
│
├── server/                  # FastAPI endpoints
│   ├── router.py            # API routes
│   ├── queue.py             # Request queue
│   ├── models.py            # Pydantic models
│   └── navigation.py        # Navigation helpers
│
└── utils/                   # Utility functions
```

#### AI Navigator Architecture

The AI Navigator is the brain of the Mitchell Agent. It uses a "brain-only" model:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           AI NAVIGATOR - "BRAIN ONLY" MODEL                         │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  THE AI HAS NO PERSISTENCE BETWEEN STEPS                                            │
│  We must provide: EYES + FINGERS + MEMORY                                           │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐│
│  │                              EACH STEP                                          ││
│  │                                                                                 ││
│  │  ┌─────────────┐   ┌─────────────────────┐   ┌─────────────────────────────┐   ││
│  │  │   EYES      │   │      FINGERS        │   │         MEMORY              │   ││
│  │  │ (Page State)│   │     (Tools)         │   │      (Path Taken)           │   ││
│  │  │             │   │                     │   │                             │   ││
│  │  │ - Elements  │   │ - click(id, reason) │   │ 1. CLICK 'DTC Index'        │   ││
│  │  │   [1] Home  │   │ - click_text(text)  │   │    → modal opened           │   ││
│  │  │   [2] Fluids│   │ - extract(data)     │   │ 2. EXPAND ALL               │   ││
│  │  │   [3] DTCs  │   │ - capture_diagram() │   │    → revealed 45 DTCs       │   ││
│  │  │   ...       │   │ - expand_all()      │   │ 3. CLICK 'P0300'            │   ││
│  │  │ - Page text │   │ - prior_page()      │   │    → DTC detail page        │   ││
│  │  │ - Modal     │   │ - collect(label)    │   │                             │   ││
│  │  │   status    │   │ - done(summary)     │   │ COLLECTED: 2 items          │   ││
│  │  └─────────────┘   └─────────────────────┘   └─────────────────────────────┘   ││
│  │                                                                                 ││
│  └─────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                     │
│  PHILOSOPHY: Don't build fences - give AI a better view of the room                 │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** The AI (Gemini/Ollama) has NO persistence between steps. Each step it receives:
1. System prompt with navigation paths (the "cheat sheet")
2. Current page state (elements, text, modal status)
3. Path taken so far WITH RESULTS of each action

**Result Hints:** Each path entry includes what happened:
```
1. CLICK 'Wiring Diagrams' → modal opened with diagram options
2. CLICK 'STARTING/CHARGING' → NOW SHOWING DIAGRAM LIST - click specific diagram!
3. CAPTURE DIAGRAM → captured 2 SVG images
4. DONE → returned all captured diagrams
```

#### Tool Definitions

Tools are defined in `an_models.py` and implemented in `an_tools.py`:

```python
AUTONOMOUS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click a numbered element from the list",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer", "description": "The [N] number of the element"},
                    "reason": {"type": "string", "description": "Why clicking this element"}
                },
                "required": ["element_id", "reason"]
            }
        }
    },
    # ... more tools
]
```

#### Worker Pool Architecture

For production, the agent uses a worker pool for parallel request processing:

```python
# Configuration in .env
MITCHELL_SCALING_MODE=ondemand  # single|pool|ondemand
MITCHELL_POOL_MIN_WORKERS=1
MITCHELL_POOL_MAX_WORKERS=3
MITCHELL_POOL_IDLE_TIMEOUT=300
MITCHELL_POOL_BASE_PORT=9222
```

**Scaling Modes:**

| Mode | Chrome Instances | Use Case |
|------|------------------|----------|
| `single` | 1, persistent | Development, debugging |
| `pool` | N, persistent | Medium traffic |
| `ondemand` | Created per request | Production, variable load |

#### Open WebUI Tool

The tool code is **pasted into Open WebUI's UI**, not loaded from file:

```python
# openwebui_tool.py (paste into Open WebUI > Workspace > Tools)
class Tools:
    class Valves(BaseModel):
        SHOP_ID: str = Field(default="", description="Shop identifier")
        API_BASE_URL: str = Field(default="https://automotive.aurora-sentient.net")
        REQUEST_TIMEOUT: int = Field(default=120)
    
    async def query_autonomous(
        self,
        year: int,
        make: str,
        model: str,
        goal: str,
        engine: str = None,
        __user__: dict = None,
    ) -> str:
        """
        Query automotive data using AI navigation.
        The AI will autonomously navigate ShopKeyPro to find the requested information.
        """
        # Create request, wait for result, return formatted data
```

**IMPORTANT:** After editing tool code:
1. Copy entire file contents
2. Paste into Open WebUI > Workspace > Tools > Mitchell Automotive Data
3. Save in UI
4. **Restart Open WebUI server** (it caches tool code in memory!)

### AutoDB Agent (Operation CHARM)

AI-powered integration for Operation CHARM automotive manuals (classic vehicles 1982-2014):

```python
from addons.autodb_agent.navigator import AutodbNavigator
from addons.autodb_agent.models import Vehicle

async def get_oil_capacity():
    nav = AutodbNavigator()
    vehicle = Vehicle(year=2008, make='Honda', model='Accord')
    result = await nav.navigate('oil capacity', vehicle)
    print(result.content)  # Oil capacity specs
    print(result.images)   # Any diagrams found
```

**Key Features:**
- Uses Ollama (qwen2.5:7b-instruct) or Gemini for autonomous navigation
- No browser required - direct HTTP/HTML parsing
- Logs to `/tmp/autodb_agent.log`
- Token billing via `record_usage_event(token_source="autodb_navigator")`

**Configuration:** Create `addons/autodb_agent/.env`:
```bash
AUTODB_MODEL=qwen2.5:7b-instruct
AUTODB_OLLAMA_URL=http://localhost:11434
AUTODB_OLLAMA_NUM_CTX=12000
```

**Deployment Note:** Tool content is loaded from the **database**, not the filesystem. Each Open WebUI tool has a corresponding `tool` row in the DB. After updating a local `openwebui_tool.py`, follow these safe steps:

```bash
# 1) Backup the DB
cp backend/data/webui.db backend/data/webui.db.$(date +%Y%m%dT%H%M%S).bak

# 2) List tools to find the ID you will update
sqlite3 backend/data/webui.db "SELECT id, name FROM tool;"

# 3) Update a single tool (example: autodb)
python - <<'PY'
import sqlite3
with open('addons/autodb_agent/openwebui_tool.py', 'r') as f:
    content = f.read()
conn = sqlite3.connect('backend/data/webui.db')
cursor = conn.cursor()
print('Before update:', cursor.execute("SELECT id, name FROM tool WHERE id = ?", ('autodb',)).fetchone())
cursor.execute('UPDATE tool SET content = ? WHERE id = ?', (content, 'autodb'))
conn.commit()
print('After update:', cursor.execute("SELECT id, name FROM tool WHERE id = ?", ('autodb',)).fetchone())
conn.close()
PY

# 4) Restart service
systemctl restart autotech_ai || ./restart.sh
```

**Note:** If your environment contains multiple Open WebUI tools, update each corresponding DB `tool` row (and back up first). This prevents confusion where the filesystem and DB diverge.
### AI Portal

Future unified interface for multiple data sources. Currently a placeholder for:
- Multiple source adapters
- Query routing and caching
- Source fallback logic

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Chrome browser (for Mitchell Agent)
- Conda (recommended for environment management)

### Environment Setup

```bash
# Clone repository
git clone https://github.com/DRawson5570/autotech_ai.git
cd autotech_ai

# Create conda environment
conda create -n open-webui python=3.11
conda activate open-webui

# Install Python dependencies
pip install -r backend/requirements.txt
playwright install chromium

# Install frontend dependencies
npm install

# Copy environment files
cp .env.example .env
cp addons/mitchell_agent/.env.example addons/mitchell_agent/.env
```

### Configuration

Edit `.env` files with your settings:

```bash
# Main .env
WEBUI_SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///./webui.db

# addons/mitchell_agent/.env
MITCHELL_SHOP_ID=dev_shop
MITCHELL_USERNAME=your_shopkeypro_user
MITCHELL_PASSWORD=your_shopkeypro_pass
GEMINI_API_KEY=your_gemini_api_key
MITCHELL_HEADLESS=false  # Set to true for production
```

### Running Locally

```bash
# Terminal 1: Start backend
cd backend
./start.sh
# Or: python -m uvicorn open_webui.main:app --reload --port 8080

# Terminal 2: Start frontend (dev mode)
npm run dev

# Terminal 3: Start Mitchell Agent (optional)
# First, launch Chrome with CDP
./launch_chrome_cdp_mode.sh

# Then start agent
python -m addons.mitchell_agent.agent.pooled_agent
```

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific addon tests
pytest addons/mitchell_agent/
pytest addons/autodb_tool/tests/
```

### End-to-End Tests

```bash
# Test full chat flow (requires running server + agent)
python addons/mitchell_agent/test_chat_e2e.py

# Test autonomous navigation
python -m addons.mitchell_agent.ai_navigator.autonomous_navigator "fluid capacities"

# Test with specific model
python -m addons.mitchell_agent.ai_navigator -m gemini-2.5-flash "oil capacity"
```

### Cypress Tests

```bash
# Run Cypress tests
npm run cypress:open

# Headless
npm run cypress:run
```

### Important Testing Notes

1. **Never run browser tests in CI** - They require interactive Chrome
2. **Mock ShopKeyPro in unit tests** - Use fixtures, not live portal
3. **Check login state before tests** - Orphaned sessions can lock account
4. **Always logout after tests** - Prevent session accumulation

---

## Deployment

### Sync Script (Recommended)

Use the sync script to deploy code to production and backup servers:

```bash
# Sync to both servers (production and backup)
./sync_to_servers.sh

# Sync to production only
./sync_to_servers.sh --prod-only

# Sync to backup only
./sync_to_servers.sh --backup-only
```

The script:
1. Rsyncs files to `/prod/autotech_ai` on target servers
2. Excludes: `.git/`, `__pycache__/`, `.env`, `node_modules/`, `logs/`, `*.db`, etc.
3. Preserves: All addons, backend, build, frontend code
4. Does NOT restart services (do this manually if needed)

**After syncing, restart services if needed:**

```bash
ssh poweredge1 "sudo systemctl restart autotech_ai"
ssh poweredge1 "sudo systemctl restart mitchell-agent"
```

### Adding New Frontend Routes (IMPORTANT for Prod)

**Dev vs Prod difference:** In development (localhost), the Python backend serves all static files directly. In production, **nginx** sits in front and only proxies specific paths to the backend.

**When you add a new SvelteKit route** (e.g., `/billing/subscription/confirm`):

1. **Add prerender config** - Create a `+page.ts` file alongside your `+page.svelte`:
   ```typescript
   // src/routes/your/new/route/+page.ts
   export const prerender = true;
   export const ssr = false;
   ```

2. **Rebuild frontend** - Run `npm run build` to generate the static HTML

3. **Update nginx on prod** - Add the route to `/etc/nginx/sites-enabled/automotive`:
   ```nginx
   # Example: Adding /billing route
   location /billing {
       root /prod/autotech_ai/build;
       try_files $uri $uri.html @backend;
   }
   
   location @backend {
       proxy_pass http://127.0.0.1:8080;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_buffering off;
   }
   ```

4. **Test and reload nginx**:
   ```bash
   ssh -tt poweredge1 'sudo nginx -t && sudo systemctl reload nginx'
   ```

**Why this is needed:** nginx doesn't know about new SvelteKit routes unless configured. The backend (Open WebUI) also doesn't serve arbitrary static files from the build folder. The `try_files` directive tells nginx to:
- First, look for the file in `/prod/autotech_ai/build`
- If not found, try with `.html` extension
- If still not found, fall back to the backend (`@backend`)

### Starting All Services

Use the convenience script to start all services:

```bash
ssh poweredge1 "cd /prod/autotech_ai && ./start_all_services.sh"
```

This starts: nginx, autotech_ai, mitchell-agent, cloudflared

### Systemd Services

```bash
# Main application
sudo systemctl status autotech_ai
sudo systemctl restart autotech_ai

# Mitchell Agent
sudo systemctl status mitchell-agent
sudo systemctl restart mitchell-agent

# Nginx
sudo systemctl status nginx
sudo systemctl reload nginx

# Cloudflare Tunnel
sudo systemctl status cloudflared
sudo systemctl restart cloudflared

# Operation Charm (autodb)
sudo systemctl status autodb
sudo systemctl restart autodb

# Redis
sudo systemctl status redis-server
```

### Service Files

```ini
# /etc/systemd/system/autotech_ai.service
[Unit]
Description=Autotech AI (Open WebUI)
After=network.target

[Service]
Type=simple
User=drawson
WorkingDirectory=/prod/autotech_ai
EnvironmentFile=/etc/default/open-webui
Environment=FRONTEND_BUILD_DIR=/prod/autotech_ai/build
ExecStart=/home/drawson/anaconda3/bin/conda run -n open-webui --no-capture-output python -m uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

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

```ini
# /etc/systemd/system/autodb.service
[Unit]
Description=AutoDB Operation Charm
After=network.target

[Service]
Type=simple
User=drawson
WorkingDirectory=/mnt/usb/operation-charm
ExecStart=/usr/bin/node server.js /autodb/ 3001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Debugging

### Log Files

| Component | Location |
|-----------|----------|
| Open WebUI | `journalctl -u autotech_ai` |
| Mitchell Agent | `journalctl -u mitchell-agent` |
| AI Navigator | `/tmp/ai_navigator.log` |
| Navigator Debug | `/tmp/navigator_debug.log` |
| Wiring Tool | `/tmp/wiring_tool.log` |
| Screenshots | `/tmp/navigator_screenshots/` |
| Nginx | `/var/log/nginx/automotive.*.log` |

### Common Issues

#### 1. Website Not Loading After Deploy

```bash
# Check nginx
ssh hp6 "sudo systemctl reload nginx"

# Check cloudflared
ssh hp6 "sudo systemctl restart cloudflared"

# Verify nginx config
ssh hp6 "nginx -t"
```

#### 2. Mitchell Agent Failing

```bash
# Check service logs
ssh hp6 "journalctl -u mitchell-agent --since '5 minutes ago' --no-pager"

# Common issues:
# - .env parsing errors (inline comments break int parsing)
# - Chrome not starting (Xvfb not running)
# - Credentials expired
```

#### 3. Tool Not Working in Chat

1. Check if tool code is updated in Open WebUI database
2. Restart Open WebUI server (caches tool code)
3. Check server logs for API errors

#### 4. AI Navigation Stuck

```bash
# Check navigator logs
tail -100 /tmp/ai_navigator.log

# Common causes:
# - Modal not detected (update selector)
# - Element not visible (need scroll)
# - Page layout changed (update selectors)
```

### Debug Screenshots

Enable debug screenshots to see what the AI sees:

```bash
# In .env
MITCHELL_DEBUG_SCREENSHOTS=true
```

Screenshots saved to `/tmp/navigator_screenshots/` with names like:
- `01_initial_state.png`
- `02_after_click.png`
- `03_modal_opened.png`

---

## Best Practices

### Code Style

1. **Type hints** - Use Pydantic models and type annotations
2. **Async/await** - All I/O operations should be async
3. **Logging** - Use structured logging with appropriate levels
4. **Error handling** - Always handle and log exceptions

### Security

1. **Never commit credentials** - Use `.env` files
2. **Always logout** - Prevent session accumulation
3. **Rate limit** - Add delays between portal requests
4. **Validate input** - Sanitize user-provided data

### AI Navigation

1. **Don't hand-hold the AI** - Provide context, not restrictions
2. **Result hints** - Show what happened after each action
3. **Trust the AI** - It's smart enough with proper context
4. **Add guardrails, not fences** - Catch wrong data types, don't block actions

### Testing

1. **Mock external services** - Don't hit live portals in tests
2. **Clean up** - Logout after every test
3. **Check state** - Verify login state before tests
4. **Use fixtures** - Pre-recorded responses for consistency

### Deployment

1. **Test locally first** - Never deploy untested code
2. **Check logs** - Monitor after deployment
3. **Rollback plan** - Know how to revert quickly
4. **Database changes** - Deploy separately from code

---

## Resources

- [Open WebUI Documentation](https://docs.openwebui.com)
- [Playwright Documentation](https://playwright.dev/python/)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Google Gemini API](https://ai.google.dev/docs)

---

## Contact

For questions about the addon system or development workflow, check the existing documentation:
- [addons/README.md](../addons/README.md) - Addon architecture
- [addons/mitchell_agent/DEVELOPER_GUIDE.md](../addons/mitchell_agent/DEVELOPER_GUIDE.md) - Mitchell Agent internals
- [addons/mitchell_agent/AI_NAVIGATION_SPEC.md](../addons/mitchell_agent/ai_navigator/AI_NAVIGATION_SPEC.md) - AI Navigator specification
