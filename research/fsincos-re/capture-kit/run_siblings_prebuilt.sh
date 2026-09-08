#!/bin/sh
# Compiler-free FPTAN/F2XM1 sibling capture for shared P6 arithmetic classes.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true
echo "using $BIN"

OUT=sibling-out
DENSE=inputs/dense_qn.txt
SWEEP=inputs/sweep_inputs.txt
TARGET=inputs/sibling_fptan_f2xm1_h245.txt
mkdir -p "$OUT"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
VENDOR=$(grep -m1 vendor_id /proc/cpuinfo 2>/dev/null | awk '{print $3}')
MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | tr -cd '[:alnum:]._-' | cut -c1-40)
echo "CPU: $VENDOR $MODEL"

for RC in rn rd ru; do
    for SET in dense sweep target; do
        case "$SET" in
            dense) INPUT=$DENSE ;;
            sweep) INPUT=$SWEEP ;;
            target) INPUT=$TARGET ;;
        esac
        for INSN in fptan f2xm1; do
            "./$BIN" "$RC" "$INSN" --status \
                < "$INPUT" > "$OUT/${SET}_${INSN}_${RC}_status.txt"
            echo " ${SET}_${INSN}_${RC}_status done"
        done
    done
done

# Precision-control falsifier on the compact hardware-blind set.
for PC in pc24 pc53 pc64; do
    for INSN in fptan f2xm1; do
        "./$BIN" rn "$PC" "$INSN" --status \
            < "$TARGET" > "$OUT/target_${INSN}_rn_${PC}_status.txt"
        echo " target_${INSN}_rn_${PC}_status done"
    done
done

for INSN in fptan f2xm1; do
    "./$BIN" rn "$INSN" --status --timing=9 \
        < "$TARGET" > "$OUT/target_${INSN}_timing.txt"
    echo " target_${INSN}_timing done"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && md5sum *.txt > MD5SUMS ) 2>/dev/null \
  || echo "(no checksum tool found - skipping; the data is still fine)"

TAG="${VENDOR:-unknown}-$(echo "${MODEL:-unknown}" | tr ' ' '_')-$(date -u +%Y%m%d 2>/dev/null || date +%Y%m%d)"
tar czf "sibling-capture-$TAG.tar.gz" "$OUT"
echo ""
echo "DONE. Please send back: sibling-capture-$TAG.tar.gz"
