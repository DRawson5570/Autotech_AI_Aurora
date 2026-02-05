# YouTube Video Search Tool

Open WebUI tool that searches YouTube for automotive repair videos from trusted channels using SearXNG.

## Installation

1. Copy the contents of `openwebui_tool.py`
2. Go to Open WebUI → Admin → Tools → Add Tool
3. Paste the code
4. Save

## Configuration

Edit the tool code to customize:

- `searxng_url` - Your SearXNG instance (default: `http://localhost:8082`)
- `trusted_channels` - List of preferred YouTube channels

### Trusted Channels (default)

- ChrisFix
- South Main Auto Repair
- Scanner Danner
- Pine Hollow Auto Diagnostics
- Weber Auto
- Rainman Ray's Repairs
- Watch Wes Work
- FordTechMakuloco
- EricTheCarGuy
- Scotty Kilmer
- 1A Auto

## Usage

Ask naturally:
- "Video on how to replace alternator on 2015 Honda Civic"
- "Show me a video about brake pad replacement"
- "YouTube tutorial for oil change on F150"

The tool will:
1. Search YouTube via SearXNG
2. Prioritize results from trusted automotive channels
3. Return the best match with thumbnail and link
4. Show additional results as alternatives

## Requirements

- SearXNG instance with YouTube engine enabled
- On prod: SearXNG runs at `http://localhost:8082` (poweredge1)
