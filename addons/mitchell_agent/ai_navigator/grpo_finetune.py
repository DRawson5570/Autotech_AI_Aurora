#!/usr/bin/env python3
"""
GRPO Fine-Tuning Script for Mitchell Navigator
===============================================

Uses collected training data to fine-tune a small model via GRPO
(Group Relative Policy Optimization).

Prerequisites:
- CUDA-enabled GPU (T4 minimum, A100 recommended)
- Collected training data from rft_live_training.py
- pip install unsloth trl transformers

Based on OpenAI's RFT notebook:
https://colab.research.google.com/github/openai/gpt-oss/blob/main/examples/reinforcement-fine-tuning.ipynb

Model options (smallest to largest):
- Qwen/Qwen2.5-0.5B-Instruct (500M params) - Very fast
- Qwen/Qwen2.5-1.5B-Instruct (1.5B params) - Good balance  
- microsoft/Phi-3-mini-4k-instruct (3.8B params) - Higher quality
- unsloth/llama-3.2-1B-Instruct (1B params) - Llama family

Usage:
1. Collect training data: python -m addons.mitchell_agent.ai_navigator.rft_live_training --episodes 100
2. Run this script: python -m addons.mitchell_agent.ai_navigator.grpo_finetune
3. Export fine-tuned model to Ollama
"""

import json
import os
import random
from pathlib import Path
from typing import Optional

# Training data file from live training
TRAINING_DATA_FILE = Path(os.environ.get("MITCHELL_RFT_TRAINING_FILE", "/tmp/rft_training_data.jsonl"))

# Section keywords for reward validation
SECTION_KEYWORDS = {
    "Fluid Capacities": ["qt", "quart", "liter", "oil", "coolant", "ATF", "DOT"],
    "Common Specs": ["ft-lb", "nm", "torque", "gap", "mm", "inch", "clearance"],
    "Tire Information": ["psi", "kPa", "tire", "pressure", "P", "R"],
    "Reset Procedures": ["reset", "relearn", "maintenance", "oil life"],
    "DTC Index": ["P0", "P1", "P2", "code", "misfire", "catalyst"],
    "Wiring Diagrams": ["wire", "circuit", "connector", "pin", "ground"],
    "TSBs": ["TSB", "bulletin", "recall", "campaign"],
}


def load_training_data() -> list[dict]:
    """Load collected training samples."""
    if not TRAINING_DATA_FILE.exists():
        print(f"No training data found at {TRAINING_DATA_FILE}")
        print("Run rft_live_training.py first to collect data!")
        return []
    
    samples = []
    with open(TRAINING_DATA_FILE) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"Loaded {len(samples)} training samples")
    return samples


def create_grpo_prompt_template() -> str:
    """
    Create the prompt template for GRPO training.
    
    This is what the model sees and must respond to.
    """
    return """You are an automotive navigation AI. Given a user query about a vehicle, 
analyze the available page elements and decide which one to click.

VEHICLE: {vehicle}
QUERY: {query}

PAGE ELEMENTS:
{elements}

Your task: Pick the element ID most likely to contain information for "{query}".

Think step by step:
1. What type of information is the user asking for?
2. Which section/category would contain this?
3. Which element ID matches that section?

Respond with ONLY a JSON object:
{{"element_id": <number>, "reason": "<brief explanation>"}}"""


