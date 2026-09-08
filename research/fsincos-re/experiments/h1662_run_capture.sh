#!/bin/sh
# H1662: accepted fresh tuples only. The guard consumes even a partial run.
# Never repeat a tuple or retry a faulting instruction.
set -eu
[ "$#" -eq 1 ] || exit 2
BIN=$1
[ -x "$BIN" ] && [ ! -e hardware-output ] || exit 2
sha256sum -c CHECKSUMS.sha256
[ "$(sha256sum "$BIN" | cut -d ' ' -f 1)" = "1f0be29e0447c4b8390e3edf0b69a78f996d7c2e6293e0588ef7087cb870212e" ] || exit 2
EXPECTED=$(wc -l < inputs.txt)
[ "$EXPECTED" -gt 0 ] || exit 2
awk -F: '/vendor_id/ {gsub(/ /,"",$2); vendor=$2} /cpu family/ {family=$2+0} /^model[[:space:]]*:/ {model=$2+0; exit} END {exit !(vendor=="GenuineIntel" && family==6 && model==85)}' /proc/cpuinfo
mkdir hardware-output
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/start-utc.txt
uname -a > hardware-output/uname.txt
awk '/vendor_id|model name|cpu family|^model[[:space:]]|stepping|microcode/ {print; n++; if(n==6)exit}' /proc/cpuinfo > hardware-output/cpu-summary.txt
sha256sum "$BIN" > hardware-output/binary.sha256
"$BIN" < inputs.txt > hardware-output/state-output.txt
[ "$(wc -l < hardware-output/state-output.txt)" -eq "$EXPECTED" ] || exit 3
sha256sum hardware-output/state-output.txt > hardware-output/outputs.sha256
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/complete-utc.txt
echo "H1662_CAPTURE_COMPLETE tuples=$EXPECTED retries=0"
