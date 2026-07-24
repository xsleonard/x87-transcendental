#!/bin/sh
# Compiler-free h257 F2XM1 boundary and operation-class validation capture.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

INPUT=inputs/f2xm1_validation_h257.txt
OUT=f2xm1-validation-out
mkdir -p "$OUT"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1

for RC in rn rd ru; do
    "./$BIN" "$RC" f2xm1 --status \
        < "$INPUT" \
        > "$OUT/f2xm1_validation_h257_${RC}_status.txt"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && md5sum *.txt > MD5SUMS ) 2>/dev/null \
  || true

tar czf f2xm1-validation-capture.tar.gz "$OUT"
echo "DONE: f2xm1-validation-capture.tar.gz"
