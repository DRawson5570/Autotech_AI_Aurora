# Wiring Diagrams Journey — January 9, 2026

## The Problem

User query: "Get me the alternator wiring diagram for a 2014 Chevy Cruze 1.4L LT"

**Symptom:** Response said "wiring diagram identified" but no image displayed. Error: "images were captured but could not be saved"

## The Debugging Journey

### Phase 1: Tracing Where Images Were Lost

1. **Added debug logging** to `openwebui_tool.py` to trace image formatting
2. **Discovered:** Images were being saved to PNG files correctly
3. **Discovered:** Markdown links like `![Fig 1](/static/mitchell/diagram_xyz.png)` were in the tool result
4. **Discovered:** Markdown was reaching the LLM context (logged in middleware.py)
5. **Root cause found:** LLM received the images but wasn't outputting them!

### Phase 2: RAG Template Fix

The RAG template in `webui.db` defines the response format. It had sections for:
- SUMMARY
- ACTION STEPS
- SPECS
- VERIFICATION
- RISKS
- NEXT

But **no IMAGES section**. The LLM was following the template strictly and not outputting images.

**Fix:** Added to RAG template:
```
- IMAGES: If context contains image markdown like ![name](/static/...), 
  you MUST include them here exactly as-is. These are wiring diagrams or 
  technical images the user needs to see.
```

The RAG template is stored in **SQLite database**, not code:
- Local: `/home/drawson/autotech_ai/backend/data/webui.db`
- Production: `/prod/autotech_ai/backend/data/db.sqlite3`
- Table: `config` (id=1)
- Column: `data` (JSON with `rag.template` field)

**Important:** Deploy scripts protect `backend/data/` so database changes must be applied separately!

### Phase 3: Image Size Issues

Images were displaying but too small to read.

**Original approach:** Screenshot wiring diagram pages
**Problem:** Screenshots captured small viewport, images tiny

**Fix in `tools/wiring.py`:**
1. Extract SVG directly from `object.clsArticleSvg` elements
2. Get SVG content via JavaScript: `element.contentDocument.documentElement.outerHTML`
3. Scale SVG to minimum 1200px width before PNG conversion
4. Use `cairosvg` to convert SVG → PNG

### Phase 4: Static Directory on Production

Error: "static directory not found"

**Problem:** `openwebui_tool.py` tried these paths:
- `/app/backend/static` (Docker)
- `/home/drawson/autotech_ai/backend/open_webui/static` (local dev)

But production uses: `/prod/autotech_ai/backend/open_webui/static`

**Fix:** Added production path to lookup list in `openwebui_tool.py`:
```python
possible_dirs = [
    os.environ.get("STATIC_DIR"),
    "/app/backend/static",  # Docker
    "/prod/autotech_ai/backend/open_webui/static",  # Production (poweredge2)
    "/home/drawson/autotech_ai/backend/open_webui/static",  # Dev
    Path(__file__).parent.parent.parent / "backend" / "open_webui" / "static",
]
```

Also created `/static/mitchell/` directory on production:
```bash
ssh poweredge2 "mkdir -p /prod/autotech_ai/backend/open_webui/static/mitchell"
```

### Phase 5: RAG Template Deployment

Since deploy script protects `backend/data/`, had to manually update production database.

Created `/tmp/update_rag_template.py` script that:
1. Connects to SQLite database
2. Reads existing config JSON
3. Updates `rag.template` field with IMAGES section
4. Saves back to database

Ran on production:
```bash
scp /tmp/update_rag_template.py poweredge2:/tmp/
ssh poweredge2 "python3 /tmp/update_rag_template.py /prod/autotech_ai/backend/data/db.sqlite3"
```

## Files Changed

| File | Change |
|------|--------|
| `tools/wiring.py` | SVG extraction, 1200px scaling, cairosvg conversion |
| `openwebui_tool.py` | Added production static path, debug logging |
| `openwebui_tool_local.py` | **NEW** — Copy with local dev path priority |
| `backend/open_webui/utils/middleware.py` | Debug logging for tool results (can be removed) |
| Production `db.sqlite3` | RAG template IMAGES section |

## Key Technical Insights

### 1. RAG Template Controls LLM Output
The LLM follows the RAG template format precisely. If you want specific content in responses, it MUST be in the template.

### 2. Database vs Code
Config changes in `webui.db` are NOT deployed by code deployment. The deploy script (`deploy-poweredge2.sh`) explicitly excludes `backend/data/` to protect:
- User accounts
- Model configurations
- RAG templates
- Knowledge bases

