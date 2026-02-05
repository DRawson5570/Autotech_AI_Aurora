# AI Navigation System — The "Brain-Only" Approach

**Date:** 2026-01-15 (updated)
**Status:** Working Implementation ✅

## The Key Insight: AI is Just a Brain

The breakthrough came from understanding that **the AI (llama3.1:8b) has no persistence between steps**. It's just a brain in a jar — no eyes, no hands, no memory. We must provide all three:

```
┌─────────────────────────────────────────────────────────────────┐
│                   THE BRAIN-ONLY MODEL                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   🧠 AI = BRAIN ONLY                                            │
│      └─► Makes decisions, picks next action                     │
│      └─► No persistence between steps                           │
│      └─► No memory of what it just did                          │
│                                                                 │
│   👁️ EYES = Page State We Show It                               │
│      └─► Elements list with [id] prefixes                       │
│      └─► PAGE TEXT content (what's visible)                     │
│      └─► Modal open/closed status                               │
│                                                                 │
│   🖐️ FINGERS = Tools We Give It                                 │
│      └─► click(element_id) - Navigate by ID                     │
│      └─► click_text(text) - Navigate by text                    │
│      └─► extract(data) - Return found data (exits)              │
│      └─► collect(label, data) - Store data (continues)          │
│      └─► done(summary) - Return all collected (exits)           │
│      └─► capture_diagram() - Save image                         │
│      └─► go_back() - Close modal                                │
│                                                                 │
│   💭 SHORT-TERM MEMORY = Path Taken WITH RESULTS                │
│      └─► "CLICK 'Wiring Diagrams' → modal opened"               │
│      └─► "CLICK 'INDEX' → NOW ON INDEX PAGE!"                   │
│      └─► "COLLECT 'P0300' → stored, continue..."                │
│      └─► Each step shows WHAT HAPPENED after                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Works

**Before (without result hints):**
```
YOUR PATH SO FAR:
  1. CLICK 'Wiring Diagrams'
  2. CLICK 'INLINE HARNESS...'
  3. CLICK 'INDEX'
  4. CLICK 'INDEX'    ← AI doesn't know it's already there!
  5. CLICK 'INDEX'    ← Keeps clicking same thing
  6. CLICK 'INDEX'
```

The AI couldn't see that clicking INDEX already worked. It just saw "I clicked INDEX" with no feedback about what happened.

**After (with result hints):**
```
YOUR PATH SO FAR:
  1. CLICK 'Wiring Diagrams' → modal opened with diagram options
  2. CLICK 'INLINE HARNESS...' → NOW SHOWING CONNECTOR INDEX!
  3. CLICK 'X310 Body Harness' → connector detail page loaded
  4. EXTRACT → got the data!
```

Now the AI sees the RESULT of each action in its memory. It knows it's on the INDEX page and should click the specific connector, not INDEX again.

### Design Philosophy: Better View, Not More Fences

**Wrong approach:** Build "fences" to block bad actions
- Detect repeated clicks, block them
- Add rules about what can't be clicked
- More code, more edge cases, more bugs

**Right approach:** Give AI a better view of the room
- Show it what HAPPENED after each action
- It naturally makes the right decision
- Less code, more robust

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Navigation Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. LOGIN (Python - deterministic)                              │
│     └─► #username, #password, #loginButton                      │
│                                                                 │
│  2. VEHICLE SELECTION (Python - deterministic)                  │
│     └─► Year → Make → Model → Engine                            │
│                                                                 │
│  3. LANDING PAGE (AI takes over here)                           │
│     ┌─────────────────────────────────────────────────────────┐ │
│     │  Quick Access Buttons:                                  │ │
│     │  [Technical Bulletins] [Common Specs] [Driver Assist]   │ │
│     │  [Fluid Capacities] [Tire Info] [Reset Procedures]      │ │
│     │  [DTC Index] [Wiring Diagrams] [Component Locations]    │ │
│     │  [Component Tests] [Service Manual]                     │ │
│     └─────────────────────────────────────────────────────────┘ │
│                                                                 │
│  4. AI NAVIGATION (with result hints)                           │
│     └─► System prompt has navigation "cheat sheet"              │
│     └─► Each step shows WHAT HAPPENED after clicking            │
│     └─► AI picks next action based on current state + memory    │
│                                                                 │
│  5. LOGOUT (Python - always, even on error)                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## System Prompt: The Cheat Sheet

The system prompt contains STATIC navigation paths — a "cheat sheet" the AI references:

```
NAVIGATION PATHS (your cheat sheet):

