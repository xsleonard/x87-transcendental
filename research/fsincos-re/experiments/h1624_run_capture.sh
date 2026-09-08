#!/bin/sh
# H1624: one observation per fresh full tuple; never rerun a partial campaign.
# No timing, warm-up, selftest or repeated sampling is permitted here.
set -eu
[ "$#" -eq 1 ] || exit 2
BIN=$1
[ -x "$BIN" ] || exit 2
[ ! -e hardware-output ] || exit 2
sha256sum -c CHECKSUMS.sha256
[ "$(sha256sum "$BIN" | cut -d ' ' -f 1)" = "9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1" ] || exit 2
awk -F: '/vendor_id/ {gsub(/ /,"",$2); vendor=$2} /cpu family/ {family=$2+0} /^model[[:space:]]*:/ {model=$2+0; exit} END {exit !(vendor=="GenuineIntel" && family==6 && model==85)}' /proc/cpuinfo
# Atomic directory creation is the once-only guard, including partial failures.
mkdir hardware-output
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/start-utc.txt
uname -a > hardware-output/uname.txt
awk '/vendor_id|model name|cpu family|^model[[:space:]]|stepping|microcode/ {print; n++; if(n==6)exit}' /proc/cpuinfo > hardware-output/cpu-summary.txt
sha256sum "$BIN" > hardware-output/binary.sha256
"$BIN" rn pc64 cos --status < inputs/fcos_rn.txt > hardware-output/fcos_rn.txt
"$BIN" rd pc64 cos --status < inputs/fcos_rd.txt > hardware-output/fcos_rd.txt
"$BIN" ru pc64 cos --status < inputs/fcos_ru.txt > hardware-output/fcos_ru.txt
"$BIN" rz pc64 cos --status < inputs/fcos_rz.txt > hardware-output/fcos_rz.txt
sha256sum hardware-output/fcos_*.txt > hardware-output/outputs.sha256
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/complete-utc.txt
echo 'H1624_CAPTURE_COMPLETE tuples=1668 repeats=0'
