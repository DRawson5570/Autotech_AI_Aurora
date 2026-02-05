# AutoDB AI Navigator Specification

**Date:** January 21, 2026  
**Status:** ✅ Production Ready (10/10 tests passing)  
**Model:** Gemini 2.0 Flash  

## Overview

The AI Navigator is a tree-based navigation system that uses an LLM to autonomously navigate hierarchical website structures (like Operation CHARM automotive manuals) to find specific information. It requires no pre-built index - the AI explores the site structure in real-time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Navigator                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Gemini    │◄──►│   State     │◄──►│  Playwright │         │
│  │   2.0 Flash │    │   Manager   │    │   Browser   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                 │                   │                 │
│         ▼                 ▼                   ▼                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Navigation Loop                         │       │
│  │  1. Extract page state (links at current depth)     │       │
│  │  2. Build message with path taken                   │       │
│  │  3. AI decides: click(n) | back() | extract()       │       │
│  │  4. Execute action, update state                    │       │
│  │  5. Repeat until extract() or max steps             │       │
│  └─────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### Tree-Based Navigation

The site structure is a nested tree of folders and content pages:

```
Repair and Diagnosis/           ← Root (tree_path: [])
├── Engine, Cooling and Exhaust/    ← Folder (tree_path: ["Engine..."])
│   ├── Engine/                     ← Folder (tree_path: ["Engine...", "Engine"])
│   │   ├── Engine Lubrication/     ← Folder
│   │   │   ├── Engine Oil Pressure ← Content link (navigates to new page)
│   │   │   │   └── Specifications  ← Content link
```

**Critical distinction:**
- **Folders** (`li.li-folder`): Clicking expands in-place, stays on same page
- **Content links** (`li:not(.li-folder) > a[href]`): Clicking navigates to new URL

### State Tracking

```python
tree_path: list[str]  # Current position in folder hierarchy
nav_stack: list[tuple[str, list[str]]]  # (url, tree_path) for backtracking
```

### AI Tools

The AI has exactly 3 tools:

| Tool | Description | When to Use |
|------|-------------|-------------|
| `click(n)` | Click link #n from current list | Navigate deeper into tree |
| `back()` | Go back one level | Wrong path, need to explore elsewhere |
| `extract()` | Extract answer from current page | Found the information |

## System Prompt Design

The system prompt is the "cheat sheet" that gives the AI its navigation intelligence:

```python
SYSTEM_PROMPT = """You are navigating a car repair manual website to find: {query}
Vehicle: {vehicle}

TOOLS:
- click(n) - Click link number n
- back() - Go back one level  
- extract() - Extract the answer from current page

NAVIGATION RULES:
1. Look for folders/links most likely to contain your answer
2. Common patterns:
   - Specifications often under "Specifications" folder
   - Capacities under "Capacity Specifications"
   - Locations under component name > "Locations"
   - Procedures under component > "Service and Repair"

3. BACKTRACKING: If you reach a page that doesn't have your answer:
   - Use back() to return to previous level
   - Try a different path
   - Don't give up until you've explored reasonable alternatives

4. When to extract():
   - Page contains the specific data you need
   - READ the page text carefully before extracting

Respond with ONLY the tool call, e.g.: click(5) or back() or extract()
"""
```

## Page State Extraction

Each step, we extract the current page state to show the AI:

```python
async def extract_page_state(page: Page, tree_path: list[str]) -> dict:
    """Extract clickable elements at current tree depth."""
    
    if tree_path:
        # Build selector for current depth in tree
        selector = build_tree_selector(tree_path)
        links = await page.locator(f"{selector} > ul > li > a").all()
    else:
        # Root level - get top-level items
        links = await page.locator("ul.tree > li > a").all()
    
    return {
        "links": [(i+1, await link.text_content()) for i, link in enumerate(links)],
        "is_content_page": len(links) == 0 or await has_article_content(page),
        "page_text": await extract_page_text(page),  # For content matching
    }
```

## User Message Format

The message sent to AI each step:

