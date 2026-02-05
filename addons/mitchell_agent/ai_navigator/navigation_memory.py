"""
Navigation Memory - Learning with Golden Thread Tracking
========================================================

When the AI finds what it's looking for, it traces back through
its exploration history to extract the "golden thread" - the clean,
replayable path from start to success.

Each step captures:
- What was clicked (selector)
- What it said (element text)
- Where we were (context)
- What happened (result)

This gives us:
1. Replayable paths for automation
2. Human-readable breadcrumbs for debugging
3. Rich context for prompting on future queries

JSON Structure:
{
  "learned_paths": {
    "horn fuse": {
      "steps": [
        {
          "action": "click",
          "selector": "#electricalAccess",
          "element_text": "Electrical",
          "context": "landing page",
          "result": "opened modal"
        },
        {
          "action": "click",
          "selector": "a:has-text('Fuses')",
          "element_text": "Fuses",
          "result": "showed fuse table"
        }
      ],
      "selectors": ["#electricalAccess", "a:has-text('Fuses')"],
      "human_readable": "Electrical → Fuses → Horn row",
      "successes": 3,
      "last_success": "2026-01-10"
    }
  },
  "failed_paths": {
    "horn fuse": [
      ["#commonSpecsAccess"]
    ]
  }
}
"""

import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

log = logging.getLogger(__name__)

DEFAULT_MEMORY_PATH = Path(__file__).parent.parent / "navigation_memory.json"


@dataclass
class NavigationStep:
    """A single step in a navigation path."""
    action: str  # click, type, scroll
    selector: str
    element_text: str = ""
    context: str = ""  # Where we were (e.g., "landing page", "Fuses modal")
    result: str = ""  # What happened (e.g., "opened modal", "found data")
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NavigationStep":
        return cls(**data)


@dataclass
class LearnedPath:
    """A complete learned navigation path with rich metadata."""
    steps: List[NavigationStep]
    selectors: List[str]  # Just the selectors for quick replay
    human_readable: str  # "Electrical → Fuses → Horn"
    successes: int = 1
    first_learned: str = ""
    last_success: str = ""
    
    def __post_init__(self):
        now = datetime.now().strftime("%Y-%m-%d")
        if not self.first_learned:
            self.first_learned = now
        if not self.last_success:
            self.last_success = now
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "selectors": self.selectors,
            "human_readable": self.human_readable,
            "successes": self.successes,
            "first_learned": self.first_learned,
            "last_success": self.last_success,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearnedPath":
        steps = [NavigationStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            steps=steps,
            selectors=data.get("selectors", []),
            human_readable=data.get("human_readable", ""),
            successes=data.get("successes", 1),
            first_learned=data.get("first_learned", ""),
            last_success=data.get("last_success", ""),
        )


