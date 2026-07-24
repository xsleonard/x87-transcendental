#!/bin/sh
# Compiler-free FSIN/FCOS/FSINCOS capture around Round-49 residual operands.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

INPUT=inputs/constraint_round49_residual_neighbors_h347.txt
OUT=${1:-round49-residual-neighbors-out}
[ -r "$INPUT" ] || {
    echo "missing input file: $INPUT"
    echo "generate it with experiments/h347_round49_residual_neighbors.py"
    exit 1
}
mkdir -p "$OUT"
cp "$INPUT" "$OUT/inputs.txt"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
for RC in rn rd ru; do
    "./$BIN" "$RC" sin --status \
        < "$INPUT" > "$OUT/fsin_${RC}_status.txt"
    "./$BIN" "$RC" cos --status \
        < "$INPUT" > "$OUT/fcos_${RC}_status.txt"
    "./$BIN" "$RC" sincos --status \
        < "$INPUT" > "$OUT/fsincos_${RC}_status.txt"
    echo " $RC done"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || true
echo "DONE: $OUT"
