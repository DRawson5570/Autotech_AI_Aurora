# AutoDB Agent - Detailed Specification

**Created:** 2026-01-20
**Status:** In Development
**Author:** AI Assistant (continuing from Mitchell Agent learnings)

## Overview

AutoDB Agent provides AI-powered navigation of the Operation CHARM automotive service manual database (700GB+ of static HTML). Unlike Mitchell (which requires browser automation for a complex JavaScript app), AutoDB is pure HTTP + HTML parsing.

## Architecture: Brain-Only Model

The AI navigator is **just a brain**. We provide:
- **Eyes** = Page state (title, breadcrumb, links, content preview)
- **Fingers** = Tools (click, extract, go_back)
- **Short-term memory** = Path taken with results of each action

The AI has NO persistence between steps. Every step it sees:
1. System prompt with navigation guidance
2. Current page state (what's visible NOW)
3. Path taken so far (what it already did)

## Key Differences from Mitchell Agent

| Aspect | Mitchell | AutoDB |
|--------|----------|--------|
| Site type | Complex JavaScript SPA | Static HTML |
| Navigation | Playwright + Chrome CDP | HTTP requests + BeautifulSoup |
| Login | Required (ShopKeyPro) | None (public site) |
| Speed | Slower (browser overhead) | Fast (pure HTTP) |
| Complexity | High (modals, AJAX, sessions) | Low (simple links) |

## Folder Structure

```
addons/autodb_agent/
├── SPEC.md                 # This file
├── __init__.py             # Package init, exports
├── config.py               # Configuration (timing, limits, URLs)
├── navigator.py            # Main AutodbNavigator class
├── page_parser.py          # HTML parsing, PageState extraction
├── llm_client.py           # Gemini/Ollama API calls with retry
├── tools.py                # Tool implementations (click, extract, go_back)
├── prompts.py              # System prompt templates
├── models.py               # Pydantic models (PageState, NavigationResult, etc.)
├── openwebui_tool.py       # Open WebUI integration
└── tests/
    ├── __init__.py
    ├── test_navigator.py
    └── test_page_parser.py
```

## Core Components

### 1. PageState Model (`models.py`)

```python
@dataclass
class PageState:
    url: str
    title: str
    breadcrumb: List[str]
    links: List[Dict[str, str]]  # [{text, href, path_hint}]
    content_text: str            # Main content (truncated)
    tables: List[str]            # Extracted table data
    has_data: bool               # True if page has specs/values (not just links)
```

### 2. NavigationResult Model (`models.py`)

```python
@dataclass
class NavigationResult:
    success: bool
    content: str = ""
    url: str = ""
    breadcrumb: str = ""
    error: str = ""
    path_taken: List[Dict] = field(default_factory=list)  # [{action, result_hint}]
    tokens_used: Dict[str, int] = field(default_factory=dict)
    steps_taken: int = 0
```

### 3. Tools (`tools.py`)

**click(link_text: str) -> ToolResult**
- Find link by text match (fuzzy)
- Fetch the target page
- Return new PageState

**extract() -> ToolResult**
- Extract main content from current page
- Parse tables into readable format
- Return extracted data

**go_back() -> ToolResult**
- Return to previous page in history
- Return previous PageState

### 4. System Prompt (`prompts.py`)

```
You are navigating the Operation CHARM automotive service manual database.

=== YOUR GOAL ===
Find: {goal}
Vehicle: {year} {make} {model}

=== SITE STRUCTURE ===
Home → Make (e.g., "Jeep", "Honda Truck") → Year → Model → Content Sections

Content sections include:
- Repair and Diagnosis (procedures, specs)
- Specifications (capacities, torque, mechanical)
- Diagnostic Trouble Codes
- Technical Service Bulletins
- Wiring Diagrams

=== TOOLS ===
Respond with JSON only:
- Click a link: {"tool": "click", "link_text": "Exact Link Text"}
- Extract content: {"tool": "extract"}
- Go back: {"tool": "go_back"}

=== RULES ===
1. Navigate to the correct MAKE first (SUVs often under "Make Truck")
2. Then YEAR, then MODEL
3. Then find the relevant content section
4. Use "extract" ONLY when you see actual data (numbers, specs, procedures)
5. If you see only category links, keep clicking deeper!

=== PATH TAKEN ===
{path_taken}

What's your next action?
```

### 5. Page Parser (`page_parser.py`)

Responsibilities:
- Fetch HTML via httpx
- Parse with BeautifulSoup
- Extract title, breadcrumb, links, content
- Detect if page has actual data vs just navigation links
- Truncate content to fit context window

Key functions:
```python
async def fetch_page(url: str) -> str
def parse_page(html: str, url: str) -> PageState
def extract_tables(soup: BeautifulSoup) -> List[str]
def detect_data_page(soup: BeautifulSoup) -> bool
```

### 6. LLM Client (`llm_client.py`)

- Support Gemini and Ollama
- Rate limiting with exponential backoff (503/429)
- Token tracking for billing
- JSON response parsing

```python
async def call_llm(
    model: str,
    system_prompt: str,
    user_message: str,
    max_retries: int = 3
) -> LLMResponse
```

### 7. Navigator (`navigator.py`)

Main orchestration:

```python
class AutodbNavigator:
    async def navigate(
        self,
        goal: str,
        vehicle: dict,  # {year, make, model, engine?}
        max_steps: int = 15
    ) -> NavigationResult:
        
        # Start at homepage or vehicle page if known
        current_url = self._get_start_url(vehicle)
        page_state = await self.fetch_and_parse(current_url)
        path_taken = []
        
        for step in range(max_steps):
            # Build prompt with current state
            prompt = self.build_prompt(goal, vehicle, page_state, path_taken)
            
            # Ask LLM what to do
            response = await self.llm.call(prompt)
            action = self.parse_action(response)
            
            # Execute the action
            if action["tool"] == "click":
                result = await self.tools.click(action["link_text"], page_state)
                path_taken.append({
                    "action": f"CLICK '{action['link_text']}'",
                    "result_hint": result.hint
                })
                page_state = result.new_state
                
            elif action["tool"] == "extract":
                content = await self.tools.extract(page_state)
                return NavigationResult(
                    success=True,
                    content=content,
                    url=page_state.url,
                    breadcrumb=" > ".join(page_state.breadcrumb),
                    path_taken=path_taken
                )
                
            elif action["tool"] == "go_back":
                # Pop from history
                ...
        
        return NavigationResult(success=False, error="Max steps exceeded")
```

## Configuration (`config.py`)

```python
# Base URLs
AUTODB_BASE_URL = "http://automotive.aurora-sentient.net/autodb"

# LLM Settings
DEFAULT_MODEL = "gemini-2.0-flash"
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 1024

# Rate Limiting
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 2.0  # seconds

# Navigation
MAX_STEPS = 15
MAX_LINKS_SHOWN = 50        # Don't overwhelm the LLM
MAX_CONTENT_CHARS = 4000    # Truncate page content
MAX_PATH_HISTORY = 10       # How many steps to show in prompt

# Timeouts
HTTP_TIMEOUT = 30           # seconds
```

## Open WebUI Integration (`openwebui_tool.py`)

```python
class Tools:
    class Valves(BaseModel):
        AUTODB_BASE_URL: str = "http://automotive.aurora-sentient.net/autodb"
        MODEL: str = "gemini-2.0-flash"
        REQUEST_TIMEOUT: int = 120
    
    async def autodb(
        self,
        year: str,
        make: str,
        model: str,
        query: str,
        engine: str = "",
        __user__: dict = None,
        __event_emitter__ = None,
    ) -> str:
        """Query Operation CHARM database for automotive service information."""
        
        navigator = AutodbNavigator(model=self.valves.MODEL)
        result = await navigator.navigate(
            goal=query,
            vehicle={"year": year, "make": make, "model": model, "engine": engine}
        )
        
        # Record billing
        if result.tokens_used:
            record_usage(...)
        
        # Format response
        return format_response(result)
```

## Error Handling

1. **HTTP errors** - Retry with backoff, then fail gracefully
2. **LLM rate limits** - Exponential backoff (2s, 4s, 8s)
3. **Parse errors** - Log and try to continue
4. **Max steps exceeded** - Return partial result with what was found
5. **Link not found** - Tell AI the link wasn't found, let it try again

## Testing Strategy

1. **Unit tests** - Page parser, link matching
2. **Integration tests** - Full navigation flows (manual, not CI)
3. **Test vehicles** - Use known vehicles with predictable content:
   - 2012 Jeep Liberty (oil capacity)
   - 2008 Honda Accord (torque specs)
   - 2010 Ford F-150 (transmission fluid)

## Migration from Old autodb_tool

The old `addons/autodb_tool/` will be kept temporarily for comparison.
Once autodb_agent is validated:
1. Update Open WebUI to use new tool
2. Archive old tool
3. Remove old tool after 1 week

## Development Phases

### Phase 1: Core Infrastructure ✅ COMPLETE
- [x] Create folder structure
- [x] Write SPEC.md (this file)
- [x] Implement models.py
- [x] Implement config.py

### Phase 2: Page Parsing ✅ COMPLETE
- [x] Implement page_parser.py
- [x] Handle edge cases (missing elements, etc.)

### Phase 3: LLM Integration ✅ COMPLETE
- [x] Implement llm_client.py with retry logic
- [x] Implement prompts.py

### Phase 4: Navigator ✅ COMPLETE
- [x] Implement tools.py
- [x] Implement navigator.py

### Phase 5: Open WebUI Integration ✅ COMPLETE
- [x] Implement openwebui_tool.py

### Phase 6: Testing (PENDING)
- [ ] Test on sample AutoDB pages
- [ ] Test prompt effectiveness
- [ ] End-to-end testing
- [ ] Deploy to production

## Key Learnings from Mitchell Agent

1. **Trust the AI** - Don't hand-hold with hard-coded rules
2. **Give it a good view** - Show ALL links, not pre-filtered
3. **Memory matters** - Path taken WITH results helps AI not repeat mistakes
4. **Simple tools** - click, extract, go_back are enough
5. **Guardrails, not fences** - Sanity checks, not forced behavior
