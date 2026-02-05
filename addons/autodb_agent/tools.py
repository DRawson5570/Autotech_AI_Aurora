"""
AutoDB Agent Tools.

Tool implementations for navigation.
Enhanced with collect/done for multi-step data gathering,
and where_am_i/how_did_i_get_here for navigation awareness.
Now with egrep/goto for indexed search - clear vision!
"""

import logging
import os
import re
from typing import Optional, List
from pathlib import Path
from difflib import SequenceMatcher

from .models import PageState, ToolResult, Vehicle
from .page_parser import PageParser
from .site_index import egrep_index, SiteIndexer, INDEX_DIR

log = logging.getLogger("autodb_agent.tools")


class Tools:
    """Tool implementations for the navigator."""
    
    def __init__(self, parser: PageParser, vehicle: Vehicle = None, base_url: str = None):
        self.parser = parser
        self.vehicle = vehicle
        self.base_url = base_url or "http://automotive.aurora-sentient.net/autodb"
        self.history: List[PageState] = []
        self.collected_data: List[dict] = []  # For multi-step collection
        self._index_path: Optional[Path] = None
        self._unified_index: bool = False  # Flag for unified vs per-vehicle index
    
    def set_vehicle(self, vehicle: Vehicle):
        """Set current vehicle (for indexed search)."""
        self.vehicle = vehicle
        self._index_path = None  # Reset cached path
    
    def _get_index_path(self) -> Optional[Path]:
        """Get index path for current vehicle.
        
        Checks for:
        1. Unified full-site index (/tmp/autodb_full_index.tsv)
        2. Per-vehicle index (/tmp/autodb_indexes/{vehicle}.idx)
        """
        if self._index_path:
            return self._index_path
        
        # First check for unified full-site index
        unified_index = Path("/tmp/autodb_full_index.tsv")
        if unified_index.exists():
            log.info(f"Using unified index: {unified_index}")
            self._index_path = unified_index
            self._unified_index = True
            return unified_index
        
        # Fall back to per-vehicle index
        if not self.vehicle:
            return None
        
        # Try with engine, then without
        patterns_to_try = []
        if self.vehicle.engine:
            vehicle_key = f"{self.vehicle.year}_{self.vehicle.make}_{self.vehicle.model}_{self.vehicle.engine}"
            patterns_to_try.append(vehicle_key)
        # Also try without engine
        vehicle_key_no_engine = f"{self.vehicle.year}_{self.vehicle.make}_{self.vehicle.model}"
        patterns_to_try.append(vehicle_key_no_engine)
        
        for vehicle_key in patterns_to_try:
            safe_key = re.sub(r'[^\w\-]', '_', vehicle_key)
            path = INDEX_DIR / f"{safe_key}.idx"
            log.debug(f"Looking for index: {path}")
            if path.exists():
                log.info(f"Found per-vehicle index: {path}")
                self._index_path = path
                self._unified_index = False
                return path
        
        log.warning(f"No index found for {self.vehicle}")
        return None
    
    def push_history(self, state: PageState):
        """Add state to history for go_back."""
        self.history.append(state)
    
    def where_am_i(self, current_state: PageState, path_taken: list) -> ToolResult:
        """Tell the AI where it is - current location and depth."""
        log.info("WHERE_AM_I")
        
        click_count = len([p for p in path_taken if "CLICK" in p.action])
        location = current_state.title or "Unknown Page"
        breadcrumb = " > ".join(current_state.breadcrumb) if current_state.breadcrumb else "Home"
        
        has_images = len(current_state.images) > 0
        has_data = current_state.has_data
        
        return ToolResult(
            success=True,
            hint=f"→ at: {location}",
            extracted_content=f"""Current Location: {location}
Breadcrumb: {breadcrumb}
Depth: {click_count} click(s) from home
Has Data: {has_data}
Has Images: {has_images} ({len(current_state.images)} images)
Links Available: {len(current_state.links)}

Use go_back() to try a different path if this isn't what you need.""",
        )
    
    def how_did_i_get_here(self, path_taken: list) -> ToolResult:
        """Show the full navigation path taken."""
        log.info("HOW_DID_I_GET_HERE")
        
        if not path_taken:
            return ToolResult(
                success=True,
                hint="→ just started",
                extracted_content="You just started. You're at the home page.",
            )
        
        path_lines = []
        for i, step in enumerate(path_taken, 1):
            path_lines.append(f"{i}. {step.action} {step.result_hint}")
        
        path_text = "\n".join(path_lines)
        
        return ToolResult(
            success=True,
            hint=f"→ {len(path_taken)} steps taken",
            extracted_content=f"Your path:\nHOME\n{path_text}",
        )
    
    def collect(self, data: str, label: str = None) -> ToolResult:
        """
        Collect data and continue navigating.
        
        Use this when you need to gather data from multiple pages/sections
        before combining them. Call done() when finished collecting.
        """
        log.info(f"COLLECT: {label or 'unlabeled'}")
        
        if not data:
            return ToolResult(
                success=False,
                hint="→ no data provided",
                error="No data provided to collect",
            )
        
        label = label or f"Item {len(self.collected_data) + 1}"
        self.collected_data.append({"label": label, "data": data})
        
        return ToolResult(
            success=True,
            hint=f"→ collected '{label}' ({len(data)} chars). {len(self.collected_data)} item(s) stored.",
        )
    
    def done(self, summary: str = None) -> ToolResult:
        """
        Finish collection and combine all gathered data.
        
        Use after collect() calls to return all data together.
        """
        log.info(f"DONE: {len(self.collected_data)} items")
        
        if not self.collected_data:
            return ToolResult(
                success=False,
                hint="→ nothing collected",
                error="No data collected. Use collect() first or extract() for single-page data.",
            )
        
        # Combine all collected data
        parts = []
        for item in self.collected_data:
            label = item.get("label", "")
            data = item.get("data", "")
            if label:
                parts.append(f"=== {label} ===\n{data}")
            else:
                parts.append(data)
        
        combined = "\n\n".join(parts)
        
        # Clear collected data for next query
        self.collected_data = []
        
        return ToolResult(
            success=True,
            hint=f"→ combined {len(parts)} items",
            extracted_content=combined,
        )
    
    async def click(self, link_text: str, current_state: PageState) -> ToolResult:
        """
        Click a link by text.
        
        Uses fuzzy matching to find the best link match.
        """
        log.info(f"CLICK: '{link_text}'")
        
        # Find matching link
        link = self._find_link(link_text, current_state.links)
        
        if not link:
            return ToolResult(
                success=False,
                hint=f"→ link '{link_text}' not found",
                error=f"Link not found: {link_text}",
            )
        
        href = link.get("href")
        if not href:
            return ToolResult(
                success=False,
                hint=f"→ '{link['text']}' has no URL - cannot navigate",
                error=f"Link has no href: {link['text']}",
            )
        
        # Save current state to history
        self.push_history(current_state)
        
        # Fetch new page
        try:
            new_state = await self.parser.fetch_and_parse(href)
            
            # Determine result hint
            if new_state.has_data:
                hint = f"→ found data page: {new_state.title}"
            else:
                link_count = len(new_state.links)
                hint = f"→ {new_state.title} ({link_count} links)"
            
            return ToolResult(
                success=True,
                hint=hint,
                new_state=new_state,
            )
        except Exception as e:
            log.error(f"Click failed: {e}")
            return ToolResult(
                success=False,
                hint=f"→ error: {str(e)[:50]}",
                error=str(e),
            )
    
    async def extract(self, current_state: PageState) -> ToolResult:
        """
        Extract content from current page.
        
        Returns the page content and tables as extracted data.
        """
        log.info(f"EXTRACT: {current_state.url}")
        
        # Combine content and tables
        parts = []
        
        if current_state.content_text:
            parts.append(current_state.content_text)
        
        if current_state.tables:
            parts.append("\n--- TABLES ---")
            for table in current_state.tables:
                parts.append(table)
        
        if not parts:
            return ToolResult(
                success=False,
                hint="→ no content to extract",
                error="Page has no extractable content",
            )
        
        content = "\n\n".join(parts)
        
        return ToolResult(
            success=True,
            hint=f"→ extracted {len(content)} chars",
            extracted_content=content,
        )
    
    async def go_back(self) -> ToolResult:
        """Go back to previous page."""
        log.info("GO_BACK")
        
        if not self.history:
            return ToolResult(
                success=False,
                hint="→ no history to go back to",
                error="No previous page in history",
            )
        
        previous_state = self.history.pop()
        
        return ToolResult(
            success=True,
            hint=f"→ back to: {previous_state.title}",
            new_state=previous_state,
        )
    
    def grep(self, pattern: str, current_state: PageState, context_lines: int = 2) -> ToolResult:
        """
        Search current page content for a pattern.
        
        Returns matching lines with context, like grep -i -C 2.
        Case-insensitive search.
        """
        log.info(f"GREP: '{pattern}'")
        
        if not pattern:
            return ToolResult(
                success=False,
                hint="→ no pattern provided",
                error="No search pattern provided",
            )
        
        # Get full page content
        content = current_state.content_text or ""
        if current_state.tables:
            content += "\n" + "\n".join(current_state.tables)
        
        if not content:
            return ToolResult(
                success=False,
                hint="→ no content to search",
                error="Page has no searchable content",
            )
        
        # Split into lines and search
        lines = content.split('\n')
        matches = []
        pattern_re = re.compile(re.escape(pattern), re.IGNORECASE)
        
        for i, line in enumerate(lines):
            if pattern_re.search(line):
                # Get context lines
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                
                context_block = []
                for j in range(start, end):
                    prefix = ">>>" if j == i else "   "
                    context_block.append(f"{prefix} {lines[j]}")
                
                matches.append(f"[Line {i+1}]\n" + "\n".join(context_block))
        
        if not matches:
            return ToolResult(
                success=True,
                hint=f"→ no matches for '{pattern}'",
                extracted_content=f"No matches found for '{pattern}' on this page.",
            )
        
        result = f"Found {len(matches)} match(es) for '{pattern}':\n\n" + "\n\n---\n\n".join(matches)
        
        return ToolResult(
            success=True,
            hint=f"→ found {len(matches)} match(es) for '{pattern}'",
            extracted_content=result,
        )
    
    def cat(self, current_state: PageState, max_chars: int = 8000) -> ToolResult:
        """
        Show full page content (like cat).
        
        Returns raw content without truncation (up to max_chars).
        Use when the summary view isn't showing enough.
        """
        log.info("CAT")
        
        parts = []
        
        # Title and breadcrumb
        if current_state.title:
            parts.append(f"=== {current_state.title} ===")
        if current_state.breadcrumb:
            parts.append(f"Path: {' > '.join(current_state.breadcrumb)}")
        
        # Full content
        if current_state.content_text:
            parts.append("\n--- CONTENT ---")
            parts.append(current_state.content_text)
        
        # Tables
        if current_state.tables:
            parts.append("\n--- TABLES ---")
            for table in current_state.tables:
                parts.append(table)
        
        # Links
        if current_state.links:
            parts.append(f"\n--- LINKS ({len(current_state.links)}) ---")
            for link in current_state.links[:50]:  # Cap at 50
                parts.append(f"  - {link['text']}")
            if len(current_state.links) > 50:
                parts.append(f"  ... and {len(current_state.links) - 50} more links")
        
        # Images
        if current_state.images:
            parts.append(f"\n--- IMAGES ({len(current_state.images)}) ---")
            for img in current_state.images:
                parts.append(f"  - {img}")
        
        if not parts:
            return ToolResult(
                success=False,
                hint="→ page is empty",
                error="Page has no content",
            )
        
        content = "\n".join(parts)
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
        
        return ToolResult(
            success=True,
            hint=f"→ full page ({len(content)} chars)",
            extracted_content=content,
        )
    
    def _find_link(self, text: str, links: List[dict]) -> Optional[dict]:
        """Find link by text with fuzzy matching. Returns the link dict or None.
        
        The AI may include path context in brackets like "Engine Oil [Specifications/Capacity]"
        so we need to match against both the text and the text+path combination.
        """
        text_lower = text.lower().strip()
        
        # Helper to get the full display text (text + path if present)
        def get_display_text(link):
            t = link["text"]
            p = link.get("path", "")
            if p:
                return f"{t} [{p}]".lower()
            return t.lower()
        
        # First try exact match on display text (includes path context)
        for link in links:
            if get_display_text(link) == text_lower:
                return link
        
        # Try exact match on just the text
        for link in links:
            if link["text"].lower().strip() == text_lower:
                return link
        
        # Try contains match on display text
        for link in links:
            if text_lower in get_display_text(link):
                return link
        
        # Fuzzy match - find best match above threshold
        best_match = None
        best_score = 0.6  # Minimum threshold
        
        for link in links:
            # Match against both text only and text+path
            display = get_display_text(link)
            score = max(
                SequenceMatcher(None, text_lower, link["text"].lower()).ratio(),
                SequenceMatcher(None, text_lower, display).ratio()
            )
            if score > best_score:
                best_score = score
                best_match = link
        
        if best_match:
            log.debug(f"Fuzzy matched '{text}' with score {best_score:.2f}")
        
        return best_match

    def egrep(self, pattern: str, max_results: int = 20) -> ToolResult:
        """
        Search the entire site index for a regex pattern.
        
        This searches across ALL pages for this vehicle, returning matching
        paths and content snippets. Use this FIRST to find where data is located
        before navigating.
        
        Args:
            pattern: Regex pattern to search for (case-insensitive)
            max_results: Maximum number of results to return
            
        Returns:
            ToolResult with matching paths and content snippets
        """
        log.info(f"EGREP: pattern='{pattern}'")
        
        # Try to find the index file
        index_path = self._get_index_path()
        
        if not index_path:
            return ToolResult(
                success=False,
                hint="→ no index available",
                error="Site index not available. Use click navigation instead.",
            )
        
        if not os.path.exists(index_path):
            return ToolResult(
                success=False,
                hint="→ index not built yet",
                error=f"Index file not found at {index_path}. It may still be building.",
            )
        
        # For unified index, build vehicle-specific pattern
        search_pattern = pattern
        vehicle_prefix = None
        
        if self._unified_index and self.vehicle:
            # Unified index paths vary but typically include make, year, and model/engine
            # Format examples:
            #   Jeep Truck/1985/L4-150 2.5L VIN U 1-bbl/Repair/...
            #   Toyota/Camry/2020/L4-2.5L/Specifications/...
            # We'll match on make and year which should be present
            make = self.vehicle.make
            year = self.vehicle.year
            
            # Build filter: line must contain make AND year
            # Use \b for word boundaries to avoid partial matches
            make_pattern = re.escape(make).replace('\\ ', '[ _]')  # Allow space or underscore
            vehicle_prefix = f"{make}.*{year}"  # For display
            # Combine: line must match vehicle filter AND user pattern
            search_pattern = f"(?=.*{make_pattern})(?=.*\\b{year}\\b)(?=.*{pattern})"
            log.info(f"Unified index search: make='{make}', year='{year}', combined_pattern='{search_pattern}'")
        
        try:
            matches = egrep_index(index_path, search_pattern)
        except Exception as e:
            log.error(f"egrep_index error: {e}")
            return ToolResult(
                success=False,
                hint="→ search error",
                error=f"Error searching index: {e}",
            )
        
        if not matches:
            return ToolResult(
                success=True,
                hint=f"→ no matches for '{pattern}'",
                extracted_content=f"No pages found matching '{pattern}'. Try a different search term.",
            )
        
        # Check for error response
        if matches and isinstance(matches[0], dict) and 'error' in matches[0]:
            return ToolResult(
                success=False,
                hint="→ invalid pattern",
                error=matches[0]['error'],
            )
        
        # Format results - egrep_index returns list of dicts with path/title/match
        results = []
        for item in matches[:max_results]:
            path = item.get('path', '')
            title = item.get('title', '')
            snippet = item.get('match', '')[:200]
            
            # For unified index, strip vehicle prefix from display path
            display_path = path
            if vehicle_prefix and path.startswith(vehicle_prefix):
                display_path = path[len(vehicle_prefix):].lstrip('/')
            
            results.append(f"PATH: {display_path}\nTITLE: {title}\nSNIPPET: {snippet}...")
        
        summary = f"Found {len(matches)} page(s) matching '{pattern}'"
        if len(matches) > max_results:
            summary += f" (showing first {max_results})"
        summary += ":\n\n" + "\n\n---\n\n".join(results)
        
        return ToolResult(
            success=True,
            hint=f"→ {len(matches)} pages match '{pattern}'",
            extracted_content=summary,
        )

    def goto(self, path: str) -> ToolResult:
        """
        Navigate directly to a specific path in the documentation.
        
        Use after egrep to jump directly to a known location.
        The path should be the relative path from the vehicle root.
        
        Args:
            path: Path like "Specifications/Capacity and Type/Engine Oil"
            
        Returns:
            ToolResult indicating whether goto is ready (the navigator will
            handle the actual navigation)
        """
        log.info(f"GOTO: path='{path}'")
        
        if not path:
            return ToolResult(
                success=False,
                hint="→ no path specified",
                error="Must specify a path to navigate to.",
            )
        
        # Clean up path
        path = path.strip().strip('/')
        
        # Return a special result that the navigator will interpret
        return ToolResult(
            success=True,
            hint=f"→ navigating to: {path}",
            extracted_content=f"GOTO:{path}",  # Navigator interprets this
        )
