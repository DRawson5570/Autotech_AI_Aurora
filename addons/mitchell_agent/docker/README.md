# Mitchell Agent Setup
# ====================
# 
# The Mitchell Agent runs at your shop and connects your ShopKeyPro account
# to Autotech AI. This allows AI-powered automotive lookups using your
# existing Mitchell subscription.
#
# Quick Start (Docker - Recommended)
# ----------------------------------
#
# 1. Install Docker:
#    - Windows: https://docs.docker.com/desktop/install/windows-install/
#    - Mac: https://docs.docker.com/desktop/install/mac-install/
#    - Linux: https://docs.docker.com/engine/install/
#
# 2. Create config file:
#    Copy config.example.json to config.json and fill in your details:
#
#    {
#      "shop_id": "abc-auto-repair",        <- Unique ID we give you
#      "mitchell_username": "your-user",     <- Your ShopKeyPro login
#      "mitchell_password": "your-pass"      <- Your ShopKeyPro password
#    }
#
# 3. Start the agent:
#    docker-compose up -d
#
# 4. Check it's running:
#    docker-compose logs -f
#
#
# Environment Variables (Alternative to config.json)
# ---------------------------------------------------
#
# You can use environment variables instead of a config file:
#
#   MITCHELL_SHOP_ID=abc-auto-repair
#   MITCHELL_USERNAME=your-user
#   MITCHELL_PASSWORD=your-pass
#   docker-compose up -d
#
#
# Manual Installation (Advanced)
# ------------------------------
#
# If you can't use Docker:
#
# 1. Install Python 3.10+
#
# 2. Install dependencies:
#    pip install httpx pydantic playwright
#    playwright install chromium
#
# 3. Set environment variables:
#    export MITCHELL_SHOP_ID=abc-auto-repair
#    export MITCHELL_USERNAME=your-user
#    export MITCHELL_PASSWORD=your-pass
#    export MITCHELL_SERVER_URL=https://automotive.aurora-sentient.net
#
# 4. Run the agent:
#    python -m addons.mitchell_agent.agent.service
#
#
# Troubleshooting
# ---------------
#
# Agent won't start:
#   - Check your ShopKeyPro credentials are correct
#   - Make sure you can access ShopKeyPro from this computer
#   - Check Docker logs: docker-compose logs
#
# Connection errors:
#   - Verify internet connectivity
#   - Check firewall allows outbound HTTPS (port 443)
#   - Verify server URL is correct
#
# Slow responses:
#   - First request may take longer (browser startup)
#   - Subsequent requests should be faster
#
#
# Support
# -------
#
# Contact: support@aurora-sentient.net
# 
