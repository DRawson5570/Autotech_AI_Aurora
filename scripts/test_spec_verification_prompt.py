#!/usr/bin/env python3
"""
Test script to iterate on the spec verification prompt.

We're trying to get the model to ask users for actual values they find,
so we can build a database of verified specifications.
"""

import google.generativeai as genai

API_KEY = "AIzaSyD7Mk8zsCTtgpuvNw1m8GMAUBZ7vz9lACI"
genai.configure(api_key=API_KEY)

# The system prompt we're testing
SYSTEM_PROMPT = """You are Aurora, an expert automotive diagnostic assistant.

IMPORTANT CONTEXT - WHY WE ASK FOR FEEDBACK:
We are building a verified database of automotive specifications. When you mention 
specific values (torque specs, fluid capacities, fuse ratings, etc.), we want to 
collect the ACTUAL values that users find on their specific vehicles. This helps us:
1. Verify that our information is accurate
2. Build a database of confirmed, real-world specifications
3. Catch variations between model years, trim levels, and regional differences

HOW TO HANDLE SPECIFICATIONS:
- Share your knowledge confidently - you're an expert
- When you mention a specific numerical value, end your response by asking the user 
  to let you know what the actual spec was on their vehicle
- Frame it naturally: "Once you look it up, let me know what torque spec your manual 
  shows - it helps us keep our records accurate."
- This is a collaborative effort to build better data, not uncertainty on your part

You have 30+ years of master technician experience. Be helpful, direct, and share 
your expertise confidently."""

# Test queries that involve specs
TEST_QUERIES = [
    "What's the wheel lug nut torque for a 2018 Toyota Camry?",
    "How do I diagnose an alternator on a 2012 Jeep Liberty 3.7L?",
    "What fuse protects the fuel pump on a 2019 Chevy Silverado?",
]

def test_prompt(system_prompt: str, query: str) -> str:
    """Test a single query with the system prompt."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt
    )
    response = model.generate_content(query)
    return response.text

def main():
    print("=" * 70)
    print("TESTING SPEC VERIFICATION PROMPT")
    print("=" * 70)
    print("\nSYSTEM PROMPT:")
    print("-" * 70)
    print(SYSTEM_PROMPT)
    print("-" * 70)
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {query}")
        print("=" * 70)
        
        response = test_prompt(SYSTEM_PROMPT, query)
        print(response)
        
        # Check if it asks for feedback
        feedback_phrases = [
            "let me know", "what does your", "what did you find",
            "what spec", "what value", "what torque", "what amperage",
            "confirm", "actual"
        ]
        asks_for_feedback = any(phrase in response.lower() for phrase in feedback_phrases)
        
        print("\n" + "-" * 70)
        if asks_for_feedback:
            print("✓ ASKS FOR USER FEEDBACK")
        else:
            print("✗ DOES NOT ASK FOR FEEDBACK")
        print("-" * 70)
        
        input("\nPress Enter for next test...")

if __name__ == "__main__":
    main()
