"""
Reinforcement Fine-Tuning (RFT) for Mitchell Navigator
======================================================

Inspired by OpenAI's GRPO approach:
https://colab.research.google.com/github/openai/gpt-oss/blob/main/examples/reinforcement-fine-tuning.ipynb

The model learns by TRYING, not from labeled examples.
We define reward functions that score its decisions.

REWARD FUNCTIONS:
1. valid_selection   - Did it pick a real element ID? (+1 or -2)
2. correct_section   - Did it pick the RIGHT section for the query type? (+10 or -5)
3. found_data        - Did extraction succeed with relevant keywords? (+5 or -3)

TRAINING LOOP:
1. Generate query (random from query bank)
2. Model sees page state and picks element_id
3. We click it and see what happens
4. Score the result
5. Update model weights via GRPO
"""

import json
import random
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# Query bank - maps queries to expected sections and validation keywords
QUERY_BANK = {
    # Fluid Capacities
    "engine oil capacity": {
        "expected_section": "Fluid Capacities",
        "validation_keywords": ["qt", "quart", "liter", "oil", "5W", "0W"],
    },
    "how much oil does it take": {
        "expected_section": "Fluid Capacities", 
        "validation_keywords": ["qt", "quart", "liter", "oil"],
    },
    "coolant capacity": {
        "expected_section": "Fluid Capacities",
        "validation_keywords": ["coolant", "gallon", "liter", "antifreeze"],
    },
    "transmission fluid type": {
        "expected_section": "Fluid Capacities",
        "validation_keywords": ["ATF", "CVT", "transmission", "fluid"],
    },
    "brake fluid type": {
        "expected_section": "Fluid Capacities",
        "validation_keywords": ["DOT", "brake", "fluid"],
    },
    
    # Common Specs (torque, gaps, etc)
    "spark plug gap": {
        "expected_section": "Common Specs",
        "validation_keywords": ["gap", "mm", "inch", "spark"],
    },
    "spark plug torque": {
        "expected_section": "Common Specs",
        "validation_keywords": ["ft-lb", "nm", "torque", "spark"],
    },
    "lug nut torque": {
        "expected_section": "Common Specs",
        "validation_keywords": ["ft-lb", "nm", "torque", "lug", "wheel"],
    },
    "valve clearance": {
        "expected_section": "Common Specs",
        "validation_keywords": ["mm", "inch", "clearance", "valve"],
    },
    "firing order": {
        "expected_section": "Common Specs",
        "validation_keywords": ["1", "2", "3", "4", "firing", "order"],
    },
    
    # Tire Information
    "tire pressure": {
        "expected_section": "Tire Information",
        "validation_keywords": ["psi", "kPa", "tire", "pressure"],
    },
    "tire size": {
        "expected_section": "Tire Information",
        "validation_keywords": ["P", "R", "tire", "size", "/"],
    },
    
    # Reset Procedures
    "oil life reset": {
        "expected_section": "Reset Procedures",
        "validation_keywords": ["reset", "oil", "life", "maintenance"],
    },
    "tpms reset": {
        "expected_section": "Reset Procedures",
        "validation_keywords": ["reset", "tpms", "sensor", "relearn"],
    },
    
    # DTC Info
    "P0300 code": {
        "expected_section": "DTC Index",
        "validation_keywords": ["misfire", "P0300", "random", "multiple"],
    },
    "P0420 meaning": {
        "expected_section": "DTC Index",
        "validation_keywords": ["catalyst", "efficiency", "P0420"],
    },
    
    # Wiring Diagrams
    "alternator wiring": {
        "expected_section": "Wiring Diagrams",
        "validation_keywords": ["wire", "alternator", "charging", "circuit"],
    },
    "fuel pump wiring": {
        "expected_section": "Wiring Diagrams",
        "validation_keywords": ["wire", "fuel", "pump", "circuit"],
    },
    
    # TSBs
    "technical service bulletins": {
        "expected_section": "TSBs",
        "validation_keywords": ["TSB", "bulletin", "recall"],
    },
}

