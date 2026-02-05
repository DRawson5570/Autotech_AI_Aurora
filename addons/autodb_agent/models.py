"""
AutoDB Agent Data Models.

Pydantic/dataclass models for page state, navigation results, and tool outputs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PageState:
    """Current state of a page for the AI to see."""
    url: str
    title: str
    breadcrumb: List[str]
    links: List[Dict[str, str]]  # [{text, href, path_hint}]
    content_text: str            # Main content (truncated)
    tables: List[str]            # Extracted table data as text
    has_data: bool               # True if page has specs/values (not just links)
    images: List[str] = field(default_factory=list)  # Image URLs found on page
    
    def filter_links_for_goal(self, goal: str, max_links: int = 50, vehicle: 'Vehicle' = None) -> List[Dict[str, str]]:
        """Filter and prioritize links based on goal and vehicle.
        
        Returns the most relevant links for the given goal.
        Uses keyword matching to prioritize relevant links.
        When vehicle is provided, prioritizes vehicle-related links first.
        """
        from difflib import SequenceMatcher
        
        goal_lower = goal.lower()
        goal_words = set(goal_lower.split())
        
        # Add vehicle info to search terms (critical for make/year/model selection)
        vehicle_terms = set()
        if vehicle:
            vehicle_terms.add(vehicle.make.lower())
            vehicle_terms.add(str(vehicle.year).lower())
            vehicle_terms.add(vehicle.model.lower())
            # Handle "Jeep Truck" -> also add "Jeep"
            for word in vehicle.make.lower().split():
                vehicle_terms.add(word)
        
        # Score each link by relevance
        scored_links = []
        for link in self.links:
            text = link.get("text", "").lower()
            path = link.get("path", "").lower()
            combined = f"{text} {path}"
            
            # Calculate score
            score = 0
            
            # CRITICAL: Vehicle make/year/model matches get highest priority
            # This ensures "Jeep Truck" appears when looking for a Jeep vehicle
            for term in vehicle_terms:
                if term in text:
                    score += 200  # Very high priority for vehicle matches
            
            # Exact goal match in text or path
            if goal_lower in combined:
                score += 100
            
            # Word matches
            for word in goal_words:
                if len(word) > 2:  # Skip short words
                    if word in text:
                        score += 20
                    if word in path:
                        score += 10
            
            # Fuzzy similarity
            text_sim = SequenceMatcher(None, goal_lower, text).ratio()
            score += text_sim * 10
            
            # Boost for specs/capacity/torque paths
            spec_keywords = ["specification", "capacity", "torque", "fluid", "oil", "coolant"]
            for kw in spec_keywords:
                if kw in path:
                    score += 5
            
            scored_links.append((score, link))
        
        # Sort by score descending
        scored_links.sort(key=lambda x: x[0], reverse=True)
        
        # Return top links
        return [link for score, link in scored_links[:max_links]]
    
    def to_prompt_text(self, max_links: int = 50, max_content: int = 4000, goal: str = "", vehicle: 'Vehicle' = None) -> str:
        """Format page state for LLM prompt."""
        # Filter links based on goal/vehicle if provided and we have many links
        if (goal or vehicle) and len(self.links) > max_links:
            display_links = self.filter_links_for_goal(goal, max_links, vehicle)
        else:
            display_links = self.links[:max_links]
        
        # Format links with path context when available
        link_lines = []
        for link in display_links:
            text = link.get('text', '')
            path = link.get('path', '')
            if path:
                # Show path context for disambiguation
                # Truncate long paths, keeping START (most distinctive)
                if len(path) > 50:
                    path = path[:47] + "..."
                link_lines.append(f"  - {text} [{path}]")
            else:
                link_lines.append(f"  - {text}")
        
        if len(self.links) > max_links:
            link_lines.append(f"  ... and {len(self.links) - max_links} more links")
        
        links_text = "\n".join(link_lines) if link_lines else "  (no links)"
        
        # Format tables
        tables_text = ""
        if self.tables:
            tables_text = "\n\nTABLES:\n" + "\n---\n".join(self.tables[:3])
        
        # Format images
        images_text = ""
        if self.images:
            images_text = f"\n\nIMAGES: {len(self.images)} diagram(s) found on this page"
        
        return f"""URL: {self.url}
Title: {self.title}
Breadcrumb: {' > '.join(self.breadcrumb) if self.breadcrumb else '(none)'}
Has Data: {self.has_data}

AVAILABLE LINKS:
{links_text}

CONTENT:
{self.content_text[:max_content]}{tables_text}{images_text}"""


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    hint: str = ""              # Short description for path history
    new_state: Optional[PageState] = None
    extracted_content: str = ""
    error: str = ""


@dataclass
class PathStep:
    """A single step in the navigation path."""
    action: str                 # e.g., "CLICK 'Engine Oil'"
    result_hint: str            # e.g., "→ now showing capacity specs"


@dataclass 
class NavigationResult:
    """Final result from navigation."""
    success: bool
    content: str = ""
    url: str = ""
    breadcrumb: str = ""
    error: str = ""
    images: List[str] = field(default_factory=list)  # Image URLs from final page
    path_taken: List[PathStep] = field(default_factory=list)
    tokens_used: Dict[str, int] = field(default_factory=dict)
    steps_taken: int = 0
    timing: Dict[str, float] = field(default_factory=dict)  # Performance breakdown
    
    def format_path_taken(self) -> str:
        """Format path taken for display."""
        if not self.path_taken:
            return "(start)"
        
        lines = []
        for i, step in enumerate(self.path_taken, 1):
            lines.append(f"{i}. {step.action} {step.result_hint}")
        return "\n".join(lines)


@dataclass
class LLMResponse:
    """Response from LLM call."""
    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    
    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class Vehicle:
    """Vehicle information for queries."""
    year: str
    make: str
    model: str
    engine: str = ""
    
    def __str__(self) -> str:
        parts = [str(self.year), self.make, self.model]
        if self.engine:
            parts.append(self.engine)
        return " ".join(parts)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Vehicle":
        return cls(
            year=d.get("year", ""),
            make=d.get("make", ""),
            model=d.get("model", ""),
            engine=d.get("engine", ""),
        )
