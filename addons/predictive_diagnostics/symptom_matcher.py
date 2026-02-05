"""
Symptom Matcher - Fuzzy matching for customer-reported symptoms

Customers describe problems in natural language:
- "car runs rough"
- "engine gets hot"
- "hard to start in the morning"
- "check engine light came on"

This module matches these to our canonical symptom list using:
1. Keyword extraction and synonyms
2. Fuzzy string matching
3. Semantic similarity (when available)

Usage:
    matcher = SymptomMatcher()
    matched = matcher.match("car hesitates when accelerating")
    # Returns: ["hesitation", "poor acceleration"]
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Tuple
import re


@dataclass
class MatchResult:
    """Result of symptom matching."""
    original: str
    matched_symptoms: List[str]
    confidence: float
    matched_keywords: List[str]


# Canonical symptoms and their keyword patterns
SYMPTOM_PATTERNS = {
    # Idle issues
    "rough idle": {
        "keywords": ["rough", "idle", "shaking", "vibrating", "shakes", "vibrates", "uneven"],
        "phrases": ["runs rough", "idles rough", "shakes at idle", "vibrates at idle"],
        "negations": []
    },
    "high idle": {
        "keywords": ["high", "idle", "fast", "racing"],
        "phrases": ["idles high", "high idle", "fast idle", "racing idle", "won't idle down"],
        "negations": []
    },
    "low idle": {
        "keywords": ["low", "idle", "slow"],
        "phrases": ["idles low", "low idle", "slow idle"],
        "negations": []
    },
    "stalling": {
        "keywords": ["stall", "stalls", "stalling", "dies", "dying", "cuts", "shuts"],
        "phrases": ["engine stalls", "car dies", "cuts out", "shuts off randomly", 
                   "car stalls", "stalls when"],
        "negations": []
    },
    
    # Starting issues
    "hard start": {
        "keywords": ["hard", "start", "starting", "crank", "cranking", "difficult"],
        "phrases": ["hard to start", "won't start", "difficult to start", "takes long to start",
                   "cranks but won't start", "slow to start", "trouble starting"],
        "negations": []
    },
    "no start": {
        "keywords": ["start", "crank"],
        "phrases": ["won't start", "no start", "doesn't start", "won't crank", "dead"],
        "negations": []
    },
    "cold start problems": {
        "keywords": ["cold", "start", "morning", "winter"],
        "phrases": ["hard to start cold", "cold start", "morning start", "won't start cold"],
        "negations": []
    },
    
    # Power/acceleration issues
    "hesitation": {
        "keywords": ["hesitate", "hesitation", "hesitates", "stumble", "stumbles", "bog", "bogs"],
        "phrases": ["hesitates when accelerating", "stumbles on acceleration", "bogs down",
                   "lacks response", "slow to respond", "hesitates when", "engine hesitates"],
        "negations": []
    },
    "poor acceleration": {
        "keywords": ["slow", "sluggish", "weak", "power", "acceleration", "accelerate"],
        "phrases": ["slow acceleration", "lacks power", "no power", "weak acceleration",
                   "sluggish", "won't accelerate", "poor power"],
        "negations": []
    },
    "surging": {
        "keywords": ["surge", "surges", "surging", "hunts", "hunting"],
        "phrases": ["engine surges", "rpm surges", "surging idle", "hunting idle"],
        "negations": []
    },
    
    # Misfire related
    "misfire": {
        "keywords": ["misfire", "misfires", "misfiring", "miss", "missing"],
        "phrases": ["engine misfires", "misfiring", "engine misses", "has a miss"],
        "negations": []
    },
    "backfire": {
        "keywords": ["backfire", "backfires", "pop", "popping", "bang"],
        "phrases": ["backfires", "pops", "popping sound", "bangs"],
        "negations": []
    },
    
    # Temperature/cooling issues
    "overheating": {
        "keywords": ["overheat", "overheating", "hot", "temp", "temperature", "gauge"],
        "phrases": ["overheats", "runs hot", "temperature high", "gauge high",
                   "engine hot", "gets hot", "overheating"],
        "negations": []
    },
    "running cold": {
        "keywords": ["cold", "cool", "temp", "warm"],
        "phrases": ["runs cold", "won't warm up", "takes long to warm", "never gets warm",
                   "temperature low", "heater not working"],
        "negations": ["overheat"]
    },
    
    # Electrical issues
    "battery light": {
        "keywords": ["battery", "light", "charging", "alternator"],
        "phrases": ["battery light on", "charging light", "battery warning",
                   "alternator light"],
        "negations": []
    },
    "dim headlights": {
        "keywords": ["dim", "headlights", "lights", "electrical"],
        "phrases": ["dim lights", "headlights dim", "lights flickering", "weak lights"],
        "negations": []
    },
    "electrical problems": {
        "keywords": ["electrical", "electronics", "power windows", "radio"],
        "phrases": ["electrical issues", "electronics acting up", "power windows slow"],
        "negations": []
    },
    
    # Fuel economy
    "poor fuel economy": {
        "keywords": ["fuel", "gas", "mileage", "mpg", "economy", "consumption"],
        "phrases": ["bad gas mileage", "poor fuel economy", "uses too much gas",
                   "low mpg", "burning gas", "fuel consumption high"],
        "negations": []
    },
    
    # Exhaust/emissions
    "black smoke": {
        "keywords": ["black", "smoke", "exhaust"],
        "phrases": ["black smoke", "smoke from exhaust", "black exhaust"],
        "negations": []
    },
    "white smoke": {
        "keywords": ["white", "smoke", "steam", "exhaust"],
        "phrases": ["white smoke", "steam from exhaust", "white exhaust"],
        "negations": []
    },
    "blue smoke": {
        "keywords": ["blue", "smoke", "oil", "burning"],
        "phrases": ["blue smoke", "burning oil", "oil smoke"],
        "negations": []
    },
    "exhaust smell": {
        "keywords": ["smell", "exhaust", "fumes", "gas", "fuel", "rotten"],
        "phrases": ["exhaust smell", "gas smell", "fuel smell", "rotten egg smell",
                   "sulfur smell"],
        "negations": []
    },
    
    # Warning lights
    "check engine light": {
        "keywords": ["check", "engine", "light", "cel", "mil", "warning"],
        "phrases": ["check engine light", "engine light on", "CEL on", "MIL on",
                   "service engine soon", "warning light"],
        "negations": []
    },
    
    # Noise related
    "knocking": {
        "keywords": ["knock", "knocking", "ping", "pinging", "rattle"],
        "phrases": ["engine knocks", "knocking sound", "pinging", "rattling"],
        "negations": []
    },
    "ticking": {
        "keywords": ["tick", "ticking", "tap", "tapping", "lifter"],
        "phrases": ["ticking sound", "tapping noise", "lifter noise", "valve tick"],
        "negations": []
    },
    
    # Fan/cooling specific
    "fan not running": {
        "keywords": ["fan", "cooling", "radiator"],
        "phrases": ["fan not running", "fan doesn't turn on", "no fan", "cooling fan"],
        "negations": []
    },
}


class SymptomMatcher:
    """
    Matches customer-reported symptoms to canonical symptom names.
    """
    
    def __init__(self):
        self.patterns = SYMPTOM_PATTERNS
        # Build reverse index for fast keyword lookup
        self.keyword_to_symptoms: Dict[str, Set[str]] = {}
        for symptom, pattern in self.patterns.items():
            for keyword in pattern["keywords"]:
                if keyword not in self.keyword_to_symptoms:
                    self.keyword_to_symptoms[keyword] = set()
                self.keyword_to_symptoms[keyword].add(symptom)
    
    def match(self, description: str, threshold: float = 0.3) -> List[MatchResult]:
        """
        Match a customer description to canonical symptoms.
        
        Args:
            description: Customer's description of the problem
            threshold: Minimum confidence to include a match
            
        Returns:
            List of MatchResult sorted by confidence
        """
        description_lower = description.lower()
        results = []
        
        for symptom, pattern in self.patterns.items():
            confidence, matched_keywords = self._score_match(
                description_lower, pattern
            )
            
            if confidence >= threshold:
                results.append(MatchResult(
                    original=description,
                    matched_symptoms=[symptom],
                    confidence=confidence,
                    matched_keywords=matched_keywords
                ))
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results
    
    def match_multiple(
        self, 
        descriptions: List[str], 
        threshold: float = 0.3
    ) -> List[str]:
        """
        Match multiple descriptions and return unique canonical symptoms.
        
        Args:
            descriptions: List of customer descriptions
            threshold: Minimum confidence
            
        Returns:
            List of unique matched canonical symptoms
        """
        all_symptoms = set()
        
        for desc in descriptions:
            matches = self.match(desc, threshold)
            for match in matches:
                all_symptoms.update(match.matched_symptoms)
        
        return list(all_symptoms)
    
    def normalize_symptoms(self, symptoms: List[str]) -> List[str]:
        """
        Normalize a list of symptoms, matching informal to canonical names.
        
        If a symptom is already canonical, keep it.
        If it's informal, match it.
        """
        normalized = set()
        
        for symptom in symptoms:
            symptom_lower = symptom.lower()
            
            # Check if it's already a canonical symptom
            if symptom_lower in self.patterns:
                normalized.add(symptom_lower)
                continue
            
            # Try to match it
            matches = self.match(symptom)
            if matches:
                # Take the best match
                normalized.add(matches[0].matched_symptoms[0])
            else:
                # Keep original if no match found
                normalized.add(symptom_lower)
        
        return list(normalized)
    
    def _score_match(
        self, 
        description: str, 
        pattern: Dict
    ) -> Tuple[float, List[str]]:
        """
        Score how well a description matches a symptom pattern.
        
        Returns (confidence, matched_keywords)
        """
        score = 0.0
        matched_keywords = []
        
        # Check for negations first
        for negation in pattern.get("negations", []):
            if negation in description:
                return 0.0, []
        
        # Check exact phrase matches (highest weight)
        for phrase in pattern.get("phrases", []):
            if phrase in description:
                score += 0.6
                matched_keywords.append(f"phrase:{phrase}")
                break  # One phrase match is enough
        
        # Check keyword matches
        keywords_found = 0
        for keyword in pattern.get("keywords", []):
            # Use word boundary matching
            if re.search(rf'\b{re.escape(keyword)}\b', description):
                keywords_found += 1
                matched_keywords.append(keyword)
        
        if keywords_found > 0:
            # More keywords = higher confidence, but with diminishing returns
            keyword_score = min(0.5, 0.2 * keywords_found)
            score += keyword_score
        
        # Cap at 1.0
        confidence = min(1.0, score)
        
        return confidence, matched_keywords
    
    def explain_match(self, description: str) -> str:
        """
        Explain how a description was matched (for debugging).
        """
        matches = self.match(description, threshold=0.1)
        
        lines = [f"Input: '{description}'", ""]
        
        if not matches:
            lines.append("No matches found.")
        else:
            lines.append("Matches:")
            for m in matches[:5]:
                lines.append(f"  - {m.matched_symptoms[0]}: {m.confidence:.0%}")
                lines.append(f"    Matched: {', '.join(m.matched_keywords)}")
        
        return "\n".join(lines)


def test_symptom_matcher():
    """Test the symptom matcher."""
    print("=" * 60)
    print("SYMPTOM MATCHER TEST")
    print("=" * 60)
    
    matcher = SymptomMatcher()
    
    # Test cases: (description, expected symptoms)
    test_cases = [
        ("car runs rough at idle", ["rough idle"]),
        ("engine hesitates when I accelerate", ["hesitation"]),
        ("hard to start in the morning", ["hard start", "cold start problems"]),
        ("check engine light came on", ["check engine light"]),
        ("car overheats in traffic", ["overheating"]),
        ("battery light is on and headlights are dim", ["battery light", "dim headlights"]),
        ("engine misfires and runs rough", ["misfire", "rough idle"]),
        ("bad gas mileage lately", ["poor fuel economy"]),
        ("car stalls when I stop", ["stalling"]),
        ("cooling fan doesn't turn on", ["fan not running"]),
    ]
    
    for description, expected in test_cases:
        print(f"\n{'-' * 60}")
        print(f"Input: '{description}'")
        print(f"Expected: {expected}")
        
        matches = matcher.match(description)
        matched_symptoms = [m.matched_symptoms[0] for m in matches]
        
        print(f"Got: {matched_symptoms}")
        
        # Check if expected symptoms are in results
        for exp in expected:
            if exp in matched_symptoms:
                print(f"  ✓ Found '{exp}'")
            else:
                print(f"  ✗ Missing '{exp}'")
    
    # Test normalization
    print(f"\n{'=' * 60}")
    print("NORMALIZATION TEST")
    print("=" * 60)
    
    informal_symptoms = [
        "rough idle",  # Already canonical
        "car hesitates",  # Informal
        "engine gets hot",  # Informal
        "CEL on",  # Abbreviated
    ]
    
    normalized = matcher.normalize_symptoms(informal_symptoms)
    print(f"Input: {informal_symptoms}")
    print(f"Normalized: {normalized}")


if __name__ == "__main__":
    test_symptom_matcher()
