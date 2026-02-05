# Autotech AI Troubleshooting Guide

Common issues and solutions for the Autotech AI platform.

---

## What to Expect

### Mitchell lookups take longer than regular AI responses

When you ask for vehicle data, the AI navigates through Mitchell's portal in real-time — clicking menus, selecting options, and extracting data. This typically takes **15-45 seconds** depending on what you're asking for.

**Quick lookups** (15-20 seconds):
- Fluid capacities
- Basic specs
- Torque values

**Longer lookups** (30-45 seconds):
- Wiring diagrams (images need to load)
- TSB searches
- Complex navigation paths

This is normal — you're getting live data from a professional repair database, not a cached answer.

---

## Getting Better Results

### Give the AI Navigation Hints

The AI navigates Mitchell's menus to find your data. If you know where something is located, **include that in your question** — it helps the AI find it faster.

**Examples:**

Without hint (AI has to figure it out):
> What's the spark plug gap for a 2019 Ford F-150 5.0?

With hint (AI goes straight there):
> What's the spark plug gap for a 2019 Ford F-150 5.0? It's in Common Specs.

**Helpful hints to include:**
- "Check in Fluid Capacities" — for oil, coolant, transmission fluid
- "Look in the Estimate Guide" — for parts pricing, labor times
- "It's under Wiring Diagrams" — for electrical schematics
- "Check Technical Bulletins" — for TSBs
- "Look in the DTC Index" — for trouble code info
- "Check Common Specs" — for gaps, pressures, capacities

### Be Specific with Vehicles

Always include:
- **Year** — 2019, not "late model"
- **Make** — Ford, not "domestic truck"
- **Model** — F-150, not "pickup"
- **Engine** — 5.0L V8, not "the V8" (important for specs that vary by engine)

For trucks, also specify when relevant:
- Drive type (2WD, 4WD)
- Cab type (Regular, SuperCrew)
- Bed length

If you don't specify, the AI will auto-select — check the response to see what it picked.

---

## Common Issues

### "No data found" or empty results

**Possible causes:**
- Vehicle not in Mitchell's database (rare/older vehicles)
- Missing details — need engine size or drive type
- AI auto-selected wrong vehicle option — retry with specific details

**Solution:** Be more specific with vehicle details. If it's a rare vehicle, data may simply not be available.

### Query takes a long time or times out

**Possible causes:**
- Mitchell agent is processing another request
- Agent lost connection to ShopKeyPro

**Solution:**
- Wait 30 seconds and try again
- If timeouts persist, contact support — the agent may need a restart

### Wiring diagram not displaying

**Possible causes:**
- Image still loading (large diagrams take a few seconds)
- Browser issue

**Solution:**
- Wait a few seconds for the image to appear
- Try refreshing the page
- Be more specific: "alternator wiring diagram" instead of just "charging system"

### Wrong vehicle was selected

**Cause:** AI auto-selects vehicle options (drive type, body style) when not specified.

**Solution:**
- Check the response header — it shows what was selected
- Retry with explicit details: "2019 F-150 5.0L 4WD SuperCrew"

---

## Account Issues

### Checking your token balance

Go to **Settings > Account** to see your current balance.

### Buying more tokens

Click **Token Dashboard** in the sidebar or go to **Settings > Account**.

### Tokens don't expire

Once purchased, tokens remain in your account until used.

---

## Using the Right Model

### AI gives a generic answer instead of looking up data

**Cause:** You're using a model without Mitchell tools enabled.

**Solution:** Use one of these models for vehicle lookups:
- **Autotech AI Expert** — Full Mitchell access
- **Mitchell Model** — Mitchell access
- **AutoDB** — Owner's manual data

The **Autotech AI Support** model explains the platform but doesn't look up vehicle data.

### How to tell if a model has tools

Look for the wrench icon (🔧) next to the model name, or check the model description.

---

## Saving Information

### Save feature didn't work

- Saves are per-user and go to your Knowledge collection
- Check **Workspace** in the sidebar for your saved items
- If missing, try the save action again

### Where are my saved items?

Look in **Workspace** in the left sidebar. Each save creates a Knowledge entry you can reference later.

---

## When to Contact Support

Contact support if you experience:
- Repeated timeouts that don't resolve
- Missing vehicles that should be in Mitchell's database
- Billing or account issues
- Bugs or unexpected behavior

---

## Quick Tips Summary

1. **Include navigation hints** — "Check in Fluid Capacities" speeds things up
2. **Be specific with vehicles** — Year, Make, Model, Engine at minimum
3. **Use the right model** — Autotech AI Expert or Mitchell Model for lookups
4. **Wait and retry** — Timeouts often resolve on retry
5. **Check what was selected** — AI shows auto-selected options in the response