### 3. Static File Serving
Open WebUI serves `/static/` from `backend/open_webui/static/`. Images saved there are accessible at URLs like `/static/mitchell/diagram_xyz.png`.

### 4. Open WebUI Markdown
- ✅ Standard markdown images: `![name](url)`
- ❌ HTML img tags: `<img src="url" width="800">`
- ❌ No width/height control in markdown

### 5. SVG vs Screenshot
- Screenshots: Limited to viewport size, may miss content
- SVG extraction: Gets vector graphics, can scale arbitrarily

## How to Debug Similar Issues

1. **Add logging to openwebui_tool.py** — trace `_format_images()` calls
2. **Check middleware.py** — log what reaches LLM context
3. **Check RAG template** — `sqlite3 webui.db "SELECT data FROM config WHERE id=1;"`
4. **Check static directory** — verify path exists and is writable
5. **Check production separately** — database may differ from dev

## Commands Reference

### Update RAG template on production:
```bash
ssh poweredge2 "python3 -c \"
import sqlite3, json
conn = sqlite3.connect('/prod/autotech_ai/backend/data/db.sqlite3')
cursor = conn.cursor()
cursor.execute('SELECT data FROM config WHERE id=1')
data = json.loads(cursor.fetchone()[0])
print('Has IMAGES:', 'IMAGES:' in data.get('rag',{}).get('template',''))
\""
```

### Create static directory:
```bash
ssh poweredge2 "mkdir -p /prod/autotech_ai/backend/open_webui/static/mitchell"
```

### Deploy code (not database):
```bash
./scripts/deploy-poweredge2.sh --user drawson
```

### Copy specific file to production:
```bash
scp addons/mitchell_agent/openwebui_tool.py poweredge2:/prod/autotech_ai/addons/mitchell_agent/
```

## Result

**Before:** "However, the actual images of the wiring diagrams could not be retrieved or saved"

**After:** Full wiring diagram with alternator, battery, starter motor, fuse block displayed at readable size in chat response! 🎉

---

# HANDOFF NOTES FOR NEXT SESSION

## Current State (January 9, 2026, ~7:30 PM)

### What's Working
- ✅ Wiring diagrams display in production chat
- ✅ SVG extraction and scaling to 1200px
- ✅ RAG template has IMAGES section
- ✅ Production static directory exists
- ✅ All code committed and pushed to main

### Recent Commits
- `427c173` - "Fix wiring diagram images on production"
- Contains: `openwebui_tool.py`, `openwebui_tool_local.py`, sample diagram PNGs

### Production Server
- URL: `https://automotive.aurora-sentient.net`
- SSH: `poweredge2:/prod/autotech_ai`
- Database: `/prod/autotech_ai/backend/data/db.sqlite3`
- Static files: `/prod/autotech_ai/backend/open_webui/static/mitchell/`

### Local Development
- Path: `/home/drawson/autotech_ai`
- Conda env: `open-webui`
- Database: `backend/data/webui.db`
- Use `openwebui_tool_local.py` for local testing

### Key Files to Know
| File | Purpose |
|------|---------|
| `addons/mitchell_agent/openwebui_tool.py` | Tool that formats images for LLM |
| `addons/mitchell_agent/tools/wiring.py` | SVG extraction from ShopKeyPro |
| `addons/mitchell_agent/navigation_config.json` | All selectors for ShopKeyPro |
| `backend/data/webui.db` (or db.sqlite3) | Config including RAG template |

### What Might Need Attention
1. **Debug logging** — Can remove from `middleware.py` once stable
2. **Image cleanup** — Old PNGs accumulate in `/static/mitchell/`
3. **Other tools** — May need similar image handling (TSBs, component diagrams)

### Testing Commands
```bash
# Test wiring diagrams (run on local machine, agent polls server)
# User runs agent manually, then test via chat or:
python addons/mitchell_agent/test_chat_e2e.py --preset wiring --no-stream

# Check production logs
ssh poweredge2 "tail -f /prod/autotech_ai/logs/autotech_ai.log"

# Check agent logs (on machine running agent)
tail -f /tmp/wiring_tool.log
```

### Don't Forget
- **Conda env**: Always `conda activate open-webui`
- **Never start agent yourself** — user handles agent service
- **Database changes** must be deployed separately from code
- **Test on production** after code deploy — DB may need separate update

---

*This document created after successful debugging session. Wiring diagrams confirmed working on production at automotive.aurora-sentient.net.*
