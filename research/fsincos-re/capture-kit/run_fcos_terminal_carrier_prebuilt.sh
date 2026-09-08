#!/bin/sh
# Compiler-free FCOS capture for terminal carrier/alignment discriminators.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

OUT=${1:-fcos-terminal-carrier-out}
mkdir -p "$OUT"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1

DATASETS="
constraint_fcos_terminal_neighbors_h363
constraint_fcos_scaled_tail_h372
constraint_fcos_payload_h380
constraint_fcos_payload_h384
constraint_fcos_tail_gate_h388
constraint_fcos_tail_gate_h389
constraint_fcos_csa_gate_h391
constraint_fcos_csa_bit_h392
constraint_fcos_square_tail_h393
constraint_fcos_square_bit_h394
constraint_fcos_d7_lane_h395
constraint_fcos_d7_lane_h397
"

for STEM in $DATASETS; do
    INPUT="inputs/${STEM}.txt"
    META="inputs/${STEM}.meta.txt"
    [ -r "$INPUT" ] || {
        echo "missing input file: $INPUT"
        exit 1
    }
    cp "$INPUT" "$OUT/${STEM}.txt"
    [ ! -r "$META" ] || cp "$META" "$OUT/${STEM}.meta.txt"
    for RC in rn rd ru; do
        "./$BIN" "$RC" cos --status \
            < "$INPUT" > "$OUT/${STEM}_fcos_${RC}_status.txt"
    done
    echo " $STEM done"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || true
echo "DONE: $OUT"