CONNECTOR END VIEWS (for pinouts, connector images):
  Wiring Diagrams → "INLINE HARNESS CONNECTOR..." (for X200, X310, body harness)
  Wiring Diagrams → "COMPONENT CONNECTOR..." (for A11 Radio, K20 ECM, sensors)

WIRING DIAGRAMS (for circuit diagrams):
  Wiring Diagrams → "SYSTEM WIRING DIAGRAMS" → category (Starting/Charging, etc.)

SPECIFICATIONS:
  Fluid Capacities → extract data
  Common Specs → look for torque, gap values
```

The AI matches the user's goal to a path and follows it. Result hints tell it when it's arrived.

## Result Hints: The Secret Sauce

Result hints are added to the path after each tool execution:

```python
# After tool execution
if tool_result.success and tool_name in ("click", "click_text"):
    if "wiring diagram" in clicked_text:
        step_record["result_hint"] = "modal opened with diagram options"
    elif "inline harness" in clicked_text:
        step_record["result_hint"] = "NOW SHOWING CONNECTOR INDEX - click on your specific connector!"
    elif clicked_text.startswith("x") and any(c.isdigit() for c in clicked_text):
        step_record["result_hint"] = "CONNECTOR DETAIL PAGE - extract the Description field!"
```

Key hints:
| After Clicking | Result Hint |
|----------------|-------------|
| Wiring Diagrams | "modal opened with diagram options" |
| INLINE HARNESS... | "NOW SHOWING CONNECTOR INDEX - click on your specific connector!" |
| COMPONENT CONNECTOR... | "NOW SHOWING COMPONENT INDEX - click on A11, K20, etc!" |
| X310, X200, etc. | "CONNECTOR DETAIL PAGE - extract the Description field!" |
| A11, K20, etc. | "CONNECTOR DETAIL PAGE - extract the Description field!" |

## Test Results

| Query | Steps (before) | Steps (after) |
|-------|---------------|---------------|
| Body harness to driver seat connector | 9+ (5 wasted INDEX clicks) | 4 |
| Radio connector A11 pinout | 10 (kept extracting wrong data) | 4 |

## Files

| File | Purpose |
|------|---------|
| `autonomous_navigator.py` | Main navigator with brain-only model |
| `element_extractor.py` | Extracts clickable elements from page |
| `ollama_navigator.py` | Ollama API wrapper |

## Usage

```bash
# Test with any goal
cd /home/drawson/autotech_ai
conda run -n open-webui python addons/mitchell_agent/ai_navigator/autonomous_navigator.py "body harness connector pinout"
```

## What We Learned

1. **AI has no memory** — Every step it sees fresh context. Show it the path taken WITH results.

2. **Don't build fences** — Instead of blocking bad actions, give AI better information to make good decisions naturally.

3. **Result hints are key** — Telling the AI "NOW ON INDEX PAGE" prevents it from clicking INDEX again.

4. **Static cheat sheet works** — No need for learning/memory system. A good system prompt with navigation paths is enough.

5. **Human + AI = 🔥** — The human understands the problem (AI keeps clicking INDEX). The AI implements solutions fast. Together we went from 10 steps to 4 in minutes.

## Previous Approaches (Deprecated)

### Navigation Memory (removed)
We tried a learning memory system that recorded successful paths. Removed because:
- Added complexity without clear benefit
- Static cheat sheet in system prompt works just as well
- Memory didn't help with the real problem (AI not knowing what happened after clicks)

### Complex Fencing (avoided)
We considered adding rules to block repeated clicks, detect loops, etc. Avoided because:
- More code = more bugs

## TRUST THE AI — The Ultimate Lesson (2026-01-14)

**The breakthrough:** Remove hand-holding code, trust the AI.

### What We Removed

**Verbatim validation** — The extract() function used to check if the AI's string existed verbatim on the page:
```python
# REMOVED - This rejected valid AI output
if data_normalized not in page_normalized:
    return ToolResult("extract", False, "not found on page")
