#!/usr/bin/env python3
"""
Billing Run Script - Execute daily to charge users whose billing periods have ended.

Usage:
    python scripts/run_billing.py
    
    # Or via cron (recommended to run daily at 2am):
    0 2 * * * cd /home/drawson/autotech_ai && /home/drawson/miniconda3/envs/open-webui/bin/python scripts/run_billing.py >> /var/log/autotech_billing.log 2>&1

Environment Variables:
    STRIPE_API_KEY - Stripe secret key (required)
    DATABASE_URL - Database connection string (optional, uses default)
"""
import os
import sys
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def main():
    log.info("=" * 60)
    log.info(f"Billing Run Started at {datetime.utcnow().isoformat()}Z")
    log.info("=" * 60)
    
    # Check for Stripe API key
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        log.error("STRIPE_API_KEY environment variable not set")
        sys.exit(1)
    
    # Import billing module
    try:
        from backend.open_webui.models.billing import Billing
    except ImportError:
        # Alternative import path
        from open_webui.models.billing import Billing
    
    # Run billing
    results = Billing.run_billing(stripe_api_key)
    
    # Log results
    log.info(f"Users to bill: {results['checked']}")
    log.info(f"Invoices created: {results['invoiced']}")
    log.info(f"Successfully charged: {results['charged']}")
    log.info(f"Failed: {results['failed']}")
    log.info(f"Skipped: {results['skipped']}")
    
    # Log details
    for detail in results["details"]:
        user_id = detail["user_id"][:8] + "..."  # Truncate for privacy
        status = detail.get("status", "unknown")
        amount = detail.get("amount_cents", 0) / 100
        
        if status == "paid":
            log.info(f"  ✓ {user_id}: ${amount:.2f} charged")
        elif status == "failed":
            log.warning(f"  ✗ {user_id}: ${amount:.2f} FAILED - {detail.get('error')}")
        else:
            log.error(f"  ? {user_id}: {status} - {detail.get('error')}")
    
    log.info("=" * 60)
    log.info(f"Billing Run Complete")
    log.info("=" * 60)
    
    # Exit with error code if any failures
    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
