#!/bin/sh
# Compiler-free FPTAN capture for a pre-generated h267 residual input file.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

INPUT=${1:-inputs/fptan_residual_h267.txt}
OUT=${2:-fptan-residual-out}
[ -r "$INPUT" ] || {
    echo "missing input file: $INPUT"
    echo "generate it with experiments/h267_fptan_residual_inputs.py"
    exit 1
}
mkdir -p "$OUT"
cp "$INPUT" "$OUT/inputs.txt"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
for RC in rn rd ru; do
    "./$BIN" "$RC" fptan --status \
        < "$INPUT" > "$OUT/fptan_${RC}_status.txt"
    echo " fptan_${RC}_status done"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || true
echo "DONE: $OUT"
