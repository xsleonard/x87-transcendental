#!/bin/bash
# Ledger epoch probe, SECOND HOST (the VM).  Captures the 40 ledger
# operands on this machine's silicon and compares to the banked
# labels (bit-identical cross-machine per the determinism verdict).
# A flip here is either an epoch transition on this part or a
# machine divergence — both are stop-and-investigate events.
# Appends one line per run to epoch_probe.log; mismatches also go
# to EPOCH_ALERTS.log and /root/EPOCH_ALERT.
set -u
cd /root/fsincos-r88/probe
TAG=${1:-cron}
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 probe_prep.py
for f in probe_in_*.txt; do
  b=${f#probe_in_}; b=${b%.txt}; insn=${b%_*}; mode=${b#*_}
  ../src/x87_capture $mode $insn < $f > probe_out_${insn}_${mode}.txt
done
line=$(python3 probe_score.py "$TS" "$TAG")
echo "$line" >> epoch_probe.log
m=$(printf '%s' "$line" | grep -o "match=[0-9]*/[0-9]*" || true)
a=${m#match=}; a=${a%%/*}; b=${m##*/}
if [ -z "$m" ] || [ "$a" != "$b" ]; then
  echo "$TS ALERT: $line" >> EPOCH_ALERTS.log
  echo "$TS ALERT (VM ledger probe): $line" >> /root/EPOCH_ALERT
fi
echo "$line"
