#!/bin/bash
# Kill all Mitchell remote agent processes and Chrome debugging instances

echo "Stopping Mitchell remote agents..."

# Kill agent processes
pkill -f "mitchell_agent.agent.service" 2>/dev/null
pkill -f "python.*mitchell_agent" 2>/dev/null
pkill -f "start_remote_agent" 2>/dev/null

# Kill Chrome with remote debugging (Mitchell browser)
echo "Stopping Chrome debugging instances..."
pkill -f "chrome.*remote-debugging-port" 2>/dev/null

# Give processes time to die
sleep 1

# Check if any agents still running
remaining=$(pgrep -f "mitchell_agent" 2>/dev/null | wc -l)
if [ "$remaining" -gt 0 ]; then
    echo "Force killing $remaining remaining agent process(es)..."
    pkill -9 -f "mitchell_agent" 2>/dev/null
fi

# Check if Chrome debugging still running
chrome_remaining=$(pgrep -f "chrome.*remote-debugging" 2>/dev/null | wc -l)
if [ "$chrome_remaining" -gt 0 ]; then
    echo "Force killing $chrome_remaining Chrome debugging process(es)..."
    pkill -9 -f "chrome.*remote-debugging" 2>/dev/null
fi

echo "Done. All Mitchell agents and Chrome debugging instances stopped."
echo "Port 9222 should now be free."
