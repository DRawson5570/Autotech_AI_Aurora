#!/usr/bin/env python3
"""
Live RFT Training Loop for Mitchell Navigator
==============================================

This script runs actual browser sessions to collect training data.

Usage:
1. Start Chrome with remote debugging (user does this)
2. Navigate to ShopKeyPro main page with a vehicle selected
3. Run this script: python -m addons.mitchell_agent.ai_navigator.rft_live_training

The script will:
1. Pick a random query from the query bank
2. Show the AI the page state
3. Let the AI pick an element
4. Click it and see what happens
5. Compute rewards
6. Record the training sample
7. Reset to main page and repeat

Training data is saved to: /tmp/rft_training_data.jsonl
"""

import asyncio
import json
import os
import random
import logging
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page

from addons.mitchell_agent.ai_navigator.element_extractor import get_page_state
from addons.mitchell_agent.ai_navigator.ollama_navigator import OllamaNavigator, build_user_message_compact
from addons.mitchell_agent.ai_navigator.ai_navigator import build_navigation_prompt
from addons.mitchell_agent.ai_navigator.rft_training import (
    QUERY_BANK,
    SECTION_TO_BUTTON,
    RFTSample,
    compute_rewards,
    format_reward_summary,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TRAINING_DATA_FILE = Path(os.environ.get("MITCHELL_RFT_TRAINING_FILE", "/tmp/rft_training_data.jsonl"))


async def run_single_episode(
    page: Page,
    navigator: OllamaNavigator,
    vehicle: dict,
    query: str,
    query_info: dict,
) -> RFTSample:
    """
    Run a single training episode.
    
    1. Get page state
    2. Ask AI to pick element
    3. Click it
    4. Record what happened
    5. Compute rewards
    """
    sample = RFTSample(
        query=query,
        expected_section=query_info["expected_section"],
        validation_keywords=query_info["validation_keywords"],
        page_state_json="",
    )
    
    try:
        # 1. Get current page state
        page_state = await get_page_state(page)
        page_text = await page.evaluate('() => document.body.innerText.slice(0, 2000)')
        sample.page_state_json = json.dumps({
            "url": page.url,
            "elements_count": len(page_state.elements),
        })
        
        # 2. Build prompts and ask AI
        system_prompt = build_navigation_prompt(query, vehicle)
        user_message = build_user_message_compact(page_state, page_text, [])
        
        logger.info(f"Query: '{query}'")
        logger.info(f"Expected section: {query_info['expected_section']}")
        
        # Get AI decision
        result = await navigator.decide_action(page_state, user_message)
        
        if result.get("action") == "click" and "element_id" in result:
            element_id = result["element_id"]
            sample.model_response = {
                "element_id": element_id,
                "reason": result.get("reason", ""),
            }
            
            # Find the element
            element = next((e for e in page_state.elements if e.id == element_id), None)
            if element:
                sample.clicked_element_text = element.text or element.tag
                logger.info(f"AI chose: [{element_id}] {element.text}")
                
                # 3. Click the element
                try:
                    el = page.locator(f'[data-nav-id="{element_id}"]')
                    if await el.count() > 0:
                        await el.first.click()
                        await page.wait_for_timeout(2000)
                        
                        # 4. Record what happened - get new page text
                        new_text = await page.evaluate('() => document.body.innerText.slice(0, 3000)')
                        sample.extraction_result = new_text[:1000]
                        
                except Exception as e:
                    logger.warning(f"Click failed: {e}")
                    sample.extraction_result = f"Click error: {e}"
            else:
                sample.model_response["error"] = f"Element {element_id} not found"
                
        elif result.get("action") == "extract":
            sample.model_response = {
                "action": "extract",
                "data": result.get("data", "")[:500],
            }
            sample.extraction_result = result.get("data", "")
            
        else:
            sample.model_response = {"error": "Unknown action", "raw": str(result)[:200]}
            
    except Exception as e:
        logger.error(f"Episode error: {e}")
        sample.model_response = {"error": str(e)}
    
    # 5. Compute rewards
    sample.rewards = compute_rewards(sample)
    sample.total_reward = sample.rewards.get("total", 0)
    
    return sample


async def reset_to_main_page(page: Page):
    """Navigate back to main Quick Access page."""
    # Look for a back button or home link
    try:
        # Try clicking the vehicle selector to reset
        selector = page.locator('#vehicleSelectorButton')
        if await selector.count() > 0:
            # Already on main page if vehicle selector is visible
            return
        
        # Look for back/home button
        back = page.locator('button:has-text("Back"), a:has-text("Home")')
        if await back.count() > 0:
            await back.first.click()
            await page.wait_for_timeout(1000)
            
    except Exception as e:
        logger.warning(f"Reset navigation: {e}")


def save_sample(sample: RFTSample):
    """Append training sample to JSONL file."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "query": sample.query,
        "expected_section": sample.expected_section,
        "validation_keywords": sample.validation_keywords,
        "model_response": sample.model_response,
        "clicked_element_text": sample.clicked_element_text,
        "extraction_result": sample.extraction_result[:500] if sample.extraction_result else None,
        "rewards": sample.rewards,
        "total_reward": sample.total_reward,
    }
    
    with open(TRAINING_DATA_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


async def run_training_loop(num_episodes: int = 20):
    """
    Run the full training loop.
    
    Collects training data by running live browser sessions.
    """
    logger.info("=" * 60)
    logger.info("RFT Live Training Loop")
    logger.info("=" * 60)
    
    vehicle = {"year": "2019", "make": "Honda", "model": "Accord", "engine": "1.5L"}
    queries = list(QUERY_BANK.keys())
    
    samples: list[RFTSample] = []
    
    cdp_url = os.environ.get("CHROME_CDP_URL", "http://127.0.0.1:9222")
    async with async_playwright() as p:
        # Connect to existing Chrome
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.pages[0]
        
        # Create navigator
        navigator = OllamaNavigator(model="llama3.1:8b")
        
        logger.info(f"Connected to browser at: {page.url}")
        logger.info(f"Running {num_episodes} training episodes")
        
        for episode in range(num_episodes):
            # Pick random query
            query = random.choice(queries)
            query_info = QUERY_BANK[query]
            
            logger.info(f"\n--- Episode {episode + 1}/{num_episodes} ---")
            
            # Run episode
            sample = await run_single_episode(page, navigator, vehicle, query, query_info)
            samples.append(sample)
            
            # Log rewards
            r = sample.rewards
            logger.info(f"Rewards: selection={r.get('valid_selection', 0):+.1f}, "
                       f"section={r.get('correct_section', 0):+.1f}, "
                       f"data={r.get('found_data', 0):+.1f}, "
                       f"TOTAL={r.get('total', 0):+.1f}")
            
            # Save sample
            save_sample(sample)
            
            # Reset to main page for next episode
            await reset_to_main_page(page)
            await page.wait_for_timeout(500)
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING SUMMARY")
    logger.info("=" * 60)
    print(format_reward_summary(samples))
    
    logger.info(f"\nTraining data saved to: {TRAINING_DATA_FILE}")
    
    return samples


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="RFT Live Training for Mitchell Navigator")
    parser.add_argument("--episodes", type=int, default=10, help="Number of training episodes")
    args = parser.parse_args()
    
    await run_training_loop(num_episodes=args.episodes)


if __name__ == "__main__":
    asyncio.run(main())
