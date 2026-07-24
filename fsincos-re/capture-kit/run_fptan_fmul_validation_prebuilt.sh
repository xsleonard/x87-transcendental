#!/bin/sh
# Compiler-free validation of the shared ordinary-FMUL FPTAN correction.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

INPUT=inputs/fptan_fmul_h275.txt
OUT=${1:-fptan-fmul-validation-out}
mkdir -p "$OUT"
cp "$INPUT" "$OUT/inputs.txt"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
for RC in rn rd ru; do
    "./$BIN" "$RC" fptan --status \
        < "$INPUT" > "$OUT/fptan_${RC}_status.txt"
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
