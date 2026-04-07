#!/bin/bash
# ClarityStack Discord bot keepalive
PIDFILE=/sandbox/ClarityStack/logs/discord_bot.pid
LOGFILE=/sandbox/ClarityStack/logs/discord_bot.log
BOT_DIR=/sandbox/ClarityStack/automation/discord_bot
mkdir -p /sandbox/ClarityStack/logs

# If a node bot process is already running, exit immediately
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if [ -f "/proc/$PID/status" ]; then
        cmdline=$(cat /proc/$PID/cmdline 2>/dev/null | tr '\0' ' ')
        if echo "$cmdline" | grep -q "index.js"; then
            echo "[$(date)] Bot already running (node PID $PID), exiting." >> "$LOGFILE"
            exit 0
        fi
    fi
    rm -f "$PIDFILE"
fi

# Install dependencies if needed
if [ ! -d "$BOT_DIR/node_modules" ]; then
    echo "[$(date)] Installing Node.js dependencies..." >> "$LOGFILE"
    npm install --prefix "$BOT_DIR" >> "$LOGFILE" 2>&1
fi

while true; do
    echo "[$(date)] Starting discord bot (Node.js)..." >> "$LOGFILE"
    /usr/local/bin/node "$BOT_DIR/index.js" >> "$LOGFILE" 2>&1 &
    NODE_PID=$!
    echo "$NODE_PID" > "$PIDFILE"
    wait "$NODE_PID"
    rm -f "$PIDFILE"
    echo "[$(date)] Bot exited, restarting in 10s..." >> "$LOGFILE"
    sleep 10
done