# Section to Quick Access button mapping
SECTION_TO_BUTTON = {
    "Fluid Capacities": "Fluid Capacities",
    "Common Specs": "Common Specs",
    "Tire Information": "Tire Information & Lifting Points", 
    "Reset Procedures": "Reset Procedures",
    "DTC Index": "DTC Index",
    "Wiring Diagrams": "System Wiring Diagrams",
    "TSBs": "TSBs",
}


@dataclass
class RFTSample:
    """A single training sample with query and model's response"""
    query: str
    expected_section: str
    validation_keywords: list
    page_state_json: str  # Serialized page state
    model_response: Optional[dict] = None  # {"element_id": int, "reason": str}
    clicked_element_text: Optional[str] = None
    extraction_result: Optional[str] = None
    rewards: dict = field(default_factory=dict)
    total_reward: float = 0.0


def compute_rewards(sample: RFTSample) -> dict:
    """
    Compute reward signals for a training sample.
    
    Returns dict with individual rewards and total.
    """
    rewards = {}
    
    # 1. Valid Selection - Did it output a valid element_id?
    if sample.model_response is None:
        rewards["valid_selection"] = -2.0  # Failed to respond
    elif not isinstance(sample.model_response.get("element_id"), int):
        rewards["valid_selection"] = -2.0  # Invalid format
    else:
        rewards["valid_selection"] = 1.0  # Valid response
    
    # 2. Correct Section - Did it click the right category?
    if sample.clicked_element_text:
        expected = SECTION_TO_BUTTON.get(sample.expected_section, sample.expected_section)
        clicked_lower = sample.clicked_element_text.lower()
        expected_lower = expected.lower()
        
        if expected_lower in clicked_lower or clicked_lower in expected_lower:
            rewards["correct_section"] = 10.0  # Perfect!
        elif any(word in clicked_lower for word in expected_lower.split()):
            rewards["correct_section"] = 2.0  # Partial match
        else:
            rewards["correct_section"] = -5.0  # Wrong section
    else:
        rewards["correct_section"] = -3.0  # No click recorded
    
    # 3. Found Data - Did extraction find relevant keywords?
    if sample.extraction_result:
        result_lower = sample.extraction_result.lower()
        matches = sum(1 for kw in sample.validation_keywords if kw.lower() in result_lower)
        if matches >= 2:
            rewards["found_data"] = 5.0  # Found good data
        elif matches >= 1:
            rewards["found_data"] = 2.0  # Partial match
        else:
            rewards["found_data"] = -3.0  # Wrong data
    else:
        rewards["found_data"] = -1.0  # No extraction
    
    # Total reward
    total = sum(rewards.values())
    rewards["total"] = total
    
    return rewards


def generate_training_batch(batch_size: int = 10) -> list[dict]:
    """
    Generate a batch of training queries.
    
    Returns list of dicts with query info.
    """
    queries = list(QUERY_BANK.keys())
    batch = []
    
    for _ in range(batch_size):
        query = random.choice(queries)
        info = QUERY_BANK[query]
        batch.append({
            "query": query,
            "expected_section": info["expected_section"],
            "validation_keywords": info["validation_keywords"],
        })
    
    return batch


def format_reward_summary(samples: list[RFTSample]) -> str:
    """
    Format a summary of rewards across samples (like the notebook's table).
    """
    lines = [
        "| Step | Query                    | Selection | Section | Data  | Total |",
        "|------|--------------------------|-----------|---------|-------|-------|",
    ]
    
    for i, sample in enumerate(samples, 1):
        r = sample.rewards
        lines.append(
            f"| {i:4d} | {sample.query[:24]:<24} | "
            f"{r.get('valid_selection', 0):+.1f}     | "
            f"{r.get('correct_section', 0):+.1f}   | "
            f"{r.get('found_data', 0):+.1f} | "
            f"{r.get('total', 0):+.1f}  |"
        )
    
    # Summary stats
    if samples:
        totals = [s.rewards.get("total", 0) for s in samples]
        avg = sum(totals) / len(totals)
        lines.append(f"\nAverage total reward: {avg:+.2f}")
        lines.append(f"Max reward: {max(totals):+.1f}")
        lines.append(f"Min reward: {min(totals):+.1f}")
    
    return "\n".join(lines)


