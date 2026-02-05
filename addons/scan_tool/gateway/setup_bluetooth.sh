#!/bin/bash
# ELM327 Bluetooth Setup Script for Ubuntu
#
# This script helps pair and connect your ELM327 Bluetooth adapter
#
# Usage: ./setup_bluetooth.sh

set -e

echo "=========================================="
echo "  ELM327 Bluetooth Setup for Ubuntu"
echo "=========================================="
echo ""

# Check if running as root for some operations
if [ "$EUID" -ne 0 ]; then
    echo "Note: Some operations may need sudo"
fi

# Check Bluetooth is available
echo "1. Checking Bluetooth..."
if ! command -v bluetoothctl &> /dev/null; then
    echo "   ❌ bluetoothctl not found. Install with:"
    echo "      sudo apt install bluez"
    exit 1
fi

if ! systemctl is-active --quiet bluetooth; then
    echo "   Starting Bluetooth service..."
    sudo systemctl start bluetooth
fi
echo "   ✓ Bluetooth service is running"

# Scan for devices
echo ""
echo "2. Scanning for ELM327 devices..."
echo "   (Make sure your ELM327 is powered on)"
echo ""

# List paired devices first
echo "   Paired devices:"
bluetoothctl paired-devices 2>/dev/null || echo "   (none)"
echo ""

echo "   Scanning for new devices (10 seconds)..."
timeout 10 bluetoothctl scan on 2>/dev/null &
sleep 10
bluetoothctl scan off 2>/dev/null || true

echo ""
echo "   Found devices:"
bluetoothctl devices 2>/dev/null | grep -i "OBD\|ELM\|VGATE\|VEEPEAK\|Vlink\|BAFX" || echo "   (No ELM327-like devices found - check device name)"
echo ""

# Get device address from user
echo "3. Enter the Bluetooth MAC address of your ELM327"
echo "   (Format: XX:XX:XX:XX:XX:XX)"
echo "   Common names: OBDII, VEEPEAK, Vlink, BAFX, ELM327"
echo ""
read -p "   MAC Address: " MAC_ADDRESS

if [ -z "$MAC_ADDRESS" ]; then
    echo "   ❌ No address provided"
    exit 1
fi

# Pair and trust
echo ""
echo "4. Pairing with $MAC_ADDRESS..."
echo "   (PIN is usually 1234 or 0000)"
echo ""

bluetoothctl << EOF
power on
agent on
default-agent
pair $MAC_ADDRESS
trust $MAC_ADDRESS
quit
EOF

echo ""
echo "5. Creating serial port connection..."

# Create rfcomm binding
echo "   Creating /dev/rfcomm0..."
sudo rfcomm release 0 2>/dev/null || true
sudo rfcomm bind 0 $MAC_ADDRESS

# Check if successful
if [ -e /dev/rfcomm0 ]; then
    echo "   ✓ /dev/rfcomm0 created successfully!"
    
    # Set permissions
    sudo chmod 666 /dev/rfcomm0
    echo "   ✓ Permissions set"
    
    echo ""
    echo "=========================================="
    echo "  ✅ Setup Complete!"
    echo "=========================================="
    echo ""
    echo "  Your ELM327 is available at: /dev/rfcomm0"
    echo ""
    echo "  Start the gateway server with:"
    echo "    cd $(dirname $0)/../.."
    echo "    python -m addons.scan_tool.gateway.server"
    echo ""
    echo "  Then on your iPhone, open Safari and go to:"
    echo "    http://$(hostname -I | awk '{print $1}'):8327/ui"
    echo ""
    echo "  To make this persist across reboots, add to /etc/rc.local:"
    echo "    rfcomm bind 0 $MAC_ADDRESS"
    echo ""
else
    echo "   ❌ Failed to create /dev/rfcomm0"
    echo "   Try manually:"
    echo "     sudo rfcomm bind 0 $MAC_ADDRESS"
fi