```
CURRENT PATH: Vehicle/Repair and Diagnosis > Engine > Specifications

AVAILABLE LINKS:
[1] Mechanical Specifications
[2] Electrical Specifications  
[3] Capacity Specifications

PAGE TEXT PREVIEW:
(first 500 chars of page content)

YOUR PATH SO FAR:
1. CLICK [5] 'Engine, Cooling and Exhaust' → entered folder
2. CLICK [1] 'Engine' → entered folder
3. CLICK [17] 'Specifications' → entered folder

What's your next action?
```

## Backtracking Implementation

```python
async def handle_back(nav_stack: list, tree_path: list, page: Page) -> str:
    """Go back one level in navigation."""
    
    if tree_path:
        # In a folder - just pop from tree_path (same page)
        folder = tree_path.pop()
        return f"Exited folder: {folder}"
    elif nav_stack:
        # On a content page - need to actually go back
        nav_stack.pop()  # Remove current
        if nav_stack:
            prev_url, prev_tree = nav_stack[-1]
            await page.goto(prev_url)
            tree_path.clear()
            tree_path.extend(prev_tree)
            return f"Returned to: {prev_url}"
    
    return "Already at root"
```

## Rate Limiting

Gemini free tier has strict limits:

```python
DELAY_BETWEEN_CALLS = 5.0  # seconds

async def call_gemini(messages: list) -> str:
    await asyncio.sleep(DELAY_BETWEEN_CALLS)
    
    for attempt, backoff in enumerate([30, 60, 90]):
        response = await client.post(GEMINI_URL, json=payload)
        if response.status_code == 429:
            print(f"Rate limited, waiting {backoff}s...")
            await asyncio.sleep(backoff)
            continue
        return parse_response(response)
```

## Test Results

**10/10 tests passing** across diverse query types:

| Query Type | Example | Avg Steps |
|------------|---------|-----------|
| Specifications | Engine oil pressure | 6 |
| Locations | Choke relay location | 6 |
| Procedures | Timing chain tensioner | 6 |
| Capacities | Coolant capacity | 4 |
| Torque specs | Spark plug torque | 14* |

*\*Includes backtracking from wrong path*

## Key Design Principles

### 1. "Brain-Only" Model

The AI is just a brain with no persistence between steps. We must provide:
- **Eyes** = Page state (links list, page text)
- **Fingers** = Tools (click, back, extract)
- **Memory** = Path taken with results

### 2. Give Better Views, Not More Fences

When the AI makes mistakes, don't add restrictions. Instead, improve what we show it:
- Add page text preview so it can verify content
- Show path taken with action results
- Include content match warnings

### 3. Trust the AI

The AI (even small models like Gemini Flash) is smart enough to:
- Navigate complex hierarchies
- Recognize when it's on the wrong path
- Backtrack and try alternatives
- Extract relevant information

## Files

```
addons/autodb_agent/
├── test_ai_navigator.py      # Main implementation + tests
├── AI_NAVIGATOR_SPEC.md      # This document
└── build_full_index.py       # Alternative: pre-built index approach
```

## Reuse Guidelines

This pattern can be adapted for any hierarchical navigation task:

1. **Define the tree structure** - How to identify folders vs content
2. **Customize the system prompt** - Domain-specific navigation hints
3. **Adjust extraction logic** - What constitutes "found the answer"
4. **Tune rate limits** - Based on your LLM provider

### Example Adaptations

- **Documentation sites** - Navigate API docs to find method signatures
- **E-commerce** - Navigate category trees to find products
- **File systems** - Navigate directories to find files
- **Knowledge bases** - Navigate wiki structures to find articles

## Performance

- **Average steps to answer:** 6.6
- **Max steps with backtracking:** 14
- **Success rate:** 100% (on valid queries)
- **Time per query:** ~40-60 seconds (due to rate limiting)

## Future Improvements

1. **Parallel exploration** - Try multiple paths simultaneously
2. **Learning from history** - Cache successful navigation patterns
3. **Confidence scoring** - Rate how confident AI is in the answer
4. **Multi-page extraction** - Combine info from multiple pages
