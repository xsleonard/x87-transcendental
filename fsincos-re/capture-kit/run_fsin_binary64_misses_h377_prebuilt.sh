#!/bin/sh
# Compiler-free recapture of the frozen standalone-FSIN binary64 residuals.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

INPUT=inputs/fsin_binary64_misses_h377.txt
OUT=${1:-fsin-binary64-misses-h377-out}
[ -r "$INPUT" ] || {
    echo "missing input file: $INPUT"
    exit 1
}
mkdir -p "$OUT"
cp "$INPUT" "$OUT/inputs.txt"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
for RC in rn rd ru; do
    "./$BIN" "$RC" sin --status \
        < "$INPUT" > "$OUT/fsin_${RC}_status.txt"
    echo " $RC done"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || true
echo "DONE: $OUT"