```

The problem: AI would see `Starter Mounting Bolts - 3.7L: 54 N.m / 40 Ft. Lbs.` and call `extract("Starter Mounting Bolts: 54 N.m (40 Ft. Lbs.)")`. Same data, different formatting. Validation rejected it.

**Auto-extractors** — We had special-case code for each query type:
- Fluid queries → auto-extract modal content
- Torque queries → auto-extract modal content  
- Spec queries → auto-extract modal content

This was "hand-holding" — doing the AI's job for it.

### What We Kept (Guardrails)

**Sanity checks** — These catch when AI grabs the WRONG type of data:
- Torque query but data has no ft-lb/N.m → reject
- Gap query but data has torque units → reject
- Capacity query but data has torque units → reject

These are guardrails, not hand-holding. They catch obvious mistakes, not formatting differences.

### Results

| Change | Impact |
|--------|--------|
| -52 lines of code | Less maintenance, fewer bugs |
| "wheel lug nut torque" | Found in 2 steps |
| "brake caliper bolt torque" | AI asked for clarification |
| "give me all of them" | AI delivered both specs + safety warning |

### The Rule

**When AI fails, ask:**
1. ❌ "How do we force it to do the right thing?" (hand-holding)
2. ✅ "What did WE not show it?" (better view)
3. ✅ "Is this actually a failure, or just different formatting?" (trust)

**Teach it to fish. Don't hand it fish.**
- Treating symptoms, not cause
- Better to give AI good information than restrict its actions

The AI should have baseline knowledge of what data lives where:

| Quick Access Button | Likely Contains |
|---------------------|-----------------|
| Fluid Capacities | Oil capacity, coolant, transmission fluid, oil drain plug torque |
| Common Specs | Lug nut torque, wheel specs, general measurements |
| Tire Information | Tire sizes, pressures, TPMS info, lifting points |
| DTC Index | Diagnostic trouble codes, meanings, procedures |
| Wiring Diagrams | Electrical diagrams, circuits, connectors |
| Reset Procedures | Oil life reset, TPMS reset, maintenance resets |
| Technical Bulletins | TSBs, recalls, campaigns |
| Driver Assist ADAS | Calibration procedures, camera/radar info |
| Component Locations | Physical locations, mounting points |
| Component Tests | Test procedures, diagnostic tests |
| Service Manual | Full repair procedures (fallback) |

This mapping helps the AI rank candidates intelligently without having learned anything yet.

## Implementation Components

### Files

```
ai_navigator/
├── __init__.py
├── element_extractor.py    # Extract interactive elements from page
├── ai_navigator.py         # Gemini decision making
├── action_executor.py      # Execute clicks, typing, etc.
├── navigation_loop.py      # Main orchestration loop
├── navigation_memory.py    # Learning/memory system
└── AI_NAVIGATION_SPEC.md   # This document
```

### Navigation Loop Flow

```python
async def navigate_with_learning(goal: str, vehicle: dict):
    memory = get_memory()
    
    # Check if we already know a path
    hint = memory.get_hints_for_prompt(goal)
    
    # AI plans candidates (using hint if available)
    candidates = await ai.plan_candidates(goal, page_elements, hint)
    
    # Try each candidate
    for candidate_path in candidates:
        # Ensure we're at landing page
        await ensure_at_landing_page()
        
        # Track this attempt
        current_path = []
        
        # Follow the candidate path
        for selector in candidate_path:
            success = await click(selector)
            if success:
                current_path.append(selector)
            else:
                break  # Path blocked
        
        # Check if we found the data
        data = await try_extract_data(goal)
        
        if data:
            # SUCCESS! Record this path
            memory.record_success(goal, current_path)
            return data
        else:
            # Dead end - record failure, backtrack
            memory.record_failure(goal, current_path)
            await backtrack_to_landing()
    
    # All candidates exhausted
    return None
```

## Critical Rules

1. **Always logout** - Even on error. Use `finally` block.
2. **One path at a time** - Don't mix exploration across paths.
3. **Clean backtrack** - Return to landing page between attempts.
4. **Record only winners** - The successful path, not exploration history.
5. **Check memory first** - Don't re-explore known paths.

## Selectors Reference

### Landing Page Quick Access

| Button | Selector |
|--------|----------|
| Technical Bulletins | `#tsbQuickAccess` |
| Common Specs | `#commonSpecsAccess` |
| Driver Assist ADAS | `#adasCalibrationAccess` |
| Fluid Capacities | `#fluidsQuickAccess` |
| Tire Information | `#tpmsTireFitmentQuickAccess` |
| Reset Procedures | `#resetProceduresAccess` |
| DTC Index | `#dtcIndexAccess` |
| Wiring Diagrams | `#wiringDiagramsAccess` |
| Component Locations | `#componentLocationsAccess` |
| Component Tests | `#componentTestsAccess` |
| Service Manual | `#serviceManualAccess` |

