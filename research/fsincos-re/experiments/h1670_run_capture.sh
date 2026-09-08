#!/bin/sh
# H1670: accepted fresh tuples only. The guard consumes even a partial run.
# Never repeat a tuple or retry a faulting instruction.
# Bound an unexpected kernel-delivery loop; a timeout consumes the whole guard.
# Partial/missing records must never be recovered by rerunning this campaign.
set -eu
[ "$#" -eq 1 ] || exit 2
BIN=$1
[ -x "$BIN" ] && [ ! -e hardware-output ] || exit 2
sha256sum -c CHECKSUMS.sha256
[ "$(sha256sum "$BIN" | cut -d ' ' -f 1)" = "04147ce0b5f38b122dd46c2dfcf7c4b4dca3cbd846040de3873b91910115a296" ] || exit 2
EXPECTED=$(wc -l < inputs.txt)
[ "$EXPECTED" -gt 0 ] || exit 2
awk -F: '/vendor_id/ {gsub(/ /,"",$2); vendor=$2} /cpu family/ {family=$2+0} /^model[[:space:]]*:/ {model=$2+0; exit} END {exit !(vendor=="GenuineIntel" && family==6 && model==85)}' /proc/cpuinfo
mkdir hardware-output
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/start-utc.txt
uname -a > hardware-output/uname.txt
awk '/vendor_id|model name|cpu family|^model[[:space:]]|stepping|microcode/ {print; n++; if(n==6)exit}' /proc/cpuinfo > hardware-output/cpu-summary.txt
sha256sum "$BIN" > hardware-output/binary.sha256
timeout --signal=TERM --kill-after=5s 120s "$BIN" < inputs.txt > hardware-output/state-output.txt
[ "$(wc -l < hardware-output/state-output.txt)" -eq "$EXPECTED" ] || exit 3
sha256sum hardware-output/state-output.txt > hardware-output/outputs.sha256
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/complete-utc.txt
echo "H1670_CAPTURE_COMPLETE tuples=$EXPECTED retries=0"
