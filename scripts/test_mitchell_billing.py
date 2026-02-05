#!/usr/bin/env python3
"""
Test script to verify Mitchell agent token billing is working.

This script:
1. Gets a test user's current token balance
2. Makes a Mitchell query 
3. Verifies tokens were deducted

Usage:
    cd /home/drawson/autotech_ai
    conda run -n open-webui python scripts/test_mitchell_billing.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from open_webui.models.billing import Billing, record_usage_event
from open_webui.models.users import Users


def main():
    # Use a known test user or the first user
    print("=" * 60)
    print("Mitchell Token Billing Test")
    print("=" * 60)
    
    # Find a test user
    result = Users.get_users()
    if not result:
        print("ERROR: No users found in database")
        return
    
    # Users.get_users() returns {"users": [...], "total": N}
    user_list = result.get("users", [])
    if not user_list:
        print("ERROR: No users found")
        return
    
    test_user = user_list[0]
    user_id = test_user.id
    print(f"\nTest user: {test_user.name} ({test_user.email})")
    print(f"User ID: {user_id}")
    
    # Check if user has a token balance record
    has_balance = Billing.has_user_balance_record(user_id)
    print(f"\nHas token balance record: {has_balance}")
    
    if not has_balance:
        print("Creating initial balance of 100,000 tokens for testing...")
        Billing.purchase_tokens(
            user_id=user_id,
            tokens=100000,
            cost="0.00",
            currency="USD",
            status="succeeded"
        )
    
    # Get current balance
    balance_before = Billing.get_user_balance(user_id)
    print(f"Balance BEFORE: {balance_before:,} tokens")
    
    # Simulate Mitchell agent recording usage (what happens in server/router.py)
    test_tokens = 5000  # Simulate a Mitchell query using 5000 tokens
    print(f"\nSimulating Mitchell query with {test_tokens:,} tokens...")
    
    record_usage_event(
        user_id=user_id,
        chat_id=None,
        message_id=None,
        tokens_prompt=3000,
        tokens_completion=2000,
        tokens_total=test_tokens,
        token_source="mitchell_agent_test",
    )
    
    # Get new balance
    balance_after = Billing.get_user_balance(user_id)
    print(f"Balance AFTER: {balance_after:,} tokens")
    
    # Verify deduction
    expected = balance_before - test_tokens
    if balance_after == expected:
        print(f"\n✅ SUCCESS! Tokens properly deducted: {balance_before:,} - {test_tokens:,} = {balance_after:,}")
    else:
        print(f"\n❌ FAILURE! Expected {expected:,}, got {balance_after:,}")
        print(f"   Difference: {balance_after - expected:,}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
