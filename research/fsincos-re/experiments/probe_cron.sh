#!/bin/bash
# Cron/timer wrapper for the ledger epoch probe (i7).  Runs the
# standing probe, and if the capture-vs-banked match is not N/N
# (or the probe fails to produce a line), appends the evidence to
# EPOCH_ALERTS.log and to /root/EPOCH_ALERT — check both at session
# start.  A flip here is an epoch transition: stop and investigate
# before trusting any capture.
set -u
cd /root/r84
line=$(bash probe_ledger.sh cron 2>/dev/null | tail -1)
m=$(printf '%s' "$line" | grep -o "match=[0-9]*/[0-9]*" || true)
a=${m#match=}; a=${a%%/*}; b=${m##*/}
if [ -z "$m" ] || [ "$a" != "$b" ]; then
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "$ts ALERT: $line" >> /root/r84/EPOCH_ALERTS.log
  echo "$ts ALERT (i7 ledger probe): $line" >> /root/EPOCH_ALERT
fi
