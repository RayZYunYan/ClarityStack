#!/bin/bash
# ClarityStack Discord bot keepalive — Node.js version for NemoClaw sandbox
PIDFILE=/sandbox/ClarityStack/logs/discord_bot.pid
LOGFILE=/sandbox/ClarityStack/logs/discord_bot.log
BOT_DIR=/sandbox/ClarityStack/automation/discord_bot
mkdir -p /sandbox/ClarityStack/logs

# Exit if already running
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if [ -f "/proc/$PID/status" ]; then
        echo "[$(date)] Bot already running (PID $PID), exiting." >> "$LOGFILE"
        exit 0
    fi
fi

echo $$ > "$PIDFILE"

# Install dependencies if node_modules is missing
if [ ! -d "$BOT_DIR/node_modules" ]; then
    echo "[$(date)] Installing Node.js dependencies..." >> "$LOGFILE"
    npm install --prefix "$BOT_DIR" >> "$LOGFILE" 2>&1
fi

while true; do
    echo "[$(date)] Starting discord bot (Node.js)..." >> "$LOGFILE"
    /usr/local/bin/node "$BOT_DIR/index.js" >> "$LOGFILE" 2>&1
    echo "[$(date)] Bot exited, restarting in 10s..." >> "$LOGFILE"
    sleep 10
done
