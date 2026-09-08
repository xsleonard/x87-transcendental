#!/bin/bash
# Epoch probe (mandated by the 2026-08-19 epoch work order): capture all
# ledger keys, compare to their banked labels, append one log line.
# A change in match-count = an epoch transition; the log is the record.
cd /root/r84
TAG=${1:-cron}
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 probe_prep.py
for f in probe_in_*.txt; do
  b=${f#probe_in_}; b=${b%.txt}; insn=${b%_*}; mode=${b#*_}
  /root/x87_capture_x86_64 $mode $insn < $f > probe_out_${insn}_${mode}.txt
done
python3 probe_score.py "$TS" "$TAG" >> /root/r84/epoch_probe.log
tail -1 /root/r84/epoch_probe.log
