#!/bin/bash
# ClarityStack bot watchdog — only starts the bot if .pending exists and bot is not running.
# Called by Claude Code durable cron every 5 minutes (断电/重启补救).

PIDFILE=/sandbox/ClarityStack/logs/discord_bot.pid
LOGFILE=/sandbox/ClarityStack/logs/discord_bot.log
PENDING_FLAG=/sandbox/ClarityStack/outbox/review/.pending
START_SCRIPT=/sandbox/ClarityStack/automation/start_bot.sh

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [watchdog] $*" >> "$LOGFILE"
}

# No pending review — nothing to do.
if [ ! -f "$PENDING_FLAG" ]; then
    exit 0
fi

# .pending exists — check if bot is already running.
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if [ -f "/proc/$PID/status" ]; then
        cmdline=$(cat /proc/$PID/cmdline 2>/dev/null | tr '\0' ' ')
        if echo "$cmdline" | grep -q "index.js"; then
            log "Bot healthy (PID $PID), .pending present — no action needed."
            exit 0
        fi
    fi
    rm -f "$PIDFILE"
fi

# Also check if start_bot.sh keepalive is already running.
for pid_dir in /proc/[0-9]*/cmdline; do
    cmdline=$(cat "$pid_dir" 2>/dev/null | tr '\0' ' ')
    if echo "$cmdline" | grep -q "start_bot.sh"; then
        log "Keepalive already running — bot restarting soon."
        exit 0
    fi
done

# .pending exists but nothing is running — start the bot.
log ".pending found but no bot/keepalive running. Launching start_bot.sh..."
nohup bash "$START_SCRIPT" >> "$LOGFILE" 2>&1 &
log "start_bot.sh launched (PID $!)."
