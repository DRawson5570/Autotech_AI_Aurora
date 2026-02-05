"""
Autodb Navigator - Hybrid navigation for Operation CHARM site.

Uses a deterministic approach for common queries (oil capacity, coolant, etc.)
with AI fallback for complex/unknown queries.

Unlike Mitchell (complex web app), autodb is simple static HTML.
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("autodb_navigator")

# Default to Ollama for local testing, can override to Gemini
DEFAULT_MODEL = os.environ.get("AUTODB_MODEL", "llama3.1:8b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

BASE_URL = os.environ.get("AUTODB_BASE_URL", "http://automotive.aurora-sentient.net/autodb")

# Direct URL patterns for common queries
# Format: (keywords, url_path_suffix)
# These are appended to the vehicle's Repair and Diagnosis path
DIRECT_URL_PATTERNS = [
    # Oil capacity - goes directly to the Engine Oil capacity page
    (["oil", "capacity"], "Specifications/Capacity%20Specifications/Engine%20Oil/"),
    (["engine oil", "capacity"], "Specifications/Capacity%20Specifications/Engine%20Oil/"),
    (["oil capacity"], "Specifications/Capacity%20Specifications/Engine%20Oil/"),
    
    # Coolant
    (["coolant", "capacity"], "Specifications/Capacity%20Specifications/Coolant/"),
    (["coolant", "type"], "Specifications/Fluid%20Type%20Specifications/Coolant/"),
    
    # Transmission - note: %2F is encoded slash for Automatic Transmission/Transaxle
    # Needs System Specifications subpage for capacity data
    (["transmission", "capacity"], "Specifications/Capacity%20Specifications/Automatic%20Transmission%2FTransaxle/System%20Specifications/"),
    (["transmission fluid", "type"], "Specifications/Fluid%20Type%20Specifications/Automatic%20Transmission%2FTransaxle/System%20Specifications/"),
    (["trans fluid"], "Specifications/Capacity%20Specifications/Automatic%20Transmission%2FTransaxle/System%20Specifications/"),
    (["transmission fluid"], "Specifications/Capacity%20Specifications/Automatic%20Transmission%2FTransaxle/System%20Specifications/"),
    (["atf"], "Specifications/Capacity%20Specifications/Automatic%20Transmission%2FTransaxle/System%20Specifications/"),
    
    # Transfer case
    (["transfer case", "capacity"], "Specifications/Capacity%20Specifications/Transfer%20Case/"),
    (["transfer case", "fluid"], "Specifications/Fluid%20Type%20Specifications/Transfer%20Case/"),
    
    # Differential - note: Differential Assembly is the actual folder name
    # Needs System Specifications subpage for capacity data
    (["differential", "capacity"], "Specifications/Capacity%20Specifications/Differential%20Assembly/System%20Specifications/"),
    (["differential", "fluid"], "Specifications/Fluid%20Type%20Specifications/Differential%20Assembly/System%20Specifications/"),
    (["diff fluid"], "Specifications/Capacity%20Specifications/Differential%20Assembly/System%20Specifications/"),
    (["axle fluid"], "Specifications/Capacity%20Specifications/Differential%20Assembly/System%20Specifications/"),
    
    # Engine torque specs
    (["torque", "spec"], "Specifications/Mechanical%20Specifications/Engine/System%20Specifications/Engine%20Torque%20Specifications/"),
    (["engine torque"], "Specifications/Mechanical%20Specifications/Engine/System%20Specifications/Engine%20Torque%20Specifications/"),
    
    # Brake specs
    (["brake", "spec"], "Specifications/Mechanical%20Specifications/Brakes%20and%20Traction%20Control/"),
    (["brake pad"], "Specifications/Mechanical%20Specifications/Brakes%20and%20Traction%20Control/Brake%20Pad/"),
    (["brake rotor"], "Specifications/Mechanical%20Specifications/Brakes%20and%20Traction%20Control/Brake%20Rotor%2FDisc/"),
    
    # Tire/wheel specs
    (["tire", "pressure"], "Specifications/Mechanical%20Specifications/Wheels%20and%20Tires/System%20Specifications/"),
    (["tire", "size"], "Specifications/Mechanical%20Specifications/Wheels%20and%20Tires/Tires/"),
    (["wheel", "torque"], "Specifications/Mechanical%20Specifications/Wheels%20and%20Tires/Wheel%20Stud%20%2F%20Lug%20Nut/"),
    (["lug nut"], "Specifications/Mechanical%20Specifications/Wheels%20and%20Tires/Wheel%20Stud%20%2F%20Lug%20Nut/"),
    (["tpms"], "Specifications/Mechanical%20Specifications/Wheels%20and%20Tires/Tire%20Monitoring%20System/"),
    
    # Spark plug
    (["spark plug"], "Specifications/Mechanical%20Specifications/Ignition%20System/Spark%20Plug/Spark%20Plug%20Specifications/"),
    (["spark plug torque"], "Specifications/Mechanical%20Specifications/Ignition%20System/Spark%20Plug/Torque/"),
    (["firing order"], "Specifications/Mechanical%20Specifications/Ignition%20System/Firing%20Order/"),
    
    # Battery
    (["battery", "spec"], "Specifications/Electrical%20Specifications/Battery/"),
    
    # DTCs
    (["dtc"], "Diagnostic%20Trouble%20Codes/"),
    (["trouble code"], "Diagnostic%20Trouble%20Codes/"),
    
    # TSBs
    (["tsb"], "Technical%20Service%20Bulletins/"),
    (["technical service bulletin"], "Technical%20Service%20Bulletins/"),
]


def get_gemini_api_key() -> Optional[str]:
    """Load Gemini API key from environment or file."""
    # Try environment variable first
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    # Try file fallback
    for path in [
        os.path.expanduser("~/gary_gemini_api_key"),
        "/home/drawson/.config/gemini/api_key.txt",
    ]:
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return None


@dataclass
class PageState:
    """Current state of the page for AI to see."""
    url: str
    title: str
    breadcrumb: List[str]
    links: List[Dict[str, str]]  # [{text, href}]
    content_preview: str
    

@dataclass 
class NavigationResult:
    """Result from navigation."""
    success: bool
    content: str = ""
    url: str = ""
    breadcrumb: str = ""
    error: str = ""
    path_taken: List[str] = field(default_factory=list)
    tokens_used: Dict[str, int] = field(default_factory=dict)  # For billing


class AutodbNavigator:
    """
    Navigator for Operation CHARM (autodb) site.
    Uses HTTP requests + LLM to navigate static HTML.
    """
    
    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.session = httpx.AsyncClient(timeout=30, follow_redirects=True)
        self.max_steps = 15
        log.info(f"AutodbNavigator initialized: model={self.model}, base_url={self.base_url}")
    
    async def close(self):
        """Close HTTP session."""
        await self.session.aclose()
    
    def _match_direct_url(self, goal: str, vehicle: dict) -> Optional[str]:
        """
        Try to match the goal to a direct URL pattern.
        Returns the full URL if matched, None otherwise.
        """
        goal_lower = goal.lower()
        
        for keywords, path_suffix in DIRECT_URL_PATTERNS:
            # Check if all keywords are in the goal
            if all(kw in goal_lower for kw in keywords):
                # Build the full URL
                base = self._build_vehicle_url(vehicle).rstrip("/")
                # Remove "Repair%20and%20Diagnosis/" if it's already in base
                if base.endswith("Repair%20and%20Diagnosis"):
                    full_url = f"{base}/{path_suffix}"
                else:
                    full_url = f"{base}/Repair%20and%20Diagnosis/{path_suffix}"
                log.info(f"Direct URL match: '{goal}' -> {full_url}")
                return full_url
        
        return None
    
    async def _fetch_page(self, url: str) -> str:
        """Fetch a page and return HTML."""
        if not url.startswith("http"):
            url = f"{self.base_url}/{url.lstrip('/')}"
        response = await self.session.get(url)
        response.raise_for_status()
        return response.text
    
    def _parse_page_state(self, html: str, url: str) -> PageState:
        """Parse HTML into a PageState for the AI."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Get title
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""
        
        # Get breadcrumb
        breadcrumb = []
        breadcrumb_div = soup.select_one(".breadcrumbs")
        if breadcrumb_div:
            for a in breadcrumb_div.find_all("a"):
                text = a.get_text(strip=True)
                if text:
                    breadcrumb.append(text)
        
        # Get links (navigation options)
        # Only include links with href (name-only are tree nodes without pages)
        links = []
        seen_hrefs = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            
            # Skip empty, home links, breadcrumbs
            if not href or not text or text.lower() == "home":
                continue
            if a.find_parent(class_="breadcrumbs"):
                continue
            
            # Make URLs absolute
            if not href.startswith("http"):
                if href.startswith("/"):
                    # Absolute path like /autodb/...
                    href = f"{self.base_url.rsplit('/autodb', 1)[0]}{href}"
                else:
                    # Relative to current URL
                    href = f"{url.rstrip('/')}/{href.rstrip('/')}"
            
            # Dedupe by href
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            
            # Calculate depth (number of path segments in the link)
            depth = href.count('/') - url.count('/')
            links.append({"text": text, "href": href, "depth": depth})
        
        # DON'T sort or filter here - let _build_user_message do goal-aware filtering
        # This preserves all links so the scorer can find the best matches
        
        # Get content preview (text from paragraphs, tables)
        content_parts = []
        for tag in soup.select(".main p, .main table, .main h2, .main h3"):
            text = tag.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                content_parts.append(text[:500])
        content_preview = "\n".join(content_parts[:10])
        
        return PageState(
            url=url,
            title=title,
            breadcrumb=breadcrumb,
            links=links,  # Pass ALL links - _build_user_message will score and filter
            content_preview=content_preview[:2000]
        )
    
    def _build_system_prompt(self, goal: str, vehicle: dict) -> str:
        """Build system prompt for the AI navigator."""
        year = vehicle.get('year', '')
        make = vehicle.get('make', '')
        model = vehicle.get('model', '')
        
        return f"""You are navigating an automotive service manual website to find information.

=== YOUR TARGET ===
Vehicle: {year} {make} {model}
Goal: {goal}

=== NAVIGATION STRATEGY ===
1. FIRST find the MAKE (look for "{make}" or "{make} Truck" - SUVs/trucks are under "Make Truck")
2. THEN find the YEAR: {year}
3. THEN find the MODEL that matches "{model}" (exact match not required - find closest)
4. THEN click "Repair and Diagnosis" or "Specifications" to find data
5. THEN navigate deeper to find "{goal}" content
6. FINALLY use "extract" ONLY when you see actual data values (numbers, specs)

=== TOOLS (respond with JSON only) ===
- Click a link: {{"tool": "click", "args": {{"link_text": "Link Text (path: shown/path/here)"}}}}  
- Go back: {{"tool": "go_back"}}
- Extract content: {{"tool": "extract"}}

IMPORTANT: When clicking a link, include the full "(path: ...)" from the link display to avoid ambiguity!

=== CRITICAL RULES ===
- Look for "{make}" first - ignore other makes!
- SUVs like Jeep, Honda CR-V are often under "{make} Truck"
- DO NOT extract until you see actual data values!
- If you only see category links (like "Repair and Diagnosis"), keep clicking to go deeper!
- Use "extract" when you see the actual {goal} data

Respond with JSON only. Find {goal} for {year} {make} {model}."""

    def _build_user_message(self, page_state: PageState, path_taken: List[str], goal: str, vehicle: dict = None) -> str:
        """Build user message showing current page state."""
        vehicle = vehicle or {}
        year = vehicle.get('year', '').lower()
        make = vehicle.get('make', '').lower()
        model = vehicle.get('model', '').lower()
        
        goal_lower = goal.lower()
        goal_words = set(goal_lower.split())
        
        # Detect which navigation stage we're in based on URL
        url_lower = page_state.url.lower()
        url_decoded = unquote(url_lower)
        
        # Better stage detection - check what's in the URL path
        is_homepage = url_lower.endswith('/autodb/') or url_lower.endswith('/autodb')
        is_make_page = make and make in url_decoded and year not in url_decoded
        
        # Model matching is tricky - check if any model words are in URL
        model_words = [w.lower() for w in model.split() if len(w) > 2] if model else []
        model_in_url = any(w in url_decoded for w in model_words)
        
        is_year_page = year and year in url_decoded and not model_in_url
        
        # Inside model = model words in URL (we've selected the vehicle)
        is_inside_model = model_in_url
        
        log.debug(f"Stage detection: homepage={is_homepage}, make={is_make_page}, year={is_year_page}, inside_model={is_inside_model}")
        
        def score_link(link):
            """Score a link by how well it matches what we need at this stage."""
            text_lower = link["text"].lower()
            href_lower = unquote(link.get("href", "")).lower()
            score = 0
            
            # === STAGE-BASED SCORING ===
            
            if is_homepage:
                # On homepage: prioritize the TARGET MAKE
                if make:
                    # Exact make match
                    if text_lower == make or text_lower == f"{make} truck":
                        score += 1000  # This is exactly what we want!
                    elif make in text_lower:
                        score += 500
                    else:
                        score = -500  # Wrong make, hide it
                        
            elif is_make_page:
                # On make page: prioritize the TARGET YEAR
                if year:
                    if text_lower == year:
                        score += 1000
                    # Check if it's a year link (4 digits)
                    try:
                        if text_lower.isdigit() and len(text_lower) == 4:
                            if text_lower == year:
                                score += 1000
                            else:
                                score = -500  # Wrong year
                    except:
                        pass
                        
            elif is_year_page:
                # On year page: prioritize the TARGET MODEL
                if model:
                    model_words_for_match = model.split()
                    matches = sum(1 for w in model_words_for_match if w.lower() in text_lower)
                    if matches > 0:
                        score += matches * 200
                    else:
                        score = -200  # Wrong model
            
            elif is_inside_model:
                # Inside model - navigate toward goal content
                # STRONGEST bonus: exact link with goal-relevant path
                if "oil" in goal_lower and text_lower == "engine oil":
                    if "capacity" in href_lower:
                        score += 1000  # Perfect match! Engine Oil under Capacity Specifications
                    else:
                        score += 100  # Right topic but maybe not the capacity page
                        
                if "coolant" in goal_lower and text_lower == "coolant":
                    if "capacity" in href_lower:
                        score += 1000
                    else:
                        score += 100
                        
                if "torque" in goal_lower and "torque" in text_lower.lower():
                    score += 400
                    
                # Boost links in the right path
                if "capacity" in goal_lower or "oil" in goal_lower or "coolant" in goal_lower:
                    if "capacity" in href_lower and "specifications" in href_lower:
                        score += 300  # This path leads to capacities
                
                # For electrical/charging queries, boost relevant sections
                if any(w in goal_lower for w in ["starting", "charging", "battery", "alternator", "starter"]):
                    if any(w in href_lower for w in ["starting", "charging", "battery", "alternator", "starter"]):
                        score += 500
                    if any(w in text_lower for w in ["starting", "charging", "battery", "alternator", "starter"]):
                        score += 300
                
                # General goal word matching - STRONGER for multi-word matches
                matching_words = sum(1 for word in goal_words if word in text_lower)
                if matching_words > 0:
                    score += matching_words * 100  # Increased from 10
                
                matching_href_words = sum(1 for word in goal_words if word in href_lower)
                if matching_href_words > 0:
                    score += matching_href_words * 50  # Increased from 5
                    
                # Penalty for completely unrelated sections
                if text_lower in ["diagnostic trouble codes", "technical service bulletins", 
                                  "a l l  diagnostic trouble codes ( dtc )"]:
                    if "dtc" not in goal_lower and "code" not in goal_lower and "tsb" not in goal_lower:
                        score -= 200  # Strong penalty for unrelated sections
            
            return score
        
        # Score and sort links
        scored_links = [(link, score_link(link)) for link in page_state.links]
        scored_links.sort(key=lambda x: -x[1])  # Highest score first
        
        # Filter: show positive scores, then a few neutral/negative
        positive_links = [link for link, score in scored_links if score > 0]
        other_links = [link for link, score in scored_links if score <= 0][:10]
        shown_links = positive_links[:30] + other_links
        
        # Dedupe
        seen = set()
        unique_links = []
        for link in shown_links:
            if link["text"] not in seen:
                seen.add(link["text"])
                unique_links.append(link)
        shown_links = unique_links[:20]
        
        # Build link display with path context
        link_lines = []
        for l in shown_links:
            href = l.get("href", "")
            path_parts = [unquote(p) for p in href.rstrip("/").split("/") if p]
            if len(path_parts) >= 2:
                path_hint = "/".join(path_parts[-3:])
            else:
                path_hint = href
            link_lines.append(f"  - {l['text']} (path: {path_hint})")
        links_text = "\n".join(link_lines)
        
        # DEBUG: Log what we're showing the LLM
        log.info(f"Showing LLM {len(shown_links)} links:")
        for l in shown_links[:10]:
            log.info(f"  {l['text']}")
        
        return f"""CURRENT PAGE STATE:
URL: {page_state.url}
Title: {page_state.title}
Breadcrumb: {' >> '.join(page_state.breadcrumb)}

AVAILABLE LINKS (most relevant first):
{links_text}

CONTENT PREVIEW:
{page_state.content_preview[:1000]}

PATH TAKEN SO FAR:
{' -> '.join(path_taken) if path_taken else '(start)'}

What's your next action? Respond with JSON."""

    async def _call_llm(self, system_prompt: str, user_message: str) -> dict:
        """Call the LLM and parse response."""
        if self.model.startswith("gemini"):
            return await self._call_gemini(system_prompt, user_message)
        else:
            return await self._call_ollama(system_prompt, user_message)
    
    async def _call_gemini(self, system_prompt: str, user_message: str) -> dict:
        """Call Gemini API."""
        api_key = get_gemini_api_key()
        if not api_key:
            raise RuntimeError("Gemini API key not found")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
            }
        }
        
        response = await self.session.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract text from Gemini response
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        # Extract token usage for billing
        usage = {}
        usage_meta = data.get("usageMetadata", {})
        if usage_meta:
            usage = {
                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                "total_tokens": usage_meta.get("totalTokenCount", 0)
            }
        
        return {"content": text, "usage": usage}
    
    async def _call_ollama(self, system_prompt: str, user_message: str) -> dict:
        """Call Ollama API."""
        url = f"{OLLAMA_URL}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        
        response = await self.session.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # Extract token usage for billing (Ollama format)
        usage = {}
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        if prompt_tokens or completion_tokens:
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        
        return {"content": data.get("message", {}).get("content", ""), "usage": usage}
    
    def _parse_llm_response(self, content: str) -> dict:
        """Parse LLM response to extract tool call."""
        log.debug(f"Parsing LLM response: {content[:500]}")
        
        # Try to find JSON with nested braces (for args object)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', content, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                log.debug(f"Parsed JSON: {parsed}")
                
                # If response has link_text but no tool, assume click
                if "link_text" in parsed and "tool" not in parsed:
                    return {"tool": "click", "args": {"link_text": parsed["link_text"]}}
                
                return parsed
            except json.JSONDecodeError as e:
                log.debug(f"JSON decode error: {e}")
        
        # Fallback: look for patterns
        if "extract" in content.lower():
            return {"tool": "extract"}
        
        # Look for link text in quotes
        link_match = re.search(r'click.*?["\']([^"\']+)["\']', content, re.IGNORECASE)
        if link_match:
            return {"tool": "click", "args": {"link_text": link_match.group(1)}}
        
        return {"tool": "unknown", "raw": content[:200]}
    
    async def navigate(self, goal: str, vehicle: dict) -> NavigationResult:
        """
        Navigate the site to find information matching the goal.
        
        Args:
            goal: What to find (e.g., "oil capacity", "P0300 DTC")
            vehicle: Dict with year, make, model, engine
        
        Returns:
            NavigationResult with success status and content
        """
        log.info(f"Starting navigation: goal='{goal}', vehicle={vehicle}")
        
        # Track cumulative token usage for billing
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        # Always start from homepage - let AI navigate naturally
        # This handles misspellings, variations, etc.
        start_url = self.base_url
        path_taken = []
        history = []  # For go_back
        current_url = start_url
        
        for step in range(self.max_steps):
            log.info(f"Step {step + 1}: Fetching {current_url}")
            
            try:
                html = await self._fetch_page(current_url)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # Try fallback to base URL
                    if current_url != self.base_url:
                        log.warning(f"404 at {current_url}, falling back to home")
                        current_url = self.base_url
                        continue
                return NavigationResult(
                    success=False, 
                    error=f"HTTP {e.response.status_code}: {current_url}",
                    path_taken=path_taken,
                    tokens_used=total_tokens
                )
            
            page_state = self._parse_page_state(html, current_url)
            
            # Build prompts
            system_prompt = self._build_system_prompt(goal, vehicle)
            user_message = self._build_user_message(page_state, path_taken, goal, vehicle)
            
            # Ask AI what to do
            try:
                llm_response = await self._call_llm(system_prompt, user_message)
                # Accumulate token usage
                step_usage = llm_response.get("usage", {})
                if step_usage:
                    total_tokens["prompt_tokens"] += step_usage.get("prompt_tokens", 0)
                    total_tokens["completion_tokens"] += step_usage.get("completion_tokens", 0)
                    total_tokens["total_tokens"] += step_usage.get("total_tokens", 0)
            except Exception as e:
                log.error(f"LLM error: {e}")
                return NavigationResult(success=False, error=f"LLM error: {e}", path_taken=path_taken, tokens_used=total_tokens)
            
            action = self._parse_llm_response(llm_response.get("content", ""))
            tool = action.get("tool", "unknown")
            
            log.info(f"Step {step + 1}: AI action = {action}")
            
            if tool == "extract":
                # Extract content from current page
                content = self._extract_content(html, goal)
                log.info(f"[TOKENS] Total: {total_tokens['total_tokens']} (prompt: {total_tokens['prompt_tokens']}, completion: {total_tokens['completion_tokens']})")
                return NavigationResult(
                    success=True,
                    content=content,
                    url=current_url,
                    breadcrumb=" >> ".join(page_state.breadcrumb),
                    path_taken=path_taken,
                    tokens_used=total_tokens
                )
            
            elif tool == "done":
                # AI has the answer
                answer = action.get("args", {}).get("answer", "")
                log.info(f"[TOKENS] Total: {total_tokens['total_tokens']} (prompt: {total_tokens['prompt_tokens']}, completion: {total_tokens['completion_tokens']})")
                return NavigationResult(
                    success=True,
                    content=answer,
                    url=current_url,
                    breadcrumb=" >> ".join(page_state.breadcrumb),
                    path_taken=path_taken,
                    tokens_used=total_tokens
                )
            
            elif tool == "go_back":
                # Go back to previous page
                path_taken.append("(back)")
                if history:
                    current_url = history.pop()
                    log.info(f"  -> Going back to {current_url}")
                else:
                    log.warning("  -> No history to go back to")
                continue
            
            elif tool == "click":
                link_text_raw = action.get("args", {}).get("link_text", "")
                path_taken.append(link_text_raw)
                
                # AI might include path info like "Engine Oil (path: Capacity Specifications/Engine Oil)"
                # Parse out the text and optional path hint
                clean_text = link_text_raw.split("(path:")[0].strip()
                path_hint = ""
                if "(path:" in link_text_raw:
                    path_hint = link_text_raw.split("(path:")[1].rstrip(")").strip().lower()
                
                # Find matching link, preferring path match
                matching_link = None
                fallback_link = None
                
                for link in page_state.links:
                    text_matches = (link["text"].lower() == clean_text.lower() or 
                                   clean_text.lower() in link["text"].lower() or 
                                   link["text"].lower() in clean_text.lower())
                    
                    if not text_matches:
                        continue
                    
                    # If we have a path hint, check if the href contains it
                    if path_hint:
                        href_lower = unquote(link["href"]).lower()
                        if path_hint in href_lower or all(p in href_lower for p in path_hint.split("/")):
                            matching_link = link
                            break
                        else:
                            # Save as fallback in case no path matches
                            if not fallback_link:
                                fallback_link = link
                    else:
                        # No path hint, take first text match
                        matching_link = link
                        break
                
                # Use fallback if no path match found
                if not matching_link and fallback_link:
                    log.warning(f"  -> No path match for '{path_hint}', using fallback")
                    matching_link = fallback_link
                
                if matching_link:
                    history.append(current_url)  # Save for go_back
                    current_url = matching_link["href"]
                    log.info(f"  -> Clicking '{clean_text}' -> {current_url}")
                else:
                    log.warning(f"  -> Link '{link_text_raw}' not found, staying on page")
            else:
                log.warning(f"Unknown tool: {tool}")
        
        log.info(f"[TOKENS] Total: {total_tokens['total_tokens']} (prompt: {total_tokens['prompt_tokens']}, completion: {total_tokens['completion_tokens']})")
        return NavigationResult(
            success=False,
            error="Max steps reached without finding answer",
            path_taken=path_taken,
            tokens_used=total_tokens
        )
    
    def _build_vehicle_url(self, vehicle: dict) -> str:
        """Build a starting URL for the vehicle - goes directly to Repair and Diagnosis."""
        make = vehicle.get("make", "")
        year = vehicle.get("year", "")
        model = vehicle.get("model", "")
        
        # Handle make variations
        make_path = make
        if make.lower() == "jeep":
            make_path = "Jeep Truck"
        elif make.lower() == "chevy":
            # Could be car or truck - start with Chevrolet
            make_path = "Chevrolet"
        elif make.lower() == "dodge" and "truck" in model.lower():
            make_path = "Dodge or Ram Truck"
        
        # URL encode
        make_encoded = quote(make_path)
        
        if year and model:
            model_encoded = quote(model)
            # Start at Repair and Diagnosis page - that's where all the technical info is
            return f"{self.base_url}/{make_encoded}/{year}/{model_encoded}/Repair%20and%20Diagnosis/"
        elif year:
            return f"{self.base_url}/{make_encoded}/{year}/"
        elif make:
            return f"{self.base_url}/{make_encoded}/"
        else:
            return self.base_url
    
    def _extract_content(self, html: str, goal: str) -> str:
        """Extract relevant content from page based on goal."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Get all text content from main area
        main = soup.select_one(".main")
        if not main:
            main = soup.body
        
        parts = []
        
        # Get title
        h1 = main.find("h1")
        if h1:
            parts.append(f"# {h1.get_text(strip=True)}")
        
        # Get tables (specs, capacities)
        for table in main.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                parts.append("\n".join(rows))
        
        # Get paragraphs
        for p in main.find_all("p"):
            text = p.get_text(strip=True)
            if text and len(text) > 20:
                parts.append(text)
        
        # Get lists
        for ul in main.find_all(["ul", "ol"]):
            items = []
            for li in ul.find_all("li", recursive=False):
                text = li.get_text(strip=True)
                if text:
                    items.append(f"• {text}")
            if items:
                parts.append("\n".join(items))
        
        # FALLBACK: If no tables/paragraphs/lists found, get all text from main
        # This handles pages that use <br> tags instead of proper HTML structure
        if len(parts) <= 1:  # Only title found
            # Remove script and style tags
            for tag in main.find_all(["script", "style"]):
                tag.decompose()
            
            # Get text, replacing <br> with newlines
            for br in main.find_all("br"):
                br.replace_with("\n")
            
            text = main.get_text(separator="\n", strip=True)
            # Clean up extra whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                parts = [f"# {lines[0]}"] + lines[1:]
        
        return "\n\n".join(parts)


async def query_autodb(goal: str, vehicle: dict, model: str = None) -> NavigationResult:
    """
    High-level function to query autodb.
    
    Args:
        goal: What to find
        vehicle: {year, make, model, engine}
        model: LLM model to use (default: gemini-2.5-flash)
    
    Returns:
        NavigationResult
    """
    navigator = AutodbNavigator(model=model)
    try:
        return await navigator.navigate(goal, vehicle)
    finally:
        await navigator.close()


# CLI for testing
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    async def test():
        vehicle = {
            "year": "2012",
            "make": "Jeep",
            "model": "Liberty 4WD V6-3.7L"
        }
        goal = "oil capacity"
        
        if len(sys.argv) > 1:
            goal = " ".join(sys.argv[1:])
        
        result = await query_autodb(goal, vehicle)
        print(f"\n{'='*60}")
        print(f"Success: {result.success}")
        print(f"URL: {result.url}")
        print(f"Breadcrumb: {result.breadcrumb}")
        print(f"Path: {' -> '.join(result.path_taken)}")
        print(f"\nContent:\n{result.content[:2000]}")
    
    asyncio.run(test())