# For GRPO training (when we have GPU access)
def create_grpo_dataset():
    """
    Create dataset format for GRPO training.
    
    Format expected by trl.GRPOTrainer:
    - prompts: list of conversation dicts
    - rewards come from reward functions during training
    """
    from addons.mitchell_agent.ai_navigator.ai_navigator import build_navigation_prompt
    
    dataset = []
    
    # Generate diverse prompts
    vehicles = [
        {"year": "2019", "make": "Honda", "model": "Accord", "engine": "1.5L"},
        {"year": "2020", "make": "Toyota", "model": "Camry", "engine": "2.5L"},
        {"year": "2018", "make": "Ford", "model": "F-150", "engine": "3.5L"},
        {"year": "2021", "make": "Chevrolet", "model": "Silverado", "engine": "5.3L"},
    ]
    
    for query, info in QUERY_BANK.items():
        for vehicle in vehicles:
            prompt = build_navigation_prompt(query, vehicle)
            dataset.append({
                "prompt": prompt,
                "query": query,
                "expected_section": info["expected_section"],
                "validation_keywords": info["validation_keywords"],
                "vehicle": vehicle,
            })
    
    return dataset


if __name__ == "__main__":
    # Demo: show what training would look like
    print("=" * 60)
    print("RFT Training Demo for Mitchell Navigator")
    print("=" * 60)
    
    # Generate sample batch
    batch = generate_training_batch(5)
    print("\nGenerated training batch:")
    for i, item in enumerate(batch, 1):
        print(f"  {i}. {item['query']}")
        print(f"     Expected: {item['expected_section']}")
        print(f"     Keywords: {item['validation_keywords'][:3]}...")
    
    # Simulate some sample results
    print("\n" + "=" * 60)
    print("Simulated Training Results")
    print("=" * 60)
    
    samples = []
    
    # Simulate: model picks WRONG section
    s1 = RFTSample(
        query="spark plug gap",
        expected_section="Common Specs",
        validation_keywords=["gap", "mm", "inch", "spark"],
        page_state_json="{}",
        model_response={"element_id": 18, "reason": "maintenance related"},
        clicked_element_text="Fluid Capacities",  # WRONG!
        extraction_result="Engine oil: 5W-30, 4.5 qt",  # Wrong data
    )
    s1.rewards = compute_rewards(s1)
    samples.append(s1)
    
    # Simulate: model picks RIGHT section
    s2 = RFTSample(
        query="engine oil capacity",
        expected_section="Fluid Capacities",
        validation_keywords=["qt", "quart", "liter", "oil", "5W", "0W"],
        page_state_json="{}",
        model_response={"element_id": 18, "reason": "fluid info"},
        clicked_element_text="Fluid Capacities",  # RIGHT!
        extraction_result="Engine oil: 5W-30, 4.5 qt with filter",  # Right data!
    )
    s2.rewards = compute_rewards(s2)
    samples.append(s2)
    
    # Simulate: model picks right section but wrong data
    s3 = RFTSample(
        query="lug nut torque",
        expected_section="Common Specs",
        validation_keywords=["ft-lb", "nm", "torque", "lug", "wheel"],
        page_state_json="{}",
        model_response={"element_id": 19, "reason": "specs"},
        clicked_element_text="Common Specs",  # RIGHT section!
        extraction_result="Spark plug gap: 0.044 inch",  # Wrong data
    )
    s3.rewards = compute_rewards(s3)
    samples.append(s3)
    
    print(format_reward_summary(samples))
    
    print("\n" + "=" * 60)
    print("KEY INSIGHT")
    print("=" * 60)
    print("""
The model learns from these reward signals:

1. WRONG SECTION (-5): "spark plug gap" → Fluid Capacities
   Model learns: Don't click Fluid Capacities for spark plug queries

2. RIGHT SECTION (+10): "oil capacity" → Fluid Capacities  
   Model learns: Fluid Capacities is good for oil queries

3. RIGHT SECTION, WRONG DATA (+10 - 3 = +7): "lug nut torque" → Common Specs
   Model learns: Common Specs is right, but need to navigate deeper

Over many iterations, the model develops intuition for:
- Which sections contain what types of data
- How automotive terminology maps to navigation
""")
