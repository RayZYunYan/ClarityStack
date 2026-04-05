#!/bin/bash
# ClarityStack Discord bot keepalive — run with nohup in NemoClaw sandbox
PIDFILE=/sandbox/ClarityStack/logs/discord_bot.pid
LOGFILE=/sandbox/ClarityStack/logs/discord_bot.log
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
cd /sandbox/ClarityStack
while true; do
    echo "[$(date)] Starting discord bot..." >> "$LOGFILE"
    python3 -m automation.discord_bot >> "$LOGFILE" 2>&1
    echo "[$(date)] Bot exited, restarting in 10s..." >> "$LOGFILE"
    sleep 10
done
