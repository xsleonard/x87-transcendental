#!/bin/sh
# H1641: one observation per fresh full tuple. A partial run is never rerun.
# No timing, warm-up, selftest, service changes or unrelated remote actions.
set -eu
[ "$#" -eq 1 ] || exit 2
BIN=$1
[ -x "$BIN" ] || exit 2
[ ! -e hardware-output ] || exit 2
sha256sum -c CHECKSUMS.sha256
[ "$(sha256sum "$BIN" | cut -d ' ' -f 1)" = "9eef49556c7da32c270b1f1c29f777bfffbba7eb85a68ddb512e8e7e1a192af1" ] || exit 2
awk -F: '/vendor_id/ {gsub(/ /,"",$2); vendor=$2} /cpu family/ {family=$2+0} /^model[[:space:]]*:/ {model=$2+0; exit} END {exit !(vendor=="GenuineIntel" && family==6 && model==85)}' /proc/cpuinfo
# Atomic creation consumes the campaign even if a subsequent command fails.
mkdir hardware-output
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/start-utc.txt
uname -a > hardware-output/uname.txt
awk '/vendor_id|model name|cpu family|^model[[:space:]]|stepping|microcode/ {print; n++; if(n==6)exit}' /proc/cpuinfo > hardware-output/cpu-summary.txt
sha256sum "$BIN" > hardware-output/binary.sha256
for insn in sin cos; do
    for pc in pc24 pc53 pc64; do
        for rc in rn rd ru rz; do
            lane="f${insn}_${pc}_${rc}"
            "$BIN" "$rc" "$pc" "$insn" --status < "inputs/$lane.txt" > "hardware-output/$lane.txt"
        done
    done
done
sha256sum hardware-output/fsin_*.txt hardware-output/fcos_*.txt > hardware-output/outputs.sha256
date -u '+%Y-%m-%dT%H:%M:%SZ' > hardware-output/complete-utc.txt
echo 'H1641_CAPTURE_COMPLETE tuples=6432 repeats=0'
