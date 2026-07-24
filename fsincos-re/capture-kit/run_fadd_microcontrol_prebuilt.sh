#!/bin/sh
# Focused h216 standalone-FSIN/paired-FSINCOS microcontrol capture.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true

INPUT=inputs/constraint_table_fadd_microcontrol_h216.txt
OUT=fadd-microcontrol-out
mkdir -p "$OUT"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1

for RC in rn rd ru; do
    "./$BIN" "$RC" sin --status \
        < "$INPUT" \
        > "$OUT/constraint_table_fadd_microcontrol_h216_fsin_${RC}_status.txt"
    "./$BIN" "$RC" sincos --status \
        < "$INPUT" \
        > "$OUT/constraint_table_fadd_microcontrol_h216_fsincos_${RC}_status.txt"
done

( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && md5sum *.txt > MD5SUMS ) 2>/dev/null \
  || true

tar czf fadd-microcontrol-capture.tar.gz "$OUT"
echo "DONE: fadd-microcontrol-capture.tar.gz"
