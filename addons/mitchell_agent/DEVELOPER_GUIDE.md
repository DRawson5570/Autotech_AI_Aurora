# Mitchell Agent — Internal Developer Guide ✅

## ✅ RESOLVED: Wiring Diagram Images (2026-01-10)

**Root Cause:** The `openwebui_tool.py` code is pasted into Open WebUI's Tools interface (stored in database), NOT loaded from file. The prod path `/prod/autotech_ai/backend/open_webui/static` was missing from the code pasted into prod's Open WebUI.

**Fix:** Created two clearly labeled files:
- `openwebui_tool_prod.py` - Paste into **automotive.aurora-sentient.net**
- `openwebui_tool_dev.py` - Paste into **localhost:8080**

Both files have both paths, but the headers clearly identify which is which.

**IMPORTANT:** When updating the tool code, you must:
1. Edit the appropriate `_prod.py` or `_dev.py` file
2. Copy the ENTIRE file contents
3. Paste into Open WebUI > Workspace > Tools > Mitchell Automotive Data
4. Save in the UI
5. **RESTART the Open WebUI server** — the server caches tool code in memory!

The files on disk are NOT automatically loaded - they're just the source of truth for what to paste.

---

**CHANGELOG:**
- 2026-01-15: **Multi-Step Collection ("Shopping" Feature)** — Added `collect` and `done` tools to AI Navigator. AI can now gather multiple items before returning. Example: "Look up P0300, P0301, P0302" → AI navigates to each DTC, calls `collect(label, data)` for each, then `done()` to return all. Key changes: (1) `an_models.py` — Added `collect` and `done` tool definitions. (2) `an_tools.py` — Added `_execute_collect()` and `_execute_done()` functions. (3) `an_navigator.py` — Added `_collected_data` tracking, handles `collect` continue and `done` exit. (4) `an_prompts.py` — Updated system prompt with MULTI-ITEM COLLECTION instructions.
- 2026-01-15: **On-Demand Chrome Scaling** — Remote agent now launches Chrome instances on-demand instead of requiring a pre-running browser. Three scaling modes: `single` (classic), `pool` (fixed workers), `ondemand` (create/destroy per request). See "Pooled Agent Architecture" section below.
- 2026-01-14: **Session Limit Error Detection** — Added `SessionLimitError` class to detect when ShopKeyPro licenses are exhausted. Agent now returns user-friendly error instead of cryptic "ShopKeyPro: 10 simultaneous sessions already active". See `api.py` `_check_session_limit()`.
- 2026-01-12: **Fixed IndexError Crash in Vehicle Selection** — When vehicle selector showed "Submodel" tab with empty values list, code crashed accessing `submodel_values[0]`. Fixed in `agent/navigator.py` (added `elif len() > 1` check), `agent/request_handler.py` and `agent/service.py` (safety checks for `missing_info[0]`). Also added **Gemini API retry logic** with exponential backoff (2s, 4s, 8s delays) for 503 "overloaded" errors in `ai_navigator/an_models.py`.
- 2026-01-11: **Gemini Model Support for Autonomous Navigator** — Added Google Gemini API support to `ai_navigator/autonomous_navigator.py`. Gemini (gemini-2.5-flash) is now the **default model** via `--model` / `-m` CLI parameter or `AN_MODEL` env var. Key changes: (1) `_call_gemini()` method using Google's native `generateContent` API. (2) `_parse_tool_calls_from_text()` method parses function calls from Gemini's text responses (handles patterns like `click(22, "reason")`, `capture_diagram("description")`, etc.). (3) API key loaded from `~/gary_gemini_api_key`. **Results:** Gemini shows significantly better reliability than llama3.1:8b for autonomous navigation. Previous llama3.1:8b tests: 1/5 success. Gemini: Much higher success rate with cleaner tool call parsing.
- 2026-01-11: **AI Navigator "Brain-Only" Model** — Major breakthrough in autonomous navigation. Key insight: AI (llama3.1:8b) has no persistence between steps — it's just a brain. We must provide: (1) **Eyes** = page state we show it, (2) **Fingers** = tools we give it, (3) **Short-term memory** = path taken WITH RESULTS. Added `result_hint` to each step showing what happened (e.g., "NOW SHOWING CONNECTOR INDEX - click on your specific connector!"). This prevents repeated INDEX clicking. **Results:** Harness connector query: 9 steps → 4 steps. Component connector query: 10 steps → 4 steps. Philosophy: Don't build fences to block bad actions — give AI a better view of the room so it makes good decisions naturally. See `ai_navigator/AI_NAVIGATION_SPEC.md` for full details.
- 2026-01-10: **Multi-Server Polling** — Agent can now poll multiple servers simultaneously. Set `MITCHELL_SERVER_URL` to comma-separated list (e.g., `https://prod.example.com,http://localhost:8080`). Agent routes results back to the originating server. Single agent instance serves both prod and dev!
- 2026-01-09: **Wiring Diagram Images Working** — Full end-to-end fix for wiring diagrams displaying in chat. Key changes: (1) SVG extraction from `object.clsArticleSvg` elements scaled to 1200px min width. (2) RAG template updated with IMAGES section instruction. (3) Production static path added to `openwebui_tool.py`. (4) `openwebui_tool_local.py` created for local dev. Images now render in chat responses!
- 2026-01-09: **VIN/Plate Lookup Tool Added** — New tool for decoding vehicle from VIN or license plate. Access: Vehicle Selector accordion > "VIN or Plate". Supports: raw OCR text parsing (e.g., "4mzh83 mi"), direct VIN input (17 chars), or plate+state. Returns decoded vehicle info (year, make, model, engine) for use in subsequent queries. Config-driven selectors in `navigation_config.json`. Log file: `/tmp/vin_plate_lookup_tool.log`.
- 2026-01-09: **Component Tests Tool Added** — New tool for getting component test info, pinouts, and operation descriptions. Access: `#ctmQuickAccess`. Structure: Tree view with system categories (ABS, Body Electrical, etc.) → component nodes (Wheel Speed Sensors, etc.) → detail page with Module Location, Operation, Pinouts table. **First tool using full config-driven selectors** — tree selectors and semantic mappings defined in `navigation_config.json` instead of hardcoded. Log file: `/tmp/component_tests_tool.log`.
- 2026-01-09: **Component Location Tool Added** — New tool for finding fuses, relays, grounds, and electrical components. Access: `#electricalComponentLocationAccess`. Structure: Modal with category links → tree views with `li.usercontrol` nodes. Log file: `/tmp/component_location_tool.log`.
- 2026-01-09: **TSB Tool Fixed** — TSBs display in a table (not tree nodes). Fixes: (1) Categories are `li.usercontrol.node.leaf` with text in `<a>` child. (2) Click the `<a>` element to select category. (3) TSBs appear in a table with columns: OEM Ref #, Title, Pub Date. (4) Must target selectors inside `.modalDialogView`. Log file: `/tmp/tsb_tool.log`.
- 2026-01-09: **Wiring Diagrams Tool Fixed** — Wiring diagrams open in `.modalDialogView` modal (not a page). Key fixes: (1) All selectors must target inside `.modalDialogView` (e.g., `.modalDialogView a:has-text("STARTING/CHARGING")`). (2) Must click "SYSTEM WIRING DIAGRAMS" link first to expand categories before clicking specific category like "STARTING/CHARGING". (3) Use semantic mapping (navigation_config.json) to map search terms like "alternator" → "STARTING/CHARGING". Log file: `/tmp/wiring_tool.log`.
- 2026-01-08: **Auto-Select Vehicle Options** — Removed clarification flow. If vehicle options (drive_type, body_style, etc.) are required but not specified, the agent now auto-selects the first available option. The `auto_selected_options` field in ToolResult shows what was selected (e.g., `{"drive_type": "4WD"}`). Technicians can re-query with specific options if the auto-selection was wrong.
- 2026-01-08: **Tool-Level Debug Screenshots** — Added `debug_screenshots` parameter to all tools. When enabled (`MITCHELL_DEBUG_SCREENSHOTS=true`), each tool saves screenshots at every step to `/tmp/navigator_screenshots/` with names like `get_fluid_capacities_01_initial_state.png`. Steps: initial, after_vehicle_select, before_click, modal_open, data_extracted, final_state, error_state.
- 2026-01-08: **Enhanced Debug Screenshots** — Navigator now takes screenshots at EVERY step with detailed state logging. Screenshots saved to `/tmp/navigator_screenshots/`. Debug log at `/tmp/navigator_debug.log`. Use `test_chat_e2e.py` to trigger real LLM + tool flow.
- 2026-01-08: **Improved Tab Detection** — Fixed `get_state()` to detect active tabs using multiple methods (selected/active/current classes, last-enabled tab, computed styles). ShopKeyPro doesn't always use 'selected' class.
- 2026-01-08: **Phase 2 Submodel Fallback** — If Submodel tab isn't detected in Phase 1, Phase 2 now handles it with clarification request instead of infinite loop.
- 2026-01-08: **Dynamic Option Matching** — Navigator now matches submodel, body_style, and drive_type against Mitchell's available options dynamically (no hardcoded trim lists). Added `drive_type` to VehicleInfo model and all tool functions.
- 2026-01-08: **Clean State at Startup** — Agent now calls `ensure_clean_state()` on startup to close modals and logout if already logged in. Prevents confusion when Chrome was left in a bad state from previous runs.
- 2026-01-08: **Unified Navigator** — Created `navigator.py` combining CDP server + navigation + data extraction. Key changes:
  - **Deterministic vehicle selection** (not AI-driven) — more reliable
  - **Text-based extraction** (not vision) — captures all data including scrollable content
  - **Quick Access buttons** with known IDs for navigation (faster, more reliable)
  - **Gemini text analysis** for parsing extracted data
  - **Human-like delays** (800-1300ms) between clicks to avoid bot detection
  - Fixed tire info selector: `#tpmsTireFitmentQuickAccess` (not `#tireInfoAccess`)
