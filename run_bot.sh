#!/bin/bash
# Run the Slack competitor insights bot.
# Usage:
#   ./run_bot.sh          - start bot (runs in background, logs to bot.log)
#   ./run_bot.sh --test   - start bot and send a digest immediately

cd "$(dirname "$0")"

# Stop any existing bot
pkill -f "slack_competitor_bot.py" 2>/dev/null
sleep 2

# Activate venv and run
source venv/bin/activate
nohup python slack_competitor_bot.py "$@" >> bot.log 2>&1 &
echo "Bot started (PID: $!). Logs: tail -f bot.log"
