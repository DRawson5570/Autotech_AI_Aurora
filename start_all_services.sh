#!/bin/bash
# Start all Autotech AI services
# Usage: ./start_all_services.sh

set -e

echo "Starting all Autotech AI services..."

# Check if we have sudo access
if ! sudo -n true 2>/dev/null; then
    echo "This script requires sudo access."
    echo "You may be prompted for your password."
fi

# Start nginx
echo "Starting nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Start autotech_ai service
echo "Starting autotech_ai service..."
sudo systemctl start autotech_ai
sudo systemctl enable autotech_ai

# Start mitchell-agent service
echo "Starting mitchell-agent service..."
sudo systemctl start mitchell-agent
sudo systemctl enable mitchell-agent

# Start cloudflared tunnel
echo "Starting cloudflared tunnel..."
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# Show status
echo ""
echo "=== Service Status ==="
echo ""
echo "nginx:"
sudo systemctl is-active nginx || true
echo ""
echo "autotech_ai:"
sudo systemctl is-active autotech_ai || true
echo ""
echo "mitchell-agent:"
sudo systemctl is-active mitchell-agent || true
echo ""
echo "cloudflared:"
sudo systemctl is-active cloudflared || true
echo ""
echo "All services started and enabled."