- 2026-01-07: **Gemini Vision Navigator** — Switched from Ollama to Google Gemini 2.0 Flash with VISION. Screenshots sent with each step for intelligent navigation. Stateless prompts (fresh context each step) work best.
- 2026-01-07: **Secure Billing** — Agent sends `request_id` (not `user_id`) to prevent billing bypass. Server looks up original user.
- 2026-01-07: **Hybrid Navigation** — Agent can use Gemini (default), local Ollama, OR server's /navigate endpoint. Set `NAVIGATOR_BACKEND=gemini|ollama|server`.
- 2026-01-07: Established "AI Employee" architecture — Gemini handles navigation with vision, polls server for requests, asks Autotech AI when info is missing.
- 2026-01-07: Updated `vehicle_options` selectors in `navigation_config.json` — Drive Type, Body Style, and other option groups now use correct `div.optionGroup` structure.
- 2026-01-07: Added `save_result` tool — saves automotive data to user's Open WebUI Knowledge base.

---

## Architecture Overview 🏗️

The Mitchell Agent is an **"AI Employee"** — a locally-running autonomous agent that fulfills automotive data requests by navigating ShopKeyPro on behalf of Autotech AI customers.

### Legal Classification
This is classified as an **AI Employee** for legal protection:
- Runs on the customer's computer (not cloud)
- Uses customer's own ShopKeyPro credentials
- Acts as an autonomous agent, not a bot/scraper
- Makes decisions and can ask for clarification

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
│                     │     │                      │     │  │ Ollama Navigator    │   │
│                     │     │                      │     │  │ (qwen3:8b + tools)  │   │
│                     │     │                      │     │  └──────────┬──────────┘   │
│  "Which drive type  │◄────│  POST /mitchell      │◄────│             │ request_info│
│   4WD or RWD?"      │     │       /clarify       │     │             │              │
│                     │     │                      │     │             ▼              │
│  User: "4WD"        │────►│  POST /mitchell      │────►│  ┌─────────────────────┐   │
│                     │     │       /answer        │     │  │ Browser Automation  │   │
│                     │◄────│  GET /mitchell/wait  │◄────│  │ Chrome + CDP        │   │
│  "Oil capacity:     │     │                      │     │  │ → ShopKeyPro        │   │
│   8.8 quarts..."    │     │  POST /mitchell      │◄────│  └─────────────────────┘   │
│                     │     │       /result        │     │                             │
└─────────────────────┘     └──────────────────────┘     └─────────────────────────────┘
```

### Data Flow

1. **User asks question** in Open WebUI: "What's the oil capacity for a 2018 Ford F-150 5.0L?"
2. **Autotech AI** extracts vehicle info, creates request, queues it
3. **AI Employee polls** server, claims the request
4. **Ollama Navigator** navigates ShopKeyPro step-by-step:
   - Selects Year → Make → Model → Engine → Submodel
   - If options (Body Style, Drive Type) are needed but not specified → **auto-selects first available option**
5. **Auto-selected options** (if any):
   - The `ToolResult.auto_selected_options` field shows what was chosen (e.g., `{"drive_type": "4WD"}`)
   - Technician can re-query with specific options if needed (e.g., "... with RWD")
6. **Data extraction**: Tool extracts the requested data from ShopKeyPro
7. **Result returned** to Autotech AI → User

---

## Key Components 📦

### Server Side (runs on automotive.aurora-sentient.net)
| File | Purpose |
|------|---------|
| `server/router.py` | FastAPI endpoints for request queue |
| `server/queue.py` | In-memory request/result queue |
| `server/models.py` | Pydantic models for requests/results |
| `openwebui_tool.py` | Open WebUI tool (HTTP client) |

### Agent Side (runs at customer site)
| File | Purpose |
|------|---------|
| `navigator.py` | **NEW (2026-01-08)** Unified browser automation — CDP + navigation + extraction |
| `agent/service.py` | Polling agent service (claims work, submits results) |
| `agent/config.py` | Agent configuration |
| `api.py` | High-level MitchellAPI (legacy, being replaced by navigator.py) |
| `portal.py` | Browser automation helpers (legacy) |
| `tools/*.py` | Individual tool implementations |
| `navigation_config.json` | Canonical selectors document |

### Reference Implementation
| File | Purpose |
|------|---------|
| `test_stable_agent.py` | Working test script — validates navigator approach |
| `test_chat_e2e.py` | **Full chat flow test** — uses Open WebUI API like real user |

---

## Pooled Agent Architecture (On-Demand Scaling) 🔄

**Added:** 2026-01-15

The agent now supports on-demand Chrome instance creation. Instead of requiring a pre-running Chrome browser, the agent launches and manages Chrome instances automatically.

### Scaling Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `single` | One worker, queues requests | Development, low traffic |
| `pool` | Fixed pool of N workers, auto-scaling | Medium traffic, consistent load |
| `ondemand` | Create/destroy Chrome per request | Production, variable load |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Pooled Agent Service                            │
│                    (addons/mitchell_agent/agent/pooled_agent.py)        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌──────────────────┐                                                  │
│   │   Poll Loop      │──► GET /api/mitchell/pending/{shop_id}          │
│   │   (async)        │                                                  │
│   └────────┬─────────┘                                                  │
│            │ Found work?                                                │
│            ▼                                                            │
│   ┌──────────────────────────────────────────────────────────────────┐ │
│   │                    Worker Pool                                    │ │
│   │              (addons/mitchell_agent/agent/worker_pool.py)        │ │
│   │                                                                  │ │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │ │
│   │   │  Worker 1   │  │  Worker 2   │  │  Worker 3   │  (on-demand)│ │
│   │   │  Port 9222  │  │  Port 9223  │  │  Port 9224  │             │ │
│   │   │  Chrome     │  │  Chrome     │  │  Chrome     │             │ │
│   │   └─────────────┘  └─────────────┘  └─────────────┘             │ │
│   │                                                                  │ │
│   │   - Workers created on-demand when requests arrive               │ │
│   │   - Workers destroyed after idle timeout                         │ │
│   │   - Each worker has its own Chrome instance + CDP port           │ │
│   └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Configuration

```bash
# In .env
MITCHELL_SCALING_MODE=ondemand   # single | pool | ondemand
MITCHELL_POOL_MIN_WORKERS=1      # Minimum warm workers (pool mode)
MITCHELL_POOL_MAX_WORKERS=3      # Maximum concurrent workers
MITCHELL_POOL_IDLE_TIMEOUT=300   # Seconds before idle worker shutdown
MITCHELL_POOL_BASE_PORT=9222     # Starting CDP port (9222, 9223, 9224...)
MITCHELL_HEADLESS=true           # Run Chrome headless (production)
```

### Key Files

| File | Purpose |
|------|---------|
| `agent/pooled_agent.py` | Main pooled service (replaces `service.py` for scaling) |
| `agent/worker_pool.py` | Worker lifecycle management, Chrome launching |
| `agent/worker.py` | Individual worker (Chrome + navigation) |

### Starting the Pooled Agent

```bash
# Production (on-demand mode)
./start_remote_agent.sh

# Or manually:
export MITCHELL_SCALING_MODE=ondemand
python -m addons.mitchell_agent.agent.pooled_agent
```

### Why On-Demand?

1. **No manual Chrome management** — agent handles everything
2. **Parallel processing** — multiple requests simultaneously
3. **Resource efficiency** — Chrome instances shut down when idle
4. **Production-ready** — headless mode, auto-recovery

---

## Multi-Step Collection ("Shopping" Feature) 🛒

**Added:** 2026-01-15

The AI Navigator can now collect multiple items before returning. This enables "shopping" queries where the user asks for several pieces of data.

### New Tools

| Tool | Purpose | Behavior |
|------|---------|----------|
| `collect(label, data)` | Store data item | Continues navigating |
| `done(summary)` | Signal finished | Returns all collected data |

### Example Flow

**User asks:** "Look up DTC codes P0300, P0301, and P0302"

**AI does:**
```
1. Click DTC Index → expand_all()
2. Click P0300 → collect("P0300", "Random/Multiple Cylinder Misfire Detected")
3. prior_page() → back to DTC list
4. Click P0301 → collect("P0301", "Cylinder 1 Misfire Detected")
5. prior_page() → back to DTC list  
6. Click P0302 → collect("P0302", "Cylinder 2 Misfire Detected")
7. done("Retrieved all 3 DTC codes")
```

**Result:**
```json
{
  "success": true,
  "data": "## Collected Items\n\n### P0300\nRandom/Multiple Cylinder...\n\n### P0301\n...",
  "collected_items": 3
}
```

### How It Works

1. **`collect(label, data)`** — Stores `{label, data}` in a mutable list, returns success, AI continues
2. **`done(summary)`** — Combines all collected items, exits navigation loop
3. **`extract(data)`** — Still works for single items (exits immediately)

### Implementation Files

| File | Changes |
|------|---------|
| `ai_navigator/an_models.py` | Added `collect` and `done` tool definitions |
| `ai_navigator/an_tools.py` | Added `_execute_collect()` and `_execute_done()` |
| `ai_navigator/an_navigator.py` | Track `_collected_data`, pass to execute_tool, handle exit |
| `ai_navigator/an_prompts.py` | Updated TOOLS section, added MULTI-ITEM COLLECTION guide |

### AI Memory During Collection

The AI sees its collection progress in the path:
```
YOUR PATH SO FAR:
  1. CLICK 'DTC Index' → modal opened
  2. EXPAND ALL → revealed all DTC codes
  3. CLICK 'P0300' → DTC detail page
  4. COLLECT 'P0300' → stored
  5. PRIOR PAGE → back to DTC list

COLLECTED: 1 item(s) stored - call done() when finished collecting
```

---

## Adding a New Tool 🔧

When adding a new tool (e.g., `get_component_location`), you **MUST** update these 7 files:

### Checklist

| Step | File | What to Add |
|------|------|-------------|
| 1 | `tools/<toolname>.py` | Create tool class extending `MitchellTool` |
| 2 | `tools/registry.py` | Import and register with `registry.register_class()` |
| 3 | `server/models.py` | Add to `ToolType` enum (e.g., `COMPONENT_LOCATION = "get_component_location"`) |
| 4 | `openwebui_tool.py` | Add async method for Open WebUI to call |
| 5 | `api.py` | Add high-level API method that agent calls |
| 6 | `agent/service.py` | Add to `tool_map` dict in `_execute_tool()` |
| 7 | `test_tool_e2e.py` | Add to `--tool` CLI choices for testing |

### Example: Adding `get_component_location`

**Step 1: Create `tools/component_location.py`**
```python
from .base import MitchellTool, ToolResult, Vehicle

class ComponentLocationTool(MitchellTool):
    name = "get_component_location"
    description = "Find electrical component locations"
    tier = 1
    
    async def execute(self, vehicle: Vehicle, component: str = None, **kwargs) -> ToolResult:
        # Open modal, search, extract data
        await self._open_component_locations()
        result = await self._search_for_component(component)
        return ToolResult(success=True, data=result)
```

**Step 2: Register in `tools/registry.py`**
```python
from .component_location import ComponentLocationTool
# ... in _register_default_tools():
registry.register_class(ComponentLocationTool)
```

**Step 3: Add to `server/models.py` ToolType enum**
```python
class ToolType(str, Enum):
    # ... existing tools ...
    COMPONENT_LOCATION = "get_component_location"
```

**Step 4: Add method in `openwebui_tool.py`**
```python
async def get_component_location(
    self,
    year: int, make: str, model: str,
    component: str = Field(default="", description="Component to find"),
    # ... other fields ...
    __user__: dict = {}
) -> str:
    return await self._make_request("get_component_location", year, make, model, ...)
```

**Step 5: Add method in `api.py`**
```python
async def get_component_location(self, year, make, model, engine=None, component=None, ...) -> Dict:
    vehicle = self._make_vehicle(year, make, model, engine)
    result = await self._registry.execute_tool("get_component_location", vehicle, component=component)
    return result.to_dict()
```

**Step 6: Add to `agent/service.py` tool_map**
```python
tool_map = {
    # ... existing tools ...
    "get_component_location": lambda: self._api.get_component_location(
        year, make, model, engine,
        component=params.get("component"),
        location_type=params.get("location_type")
    ),
}
```

**Step 7: Add to `test_tool_e2e.py` choices**
```python
parser.add_argument("--tool", choices=[
    # ... existing tools ...
    "get_component_location",
])
```

### Restart Requirements

After adding a new tool, restart **both**:
1. **Main server** (autotech_ai.service) — to pick up `server/models.py` changes
2. **Agent** (mitchell agent process) — to pick up tool registry changes

### Testing

```bash
# Restart server first
sudo systemctl restart autotech_ai.service

# Restart agent (in agent terminal)
# Ctrl+C and restart

# Test the new tool
python test_tool_e2e.py --tool get_component_location --component "radio" --year 2014 --make Chevrolet --model Cruze --engine "1.4L"
```

---

## Debugging Navigation Issues 🔍

When navigation gets stuck, use these tools:

### Enabling Tool Debug Screenshots

Set the environment variable before starting the agent:
```bash
export MITCHELL_DEBUG_SCREENSHOTS=true
```

Each tool will then save screenshots at every step:
```
get_fluid_capacities_01_initial_state.png
get_fluid_capacities_02_after_vehicle_select.png
get_fluid_capacities_03_home_page.png
get_fluid_capacities_04_before_fluids_click.png
get_fluid_capacities_05_fluids_modal_open.png   <-- The data!
get_fluid_capacities_06_data_extracted.png
get_fluid_capacities_07_final_state.png
```

### Screenshot Trail (Navigator)

Every navigation step creates a screenshot in `/tmp/navigator_screenshots/`:
```
01_selector_opened_135245.png
02_year_selected_135246.png
03_make_selected_135247.png
04_model_selected_135248.png
05_before_engine_135249.png
06_engine_selected_135250.png
07_before_submodel_135251.png
08_submodel_not_detected_135252.png  <-- Problem here!
```

### Debug Log

Detailed state at each step in `/tmp/navigator_debug.log`:
```
============================================================
STEP 7: before_submodel
============================================================
Screenshot: /tmp/navigator_screenshots/07_before_submodel_135251.png
Current tab: NOT FOUND
Tab class: N/A
Values (3): ['LX', 'Sport', 'Type R']
Use button disabled: True
Selector visible: True
All tabs:
  - Year: classes='year' disabled=False
  - Make: classes='make' disabled=False
  - Model: classes='model' disabled=False
  - Engine: classes='engine' disabled=False
  - Submodel: classes='submodel' disabled=False  <-- Active but no 'selected' class!
============================================================
```

### Tab Detection Methods

The navigator tries multiple methods to detect the current tab:
1. `li.selected` class
2. `li.active` class
3. `li.current` or `li.on` class
4. `aria-selected="true"` attribute
5. Last non-disabled tab (fallback)
6. Computed background color (fallback)

If all fail, the debug log shows `tab_classes` and `tab_texts` for manual inspection.

### Running Chat E2E Tests

Test the full flow through Open WebUI's chat API:
```bash
# Test with complete vehicle info (should succeed)
python addons/mitchell_agent/test_chat_e2e.py --preset fluids --no-stream

# Test missing info (auto-selects first option, check auto_selected_options in result)
python addons/mitchell_agent/test_chat_e2e.py --preset clarification --no-stream

# Test Honda Civic (known to have submodel options)
python addons/mitchell_agent/test_chat_e2e.py --preset dtc --no-stream
```

---

## Unified Navigator (2026-01-08) 🚀

The new `navigator.py` combines all browser automation into one module.

### Key Design Principles

1. **Deterministic vehicle selection** — Scripted, not AI-driven
2. **Text-based data extraction** — Gets all content including scrollable areas
3. **Quick Access buttons** — Known IDs for fast, reliable navigation
4. **Gemini text analysis** — Parses extracted text into structured data
5. **Human-like delays** — 800-1300ms random delays to avoid bot detection

### Quick Access Button IDs

```python
QUICK_ACCESS_BUTTONS = {
    "fluid capacities": "#fluidsQuickAccess",
    "common specs": "#commonSpecsAccess",
    "reset procedures": "#resetProceduresAccess",
    "technical bulletins": "#technicalBulletinAccess",
    "dtc index": "#dtcIndexAccess",
    "tire information": "#tpmsTireFitmentQuickAccess",  # Note: NOT #tireInfoAccess!
    "adas": "#adasAccess",
    "wiring diagrams": "#wiringDiagramsAccess",
    "electrical locations": "#electricalComponentLocationAccess",
    "component tests": "#ctmQuickAccess",
    "service manual": "#serviceManualQuickAccess",
}
```

### Usage Example

```python
from addons.mitchell_agent.navigator import MitchellNavigator

async def main():
    nav = MitchellNavigator()
    await nav.connect()  # Launches Chrome if needed, logs in
    
    # Get fluid capacities
    result = await nav.get_data(
        year=2020, make="Toyota", model="Camry", engine="2.5L",
        data_type="fluid capacities"
    )
    print(result["data"])
    
    # Get more data (same session, vehicle already selected)
    result = await nav.get_data(
        year=2020, make="Toyota", model="Camry", engine="2.5L",
        data_type="tire information"
    )
    
    await nav.logout()
    await nav.disconnect()
```

### Why Text Extraction Over Vision?

Vision (screenshots) only captures visible content. If data requires scrolling, it's missed.
Text extraction gets ALL content from the DOM, including scrollable areas.

```python
# Text extraction captures everything
text = await page.evaluate('''() => {
    const mainContent = document.querySelector('#contentPanel')?.innerText;
    const tables = [...document.querySelectorAll('table')].map(t => t.innerText);
    return { mainContent, tables };
}''')
```

### Human Delays (Bot Detection Prevention)

```python
async def human_delay(min_ms: int = 800, max_ms: int = 1300) -> None:
    """Add random delay to mimic human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)
```

All clicks and navigation actions include human-like delays.

---

## Legacy: Ollama Navigator 🤖

The navigator uses an LLM to autonomously navigate ShopKeyPro's vehicle selector.

### Backend Selection

| Backend | Setting | Behavior |
|---------|---------|----------|
| **gemini** (default) | `NAVIGATOR_BACKEND=gemini` | Google Gemini 2.0 Flash with VISION - sees screenshots! |
| **ollama** | `NAVIGATOR_BACKEND=ollama` | Local Ollama instance (qwen3:8b) |
| **server** | `NAVIGATOR_BACKEND=server` | Server's `/navigate` endpoint |

### Gemini Vision (Recommended)

The default backend uses **Gemini 2.0 Flash** with vision capabilities:

- **Screenshots**: Takes a screenshot with each step and sends to Gemini
- **Stateless Prompts**: Fresh system + user message each step (no accumulated history)
- **Simple System Prompt**: "Trust the SCREENSHOT to see the current state"
- **Temperature 0.0**: Deterministic responses
- **Mode ANY**: Forces function calling

**Why Gemini Vision works so well:**
1. Can SEE the actual page, not just DOM text
2. Understands visual context (buttons, modals, popups)
3. No hallucinations about what's on screen
4. Handles edge cases gracefully

**Key insight from testing:** Complex prompts confuse the model. Minimal instructions + visual context = best results.

### Hybrid Architecture (GPU Optional!)

Not all customers have GPUs. The navigator supports three modes:

| Mode | Setting | Behavior |
|------|---------|----------|
| **auto** (default) | `NAVIGATION_MODE=auto` | Try local Ollama first, fall back to server if unavailable |
| **local** | `NAVIGATION_MODE=local` | Only use local Ollama (fails if model not available) |
| **server** | `NAVIGATION_MODE=server` | Always use server's `/navigate` endpoint |

**How it works:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AI Employee                                    │
│                                                                         │
│   ┌─────────────┐     Mode=auto?     ┌──────────────────────┐          │
│   │ Get State   │─────────┬─────────►│ Check Local Ollama   │          │
│   │ from Page   │         │          │ (qwen3:8b available?)│          │
│   └─────────────┘         │          └──────────┬───────────┘          │
│                           │                     │                       │
│                           │          ┌──────────┴───────────┐          │
│                           │          │         Yes          │  No      │
│                           │          ▼                      ▼          │
│                     ┌─────────────────────┐   ┌──────────────────┐    │
│                     │   Local Ollama      │   │  Server /navigate│    │
│                     │   localhost:11434   │   │  (server-side AI)│    │
│                     └──────────┬──────────┘   └────────┬─────────┘    │
│                                │                       │               │
│                                └───────────┬───────────┘               │
│                                            ▼                           │
│                                  ┌─────────────────┐                   │
│                                  │ Tool Call:      │                   │
│                                  │ select_year(...)│                   │
│                                  └────────┬────────┘                   │
│                                           │                            │
│                                           ▼                            │
│                                  ┌─────────────────┐                   │
│                                  │ Execute Action  │                   │
│                                  │ on Browser      │                   │
│                                  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Server-Side Navigation Endpoint:**

```
POST /api/mitchell/navigate
{
    "request_id": "abc-123",  // Used to lookup user for secure billing
    "shop_id": "shop_xyz",
    "goal": "2018 Ford F-150 5.0L XLT",
    "state": {"current_tab": "Year", "values": ["2016", "2017", "2018", ...]},
    "step": 1
}

Response:
{
    "action": {"tool": "select_year", "args": {"year": "2018"}},
    "done": false,
    "tokens_used": {"prompt_tokens": 450, "completion_tokens": 12, "total_tokens": 462}
}
```

**Security & Billing:**
- Agent sends `request_id` (not `user_id`) to prevent spoofing
- Server looks up `request_id` → finds original user who created request
- Server bills that verified user via `record_usage_event()`
- Tokens billed per step with `token_source="mitchell_navigation"`
- Agent cannot bypass billing by changing identifiers

### Why Local Ollama (When Available)?
- **Privacy**: Customer credentials never leave their machine
- **Speed**: No round-trip to cloud for each navigation step
- **Cost**: No per-token charges for navigation
- **Legal**: "AI Employee" using local compute

### Model Selection
| Model | Status | Notes |
|-------|--------|-------|
| `gemini-2.0-flash` | ✅ **Recommended** | Vision + tool calling, sees screenshots, fast |
| `qwen3:8b` (Ollama) | ⚠️ Works | Good tool-calling but no vision, may loop |
| `qwen2-vl:8b` (Ollama) | ⚠️ Experimental | Has vision but no native tool calling |
| `llama3.1:8b` | ❌ Loops | Gets stuck re-selecting options |

### Native Tool Calling

Uses Ollama's native `/api/chat` with `tools` parameter — model outputs structured `tool_calls`:

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "select_year",
            "description": "Select a year from the vehicle selector",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "string"}
                },
                "required": ["year"]
            }
        }
    },
    # ... more tools
]

response = await client.post(OLLAMA_URL, json={
    "model": "qwen3:8b",
    "messages": messages,
    "tools": TOOLS,
    "stream": False
})

# Response includes:
# {"message": {"tool_calls": [{"function": {"name": "select_year", "arguments": {"year": "2018"}}}]}}
```

### Available Tools

| Tool | Description |
|------|-------------|
| `select_year` | Select year from list |
| `select_make` | Select make (Ford, Chevy, etc.) |
| `select_model` | Select model (F-150, Silverado, etc.) |
| `select_engine` | Select engine (5.0L VIN 5, etc.) |
| `select_submodel` | Select submodel (XLT, Lariat, etc.) |
| `select_body_style` | Select body style option |
| `select_drive_type` | Select drive type (4WD/RWD/AWD) |
| `request_info` | **Request missing info from Autotech AI** |
| `confirm_vehicle` | Click "Use This Vehicle" |
| `done` | Navigation complete |

### Request Info Flow 🔄

When the navigator encounters an option it needs but doesn't have:

```python
# Model calls:
Tool: request_info({
    'option_name': 'Drive Type',
    'available_values': ['4WD', 'RWD'],
    'message': 'Please select Drive Type for the 2018 Ford F-150.'
})

# Navigator calls callback:
answer = on_info_needed("Drive Type", ["4WD", "RWD"], "Please select...")

# In production, this:
# 1. Posts to Autotech AI server: POST /mitchell/clarify
# 2. Autotech AI asks user
# 3. User answers "4WD"
# 4. Answer returns to navigator
# 5. Navigator continues with updated goal
```

---

## Browser Automation: Hybrid Chrome + Playwright CDP 🌐

### Why This Approach
- **Real Chrome** bypasses bot detection (Playwright's bundled Chromium gets blocked)
- **Playwright API** via CDP provides nice async automation
- **Session persistence** via user data directory

### Connection Flow
```python
# 1. Launch real Chrome with remote debugging
subprocess.Popen([
    "/usr/bin/google-chrome",
    "--remote-debugging-port=9222",
    f"--user-data-dir={profile_path}",
    "about:blank"
])

# 2. Connect Playwright to Chrome via CDP
browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0]
page = context.pages[0]

# 3. Use standard Playwright API
await page.click("#qualifierTypeSelector li:has-text('Year')")
```

---

## Configuration ⚙️

### Environment Variables (.env)
```bash
# Agent identity
MITCHELL_SHOP_ID=customer_shop_id
MITCHELL_SERVER_URL=https://automotive.aurora-sentient.net
MITCHELL_HEADLESS=false  # true for production

# ShopKeyPro credentials
MITCHELL_USERNAME=xxx
MITCHELL_PASSWORD=xxx

# Chrome settings
CHROME_EXECUTABLE_PATH=/usr/bin/google-chrome
CHROME_USER_DATA_PATH=/home/user/.config/mitchell-profile

# Ollama (local)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

### navigation_config.json Selectors

All selectors live in `navigation_config.json`. Key sections:

```json
{
  "vehicle_selector": {
    "button": "#vehicleSelectorButton",
    "type_selector": "#qualifierTypeSelector",
    "value_selector": "#qualifierValueSelector",
    "confirm_button": "input[data-action='SelectComplete']"
  },
  "vehicle_options": {
    "panel_container": "#qualifierValueSelector div.options",
    "option_group": "div.optionGroup",
    "body_style": {
      "group": "div.optionGroup:has(h1:has-text('Body Style'))"
    },
    "drive_type": {
      "group": "div.optionGroup:has(h1:has-text('Drive Type'))"
    }
  },
  "quick_access": {
    "fluid_capacities": "#fluidsQuickAccess",
    "dtc_index": "#dtcIndexAccess"
  }
}
```

---

## Running the Navigator 🚀

### Development/Testing
```bash
cd /home/drawson/autotech_ai
conda activate open-webui
python scripts/ollama_navigator_v3.py
```

### Expected Output
```
=============================================================
  Ollama Navigator v3 - Native Tool Calling
=============================================================

[1/3] Checking Ollama...
  ✅ qwen3:8b ready

[2/3] Launching Chrome...
  ✅ Logged in

[3/3] Starting navigation...
GOAL: Select 2018 Ford F-150 with 5.0L engine, XLT submodel, 4D Pickup Crew Cab

--- Step 1 --- Tab: Year
  Tool: select_year({'year': '2018'})  ✅

--- Step 6 --- Tab: Options
  Tool: select_body_style({'body_style': '4D Pickup Crew Cab'})  ✅

--- Step 7 --- Tab: Options  
  Tool: request_info({'option_name': 'Drive Type', ...})
  📋 Requesting: Drive Type from ['4WD', 'RWD']

--- Step 8 ---
  Tool: select_drive_type({'drive_type': '4WD'})  ✅

--- Step 9 ---
  Tool: confirm_vehicle({})  ✅

🎉 Success!
```

---

## Save to Knowledge 💾

The `save_result` tool allows users to save automotive data to their personal Open WebUI Knowledge base.

**How it works:**
1. User gets automotive data (e.g., fluid capacities)
2. User says "Save that" or "Remember this"
3. `save_result` creates markdown file, links to Knowledge base
4. Open WebUI indexes for future RAG retrieval

**Key files:**
- `backend/open_webui/routers/mitchell.py` — `POST /mitchell/save` endpoint
- `openwebui_tool.py` — `save_result()` method

**Policy:**
- Saving is ALWAYS user-triggered (never auto-save)
- Data is private to the user
- Works for any automotive data source

---

## Testing 🧪

**CRITICAL:** Never run tests via CI — browser automation requires manual monitoring. Run all tests locally.

### Prerequisites

1. **Conda environment activated:**
   ```bash
   conda activate open-webui
   ```

2. **Chrome running with CDP (separate terminal):**
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/mitchell_chrome
   ```

3. **Check if already logged in (prevents session conflicts):**
   ```bash
   curl -s http://127.0.0.1:9222/json | jq -r '.[0].url'
   # If URL contains "shopkeypro.com/Main", logout first!
   ```

4. **Server running:**
   ```bash
   # Check server status
   curl -s http://localhost:8080/health
   ```

---

### Test 1: Direct Autonomous Navigator (Recommended for Development)

Test the AI navigator directly without going through the full agent/server stack.

```bash
cd /home/drawson/autotech_ai

# Gemini model (default, recommended)
python addons/mitchell_agent/ai_navigator/autonomous_navigator.py \
    --goal "Get alternator wiring diagram for 2014 Chevrolet Cruze 1.4L" \
    --model gemini-2.5-flash

# Ollama model (fallback)
python addons/mitchell_agent/ai_navigator/autonomous_navigator.py \
    --goal "Get oil capacity for 2020 Toyota Camry 2.5L" \
    --model llama3.1:8b
```

**CLI Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--goal`, `-g` | The task to perform | Required |
| `--model`, `-m` | AI model (`gemini-2.5-flash` or `llama3.1:8b`) | `gemini-2.5-flash` |
| `--max-steps` | Maximum navigation steps | 20 |
| `--debug` | Enable debug output | False |

**Environment Variables:**
| Variable | Description |
|----------|-------------|
| `AN_MODEL` | Default model if `--model` not specified |
| `GEMINI_API_KEY` | Gemini API key (or reads from `~/gary_gemini_api_key`) |

---

### Test 2: Tool E2E Test

Test specific tools through the agent HTTP API.

```bash
cd /home/drawson/autotech_ai

# Fluid capacities
python addons/mitchell_agent/test_tool_e2e.py \
    --tool get_fluid_capacities \
    --year 2020 --make Toyota --model Camry --engine "2.5L"

# Wiring diagrams
python addons/mitchell_agent/test_tool_e2e.py \
    --tool get_wiring_diagram \
    --component "alternator" \
    --year 2014 --make Chevrolet --model Cruze --engine "1.4L"

# DTCs
python addons/mitchell_agent/test_tool_e2e.py \
    --tool get_dtc_info \
    --dtc_code "P0420" \
    --year 2018 --make Honda --model Civic --engine "1.5L"
```

---

### Test 3: Chat E2E Test (Full Stack)

Test the complete flow through Open WebUI's chat API. Requires server and agent running.

```bash
cd /home/drawson/autotech_ai

# Test with preset query
python addons/mitchell_agent/test_chat_e2e.py --preset fluids --no-stream

# Test with custom query
python addons/mitchell_agent/test_chat_e2e.py \
    --query "What is the oil capacity for a 2020 Toyota Camry 2.5L?" \
    --no-stream

# Test DTCs
python addons/mitchell_agent/test_chat_e2e.py --preset dtc --no-stream

# Test wiring diagrams (returns image URLs)
python addons/mitchell_agent/test_chat_e2e.py \
    --query "Show me the alternator wiring diagram for 2014 Chevy Cruze 1.4L" \
    --no-stream
```

**Available Presets:**
| Preset | Description |
|--------|-------------|
| `fluids` | Fluid capacities for 2020 Toyota Camry |
| `dtc` | DTC info for Honda Civic |
| `clarification` | Tests auto-select when options missing |

---

### Test 4: Batch Testing

Run multiple tests in sequence (useful for reliability testing):

```bash
cd /home/drawson/autotech_ai

# 5-test loop
for i in {1..5}; do
    echo "=== Test $i/5 ==="
    python addons/mitchell_agent/ai_navigator/autonomous_navigator.py \
        --goal "Get alternator wiring diagram for 2014 Chevrolet Cruze 1.4L" \
        --model gemini-2.5-flash
    echo ""
done
```

⚠️ **Warning:** Long batch runs may hit terminal buffer overflow (BlockingIOError) from base64 image data in output. This is a display issue, not a test failure.

---

### Key Test Scenarios

1. **Complete vehicle selection** — all info provided in goal
2. **Missing drive type** — should auto-select first option (check `auto_selected_options`)
3. **Missing body style** — should auto-select first option
4. **Wiring diagrams** — should capture SVG, convert to PNG, return image URL
5. **TSBs** — should extract bulletin list from modal table

---

## Troubleshooting 🔧

| Issue | Solution |
|-------|----------|
| Model keeps re-selecting same option | Use `qwen3:8b`, not `llama3.1:8b` |
| Model guesses instead of asking | Use instruct model with clear `request_info` tool |
| Selector timeout | Check `navigation_config.json` selectors match current ShopKeyPro DOM |
| Chrome won't launch | Check `CHROME_EXECUTABLE_PATH`, kill stale chrome processes |
| Login fails | Check credentials, may need to reset session |

---

## Next Steps 📋

1. **Create `agent/navigator.py`** — Module version of `scripts/ollama_navigator_v3.py`
2. **Integrate with `agent/service.py`** — Polling agent uses navigator for vehicle selection
3. **Add `/mitchell/clarify` endpoint** — Server receives `request_info` and forwards to Autotech AI
4. **Add `/mitchell/answer` endpoint** — Returns user's answer to waiting agent
5. **Production hardening** — Retry logic, timeout handling, graceful degradation