def extract_response(text: str) -> Optional[dict]:
    """
    Extract the JSON response from model output.
    
    Handles various formatting issues.
    """
    import re
    
    # Try to find JSON in the response
    json_match = re.search(r'\{[^}]+\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try to extract element_id manually
    id_match = re.search(r'element_id["\s:]+(\d+)', text)
    if id_match:
        return {"element_id": int(id_match.group(1)), "reason": "extracted"}
    
    return None


# ============================================================================
# REWARD FUNCTIONS (used during GRPO training)
# ============================================================================

def reward_valid_response(completions, **kwargs) -> list[float]:
    """
    Reward function: Did the model output valid JSON with element_id?
    
    +1.0: Valid JSON with element_id
    -2.0: Invalid response
    """
    scores = []
    for completion in completions:
        response_text = completion[0]["content"]
        parsed = extract_response(response_text)
        
        if parsed and isinstance(parsed.get("element_id"), int):
            scores.append(1.0)
        else:
            scores.append(-2.0)
    
    return scores


def reward_correct_section(completions, queries=None, elements_map=None, **kwargs) -> list[float]:
    """
    Reward function: Did the model pick the correct section?
    
    +10.0: Perfect match to expected section
    +2.0: Partial match
    -5.0: Wrong section
    """
    scores = []
    
    for i, completion in enumerate(completions):
        response_text = completion[0]["content"]
        parsed = extract_response(response_text)
        
        if not parsed or "element_id" not in parsed:
            scores.append(-3.0)
            continue
        
        element_id = parsed["element_id"]
        
        # Get the expected section from query info
        query = queries[i] if queries else None
        expected = kwargs.get("expected_sections", {}).get(query)
        
        # Get what element was clicked
        clicked_text = elements_map.get(element_id, "") if elements_map else ""
        
        if expected and expected.lower() in clicked_text.lower():
            scores.append(10.0)  # Perfect!
        elif expected and any(w in clicked_text.lower() for w in expected.lower().split()):
            scores.append(2.0)  # Partial match
        else:
            scores.append(-5.0)  # Wrong
    
    return scores


def reward_found_keywords(completions, extraction_results=None, expected_keywords=None, **kwargs) -> list[float]:
    """
    Reward function: Did clicking that element lead to relevant data?
    
    +5.0: Found multiple expected keywords in result
    +2.0: Found some keywords
    -3.0: Found nothing relevant
    """
    scores = []
    
    for i, completion in enumerate(completions):
        result = extraction_results[i] if extraction_results else ""
        keywords = expected_keywords[i] if expected_keywords else []
        
        if not result or not keywords:
            scores.append(-1.0)
            continue
        
        result_lower = result.lower()
        matches = sum(1 for kw in keywords if kw.lower() in result_lower)
        
        if matches >= 2:
            scores.append(5.0)
        elif matches >= 1:
            scores.append(2.0)
        else:
            scores.append(-3.0)
    
    return scores


# ============================================================================
# GRPO TRAINING (requires GPU + Unsloth)
# ============================================================================

def run_grpo_training(
    model_name: str = "unsloth/Qwen2.5-1.5B-Instruct",
    max_seq_length: int = 1024,
    lora_rank: int = 8,
    num_steps: int = 200,
):
    """
    Run GRPO training with Unsloth.
    
    This is the actual fine-tuning loop.
    """
    try:
        from unsloth import FastLanguageModel
        from trl import GRPOConfig, GRPOTrainer
        import torch
    except ImportError:
        print("=" * 60)
        print("GRPO training requires GPU and Unsloth")
        print("Install: pip install unsloth trl transformers")
        print("Run on Google Colab with GPU or local CUDA machine")
        print("=" * 60)
        return
    
    print(f"Loading model: {model_name}")
    
    # Load model with Unsloth
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        load_in_4bit=True,  # Quantization for memory
    )
    
    # Add LoRA adapters
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_rank,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", 
                       "gate_proj", "up_proj", "down_proj"],
        lora_alpha=lora_rank * 2,
        use_gradient_checkpointing="unsloth",
    )
    
    # Load training data
    training_data = load_training_data()
    if not training_data:
        return
    
    # Create dataset from training samples
    # Format: list of prompt strings
    prompt_template = create_grpo_prompt_template()
    
    dataset = []
    for sample in training_data:
        prompt = prompt_template.format(
            vehicle="2019 Honda Accord 1.5L",  # Example
            query=sample["query"],
            elements="[Example elements would go here]",
        )
        dataset.append({"prompt": prompt})
    
    # Configure GRPO training
    training_args = GRPOConfig(
        temperature=1.0,
        learning_rate=5e-5,
        weight_decay=0.01,
        warmup_ratio=0.1,
        num_generations=2,  # Number of completions to sample per prompt
        max_prompt_length=max_seq_length // 2,
        max_completion_length=max_seq_length // 2,
        max_steps=num_steps,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        logging_steps=10,
        output_dir=os.environ.get("MITCHELL_GRPO_OUTPUT_DIR", "/tmp/mitchell_grpo_output"),
        report_to="none",
    )
    
    # Create trainer with reward functions
    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[
            reward_valid_response,
            reward_correct_section,
            reward_found_keywords,
        ],
        args=training_args,
        train_dataset=dataset,
    )
    
    print("Starting GRPO training...")
    trainer.train()
    
    # Save the fine-tuned model
    output_path = os.environ.get("MITCHELL_FINETUNED_MODEL_PATH", "/tmp/mitchell_navigator_finetuned")
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)
    
    print(f"\nModel saved to: {output_path}")
    print("\nTo convert to Ollama format:")
    print(f"  ollama create mitchell-navigator -f {output_path}/Modelfile")
    
    return model, tokenizer


def create_ollama_modelfile(model_path: str) -> str:
    """
    Create Modelfile for importing into Ollama.
    """
    modelfile = f"""FROM {model_path}

TEMPLATE \"\"\"{{{{ if .System }}}}<|im_start|>system
{{{{ .System }}}}<|im_end|>
{{{{ end }}}}<|im_start|>user
{{{{ .Prompt }}}}<|im_end|>
<|im_start|>assistant
\"\"\"

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER temperature 0.1
PARAMETER num_predict 256

SYSTEM \"\"\"You are an automotive navigation AI specialized in finding technical data.
Given page elements and a user query, pick the element ID most likely to contain the answer.
Respond with JSON: {{"element_id": <number>, "reason": "<brief>"}}\"\"\"
"""
    
    return modelfile


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="GRPO Fine-tuning for Mitchell Navigator")
    parser.add_argument("--model", default="unsloth/Qwen2.5-1.5B-Instruct", 
                       help="Base model to fine-tune")
    parser.add_argument("--steps", type=int, default=200, 
                       help="Number of training steps")
    parser.add_argument("--rank", type=int, default=8, 
                       help="LoRA rank")
    parser.add_argument("--dry-run", action="store_true",
                       help="Just show training data stats, don't train")
    args = parser.parse_args()
    
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN - Training Data Analysis")
        print("=" * 60)
        
        data = load_training_data()
        if data:
            print(f"\nTotal samples: {len(data)}")
            
            # Analyze rewards
            rewards = [s.get("total_reward", 0) for s in data]
            print(f"Average reward: {sum(rewards)/len(rewards):.2f}")
            print(f"Max reward: {max(rewards):.1f}")
            print(f"Min reward: {min(rewards):.1f}")
            
            # Query distribution
            queries = {}
            for s in data:
                q = s.get("query", "unknown")
                queries[q] = queries.get(q, 0) + 1
            
            print(f"\nQuery distribution ({len(queries)} unique):")
            for q, count in sorted(queries.items(), key=lambda x: -x[1])[:10]:
                print(f"  {q}: {count}")
            
            # Section accuracy
            correct = sum(1 for s in data if s.get("rewards", {}).get("correct_section", 0) > 0)
            print(f"\nSection accuracy: {correct}/{len(data)} ({100*correct/len(data):.1f}%)")
    else:
        run_grpo_training(
            model_name=args.model,
            num_steps=args.steps,
            lora_rank=args.rank,
        )