### Modal Close

- Primary: `.modalDialogView .close`
- Alt: `input[data-action='Cancel']`
- Alt: `.modalDialogView span.close`

### Verify Landing Page

Check that Quick Access buttons are visible:
```javascript
document.querySelector('#fluidsQuickAccess')?.offsetParent !== null
```

## Reinforcement Fine-Tuning (RFT)

**Date Added:** 2026-01-10
**Status:** Experimental

### The Problem

Small local models (Llama 3.1 8B) make poor section routing decisions:
- "spark plug gap" → clicks Fluid Capacities (wrong!)
- No domain knowledge about automotive data organization

### The Solution: GRPO Training

Based on OpenAI's Reinforcement Fine-Tuning approach:
https://colab.research.google.com/github/openai/gpt-oss/blob/main/examples/reinforcement-fine-tuning.ipynb

Instead of supervised learning with labeled examples, the model learns by:
1. **Trying** - Pick an element and click it
2. **Getting feedback** - Reward signals based on result
3. **Improving** - Update weights via GRPO algorithm

### Reward Functions

```python
REWARD_FUNCTIONS:
1. valid_selection   - Did it output valid JSON with element_id?
   +1.0: Valid response
   -2.0: Invalid/malformed

2. correct_section   - Did it click the RIGHT section?
   +10.0: Perfect match (e.g., "oil capacity" → Fluid Capacities)
   +2.0: Partial match
   -5.0: Wrong section (e.g., "spark plug gap" → Fluid Capacities)

3. found_data        - Did extraction find relevant keywords?
   +5.0: Found multiple expected keywords
   +2.0: Found some keywords
   -3.0: Found nothing relevant
```

### Training Data Collection

File: `rft_live_training.py`

```bash
# Collect 100 training episodes
python -m addons.mitchell_agent.ai_navigator.rft_live_training --episodes 100
```

This runs live browser sessions:
1. Pick random query from query bank
2. Let AI see page and decide
3. Click and see what happens
4. Compute rewards
5. Save to `/tmp/rft_training_data.jsonl`

### GRPO Fine-Tuning

File: `grpo_finetune.py`

```bash
# Requires GPU + Unsloth
python -m addons.mitchell_agent.ai_navigator.grpo_finetune --steps 200
```

Uses Unsloth + TRL to fine-tune a small model:
- Qwen2.5-1.5B-Instruct (recommended)
- Phi-3-mini (3.8B, higher quality)
- Llama-3.2-1B-Instruct

### Query Bank

Located in `rft_training.py`, maps queries to expected sections:

```python
QUERY_BANK = {
    "spark plug gap": {
        "expected_section": "Common Specs",
        "validation_keywords": ["gap", "mm", "inch", "spark"],
    },
    "engine oil capacity": {
        "expected_section": "Fluid Capacities",
        "validation_keywords": ["qt", "quart", "liter", "oil"],
    },
    # ... 20+ queries covering all sections
}
```

### Architecture After Fine-Tuning

```
┌─────────────────────────────────────────────────────────────────┐
│                     Two-Model Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Query: "spark plug gap for 2019 Honda Accord"             │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  FINE-TUNED 1.5B MODEL (Section Router)                 │    │
│  │  Input: Query + Landing Page Elements                   │    │
│  │  Output: element_id: 19 (Common Specs)                  │    │
│  │  Speed: ~50ms                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  LARGER MODEL (Deep Navigation / Extraction)            │    │
│  │  Handles: Sub-navigation, data extraction, reasoning    │    │
│  │  Could be: Llama 8B, Gemini, or cloud API               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│                      Extracted Data                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Files

```
ai_navigator/
├── rft_training.py        # Query bank + reward functions
├── rft_live_training.py   # Live browser data collection
├── grpo_finetune.py       # GRPO training script (GPU required)
└── ...
```

## Future Enhancements

1. **Multi-step paths** - For nested navigation (Wiring → Category → Subcategory)
2. **Semantic similarity** - Match "oil change specs" to "oil drain plug torque"
3. **Confidence scoring** - Weight paths by success rate
4. **Path optimization** - If path A works but path B is shorter, prefer B
5. **Negative learning** - Remember what definitely ISN'T in each section
6. **Fine-tuned routing model** - Deploy GRPO-trained 1.5B model for section routing