class NavigationMemory:
    """
    Persistent memory of successful navigation paths with golden thread tracking.
    
    When the AI finds data, it traces back to create a clean, replayable path.
    Next time a similar query comes in, it can replay the exact steps.
    """
    
    def __init__(self, memory_path: Optional[Path] = None):
        self.memory_path = memory_path or DEFAULT_MEMORY_PATH
        self.learned_paths: Dict[str, LearnedPath] = {}
        self.failed_paths: Dict[str, List[List[str]]] = {}
        self._load()
    
    def _load(self) -> None:
        """Load memory from JSON file."""
        if self.memory_path.exists():
            try:
                with open(self.memory_path, 'r') as f:
                    data = json.load(f)
                
                # Load learned paths
                for query, path_data in data.get("learned_paths", {}).items():
                    self.learned_paths[query] = LearnedPath.from_dict(path_data)
                
                self.failed_paths = data.get("failed_paths", {})
                log.info(f"Loaded navigation memory: {len(self.learned_paths)} learned paths")
            except Exception as e:
                log.warning(f"Failed to load navigation memory: {e}")
                self.learned_paths = {}
                self.failed_paths = {}
        else:
            log.info("No existing navigation memory, starting fresh")
    
    def _save(self) -> None:
        """Save memory to JSON file."""
        try:
            data = {
                "learned_paths": {
                    q: p.to_dict() for q, p in self.learned_paths.items()
                },
                "failed_paths": self.failed_paths,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.memory_path, 'w') as f:
                json.dump(data, f, indent=2)
            log.debug("Navigation memory saved")
        except Exception as e:
            log.error(f"Failed to save navigation memory: {e}")
    
    def record_success(
        self,
        query: str,
        steps: List[NavigationStep],
        data_found: str = ""
    ) -> None:
        """
        Record a successful navigation with full golden thread.
        
        Args:
            query: The search query (e.g., "horn fuse")
            steps: List of NavigationStep objects tracing the path
            data_found: The data that was found (for context)
        """
        query_key = query.lower().strip()
        
        # Extract just selectors for quick replay
        selectors = [s.selector for s in steps]
        
        # Build human-readable path
        readable_parts = []
        for step in steps:
            if step.element_text:
                readable_parts.append(step.element_text)
            else:
                # Extract meaningful part from selector
                sel = step.selector
                if ":has-text(" in sel:
                    # Extract text from has-text
                    start = sel.find(":has-text(") + 11
                    end = sel.find(")", start) - 1
                    readable_parts.append(sel[start:end])
                elif "#" in sel:
                    # Use ID name
                    readable_parts.append(sel.replace("#", "").replace("Access", ""))
                else:
                    readable_parts.append(sel[:30])
        
        human_readable = " → ".join(readable_parts)
        if data_found:
            human_readable += f" → FOUND: {data_found[:50]}"
        
        if query_key in self.learned_paths:
            # Update existing
            existing = self.learned_paths[query_key]
            existing.successes += 1
            existing.last_success = datetime.now().strftime("%Y-%m-%d")
            
            # Update path if shorter
            if len(steps) < len(existing.steps):
                log.info(f"Found shorter path for '{query_key}'")
                existing.steps = steps
                existing.selectors = selectors
                existing.human_readable = human_readable
        else:
            # New discovery
            self.learned_paths[query_key] = LearnedPath(
                steps=steps,
                selectors=selectors,
                human_readable=human_readable,
            )
            log.info(f"🧠 Learned new path: '{query_key}' → {human_readable}")
        
        # Remove from failed if present
        if query_key in self.failed_paths:
            self.failed_paths[query_key] = [
                p for p in self.failed_paths[query_key] if p != selectors
            ]
        
        self._save()
    
    def record_failure(self, query: str, selectors: List[str]) -> None:
        """Record a failed navigation path."""
        query_key = query.lower().strip()
        
        if query_key not in self.failed_paths:
            self.failed_paths[query_key] = []
        
        if selectors not in self.failed_paths[query_key]:
            self.failed_paths[query_key].append(selectors)
            log.info(f"📝 Recorded failed path: '{query_key}' ✗ {selectors}")
            self._save()
    
    def get_known_path(self, query: str) -> Optional[LearnedPath]:
        """Get a known successful path for a query."""
        query_key = query.lower().strip()
        
        # Exact match
        if query_key in self.learned_paths:
            return self.learned_paths[query_key]
        
        # Partial match - query contains known term
        for known_query, path in self.learned_paths.items():
            if known_query in query_key or query_key in known_query:
                return path
        
        return None
    
    def get_selectors(self, query: str) -> Optional[List[str]]:
        """Get just the selectors for quick replay."""
        path = self.get_known_path(query)
        return path.selectors if path else None
    
    def get_failed_paths(self, query: str) -> List[List[str]]:
        """Get paths that failed for this query."""
        query_key = query.lower().strip()
        return self.failed_paths.get(query_key, [])
    
    def get_hints_for_prompt(self, query: str) -> str:
        """Get formatted hints for the AI prompt."""
        hints = []
        query_key = query.lower().strip()
        
        # Known path with full context
        known = self.get_known_path(query)
        if known:
            hints.append(f"✓ KNOWN PATH ({known.successes} successes):")
            hints.append(f"   Route: {known.human_readable}")
            hints.append(f"   Steps:")
            for i, step in enumerate(known.steps, 1):
                hints.append(f"     {i}. {step.action} → {step.selector}")
                if step.element_text:
                    hints.append(f"        Text: '{step.element_text}'")
                if step.result:
                    hints.append(f"        Result: {step.result}")
        
        # Related paths
        for kq, path in self.learned_paths.items():
            if kq != query_key:
                query_words = set(query_key.split())
                known_words = set(kq.split())
                if query_words & known_words:
                    hints.append(f"Related: '{kq}' → {path.human_readable}")
        
        # Failed paths to avoid
        failed = self.get_failed_paths(query)
        if failed:
            failed_strs = [" → ".join(p) for p in failed[:3]]
            hints.append(f"✗ AVOID: {', '.join(failed_strs)}")
        
        if hints:
            return "\n## Navigation Memory\n" + "\n".join(hints) + "\n"
        return ""
    
    def is_path_failed(self, query: str, selectors: List[str]) -> bool:
        """Check if a path has previously failed."""
        failed = self.get_failed_paths(query)
        return selectors in failed
    
    def get_stats(self) -> Dict:
        """Get memory statistics."""
        return {
            "total_learned_paths": len(self.learned_paths),
            "total_failed_paths": sum(len(v) for v in self.failed_paths.values()),
            "total_successes": sum(p.successes for p in self.learned_paths.values()),
            "queries": list(self.learned_paths.keys()),
            "paths": {q: p.human_readable for q, p in self.learned_paths.items()}
        }
    
    def export_markdown(self, output_path: Optional[Path] = None) -> str:
        """Export all learned paths as human-readable markdown."""
        lines = ["# Learned Navigation Paths\n"]
        lines.append(f"Last updated: {datetime.now().isoformat()}\n")
        
        for query, path in sorted(self.learned_paths.items()):
            lines.append(f"## {query.title()}\n")
            lines.append(f"**Route:** {path.human_readable}\n")
            lines.append(f"**Successes:** {path.successes}\n")
            lines.append("**Steps:**\n")
            for i, step in enumerate(path.steps, 1):
                lines.append(f"{i}. **{step.action}** → `{step.selector}`")
                if step.element_text:
                    lines.append(f"   - Text: {step.element_text}")
                if step.context:
                    lines.append(f"   - Context: {step.context}")
                if step.result:
                    lines.append(f"   - Result: {step.result}")
            lines.append("")
        
        content = "\n".join(lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)
        
        return content


# Global instance
_memory: Optional[NavigationMemory] = None


def get_memory() -> NavigationMemory:
    """Get the global navigation memory instance."""
    global _memory
    if _memory is None:
        _memory = NavigationMemory()
    return _memory


def record_success(query: str, steps: List[NavigationStep], data_found: str = "") -> None:
    """Convenience function to record a successful navigation."""
    get_memory().record_success(query, steps, data_found)


def record_failure(query: str, selectors: List[str]) -> None:
    """Convenience function to record a failed navigation."""
    get_memory().record_failure(query, selectors)


def get_hints_for_prompt(query: str) -> str:
    """Convenience function to get hints for a query."""
    return get_memory().get_hints_for_prompt(query)


def get_known_path(query: str) -> Optional[LearnedPath]:
    """Convenience function to get known path."""
    return get_memory().get_known_path(query)


def get_selectors(query: str) -> Optional[List[str]]:
    """Convenience function to get just selectors for replay."""
    return get_memory().get_selectors(query)
