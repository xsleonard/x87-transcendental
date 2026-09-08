#!/bin/sh
# H1712: frozen fresh paired tuples only. A partial run must never be restarted.
set -eu
[ "$#" -eq 1 ] || exit 2
BIN=$1
[ -x "$BIN" ] && [ ! -e hardware-output ] && [ ! -e OPENED.json ] || exit 2
sha256sum -c CHECKSUMS.sha256
[ "$(sha256sum "$BIN" | cut -d ' ' -f 1)" = "2a2adae7cf86348e78c6c5a3cd35c18762971b19542fdafcee52d9fabf369a82" ] || exit 2
EXPECTED=$(wc -l < inputs.txt)
[ "$EXPECTED" -eq 13800 ] || exit 2
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
echo "H1712_CAPTURE_COMPLETE tuples=$EXPECTED retries=0"
