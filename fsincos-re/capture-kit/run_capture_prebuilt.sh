#!/bin/sh
# x87 FSINCOS capture — PREBUILT-BINARY edition for machines without a
# compiler (old hardware booted from a live CD/USB).  Same captures as
# run_capture.sh, but uses the static binaries in bin/ instead of gcc.
# Requirements: x86 Linux with kernel >= 3.2 (any live image from the
# last decade), tar, gzip.  Run it from a writable directory — ideally
# the USB stick itself, so the output lands there directly.
# Output tarball is ~15-20 MB.  Takes a few minutes on very old CPUs.
set -e
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true
echo "using $BIN"

mkdir -p out
sh ./cpu_info.sh > out/cpu_info.txt 2>&1
VENDOR=$(grep -m1 vendor_id /proc/cpuinfo 2>/dev/null | awk '{print $3}')
MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | tr -cd '[:alnum:]._-' | cut -c1-40)
echo "CPU: $VENDOR $MODEL"

"./$BIN" rn     < inputs/sweep_inputs.txt > out/sweep_rn.txt
echo " sweep_rn done"
"./$BIN" rn     < inputs/dense_qn.txt     > out/dense_rn.txt
echo " dense_rn done"
"./$BIN" rd     < inputs/dense_qn.txt     > out/dense_rd.txt
echo " dense_rd done"
"./$BIN" ru     < inputs/dense_qn.txt     > out/dense_ru.txt
echo " dense_ru done"
"./$BIN" rn sin < inputs/dense_qn.txt     > out/dense_fsin.txt
echo " dense_fsin done"
"./$BIN" rn cos < inputs/dense_qn.txt     > out/dense_fcos.txt
echo " dense_fcos done"
"./$BIN" rn < inputs/constraint_narrow_h59.txt > out/constraint_narrow_rn.txt
echo " constraint_narrow_rn done"
"./$BIN" rd < inputs/constraint_narrow_h59.txt > out/constraint_narrow_rd.txt
echo " constraint_narrow_rd done"
"./$BIN" ru < inputs/constraint_narrow_h59.txt > out/constraint_narrow_ru.txt
echo " constraint_narrow_ru done"
"./$BIN" rn < inputs/constraint_mwidth_h62.txt > out/constraint_mwidth_rn.txt
echo " constraint_mwidth_rn done"
"./$BIN" rd < inputs/constraint_mwidth_h62.txt > out/constraint_mwidth_rd.txt
echo " constraint_mwidth_rd done"
"./$BIN" ru < inputs/constraint_mwidth_h62.txt > out/constraint_mwidth_ru.txt
echo " constraint_mwidth_ru done"
"./$BIN" rn < inputs/constraint_poly_h65.txt > out/constraint_poly_rn.txt
echo " constraint_poly_rn done"
"./$BIN" rd < inputs/constraint_poly_h65.txt > out/constraint_poly_rd.txt
echo " constraint_poly_rd done"
"./$BIN" ru < inputs/constraint_poly_h65.txt > out/constraint_poly_ru.txt
echo " constraint_poly_ru done"
"./$BIN" rn < inputs/constraint_poly_round75_h71.txt > out/constraint_poly_round75_rn.txt
echo " constraint_poly_round75_rn done"
"./$BIN" rd < inputs/constraint_poly_round75_h71.txt > out/constraint_poly_round75_rd.txt
echo " constraint_poly_round75_rd done"
"./$BIN" ru < inputs/constraint_poly_round75_h71.txt > out/constraint_poly_round75_ru.txt
echo " constraint_poly_round75_ru done"
"./$BIN" rn < inputs/constraint_poly_product_h74.txt > out/constraint_poly_product_rn.txt
echo " constraint_poly_product_rn done"
"./$BIN" rd < inputs/constraint_poly_product_h74.txt > out/constraint_poly_product_rd.txt
echo " constraint_poly_product_rd done"
"./$BIN" ru < inputs/constraint_poly_product_h74.txt > out/constraint_poly_product_ru.txt
echo " constraint_poly_product_ru done"
"./$BIN" rn < inputs/constraint_wide_producer_h67.txt > out/constraint_wide_producer_rn.txt
echo " constraint_wide_producer_rn done"
"./$BIN" rd < inputs/constraint_wide_producer_h67.txt > out/constraint_wide_producer_rd.txt
echo " constraint_wide_producer_rd done"
"./$BIN" ru < inputs/constraint_wide_producer_h67.txt > out/constraint_wide_producer_ru.txt
echo " constraint_wide_producer_ru done"
"./$BIN" rn < inputs/constraint_paired_table_h78.txt > out/constraint_paired_table_rn.txt
echo " constraint_paired_table_rn done"
"./$BIN" rd < inputs/constraint_paired_table_h78.txt > out/constraint_paired_table_rd.txt
echo " constraint_paired_table_rd done"
"./$BIN" ru < inputs/constraint_paired_table_h78.txt > out/constraint_paired_table_ru.txt
echo " constraint_paired_table_ru done"
"./$BIN" rn < inputs/constraint_small_h83.txt > out/constraint_small_rn.txt
echo " constraint_small_rn done"
"./$BIN" rd < inputs/constraint_small_h83.txt > out/constraint_small_rd.txt
echo " constraint_small_rd done"
"./$BIN" ru < inputs/constraint_small_h83.txt > out/constraint_small_ru.txt
echo " constraint_small_ru done"
"./$BIN" rn < inputs/constraint_small_width_h85.txt > out/constraint_small_width_rn.txt
echo " constraint_small_width_rn done"
"./$BIN" rd < inputs/constraint_small_width_h85.txt > out/constraint_small_width_rd.txt
echo " constraint_small_width_rd done"
"./$BIN" ru < inputs/constraint_small_width_h85.txt > out/constraint_small_width_ru.txt
echo " constraint_small_width_ru done"
"./$BIN" rn < inputs/constraint_small_chop_h87.txt > out/constraint_small_chop_rn.txt
echo " constraint_small_chop_rn done"
"./$BIN" rd < inputs/constraint_small_chop_h87.txt > out/constraint_small_chop_rd.txt
echo " constraint_small_chop_rd done"
"./$BIN" ru < inputs/constraint_small_chop_h87.txt > out/constraint_small_chop_ru.txt
echo " constraint_small_chop_ru done"
"./$BIN" rn < inputs/constraint_small_deep_h89.txt > out/constraint_small_deep_rn.txt
echo " constraint_small_deep_rn done"
"./$BIN" rd < inputs/constraint_small_deep_h89.txt > out/constraint_small_deep_rd.txt
echo " constraint_small_deep_rd done"
"./$BIN" ru < inputs/constraint_small_deep_h89.txt > out/constraint_small_deep_ru.txt
echo " constraint_small_deep_ru done"
"./$BIN" rn < inputs/constraint_table_residual_h93.txt > out/constraint_table_residual_rn.txt
echo " constraint_table_residual_rn done"
"./$BIN" rd < inputs/constraint_table_residual_h93.txt > out/constraint_table_residual_rd.txt
echo " constraint_table_residual_rd done"
"./$BIN" ru < inputs/constraint_table_residual_h93.txt > out/constraint_table_residual_ru.txt
echo " constraint_table_residual_ru done"
"./$BIN" rn < inputs/constraint_table_local_h95.txt > out/constraint_table_local_rn.txt
echo " constraint_table_local_rn done"
"./$BIN" rd < inputs/constraint_table_local_h95.txt > out/constraint_table_local_rd.txt
echo " constraint_table_local_rd done"
"./$BIN" ru < inputs/constraint_table_local_h95.txt > out/constraint_table_local_ru.txt
echo " constraint_table_local_ru done"
"./$BIN" rn < inputs/constraint_narrow_coefficient_h97.txt > out/constraint_narrow_coefficient_rn.txt
echo " constraint_narrow_coefficient_rn done"
"./$BIN" rd < inputs/constraint_narrow_coefficient_h97.txt > out/constraint_narrow_coefficient_rd.txt
echo " constraint_narrow_coefficient_rd done"
"./$BIN" ru < inputs/constraint_narrow_coefficient_h97.txt > out/constraint_narrow_coefficient_ru.txt
echo " constraint_narrow_coefficient_ru done"
"./$BIN" rn < inputs/constraint_round24_parameters_h107.txt > out/constraint_round24_parameters_rn.txt
echo " constraint_round24_parameters_rn done"
"./$BIN" rd < inputs/constraint_round24_parameters_h107.txt > out/constraint_round24_parameters_rd.txt
echo " constraint_round24_parameters_rd done"
"./$BIN" ru < inputs/constraint_round24_parameters_h107.txt > out/constraint_round24_parameters_ru.txt
echo " constraint_round24_parameters_ru done"
"./$BIN" rn < inputs/constraint_reduced_table_parameters_h108.txt > out/constraint_reduced_table_parameters_rn.txt
echo " constraint_reduced_table_parameters_rn done"
"./$BIN" rd < inputs/constraint_reduced_table_parameters_h108.txt > out/constraint_reduced_table_parameters_rd.txt
echo " constraint_reduced_table_parameters_rd done"
"./$BIN" ru < inputs/constraint_reduced_table_parameters_h108.txt > out/constraint_reduced_table_parameters_ru.txt
echo " constraint_reduced_table_parameters_ru done"

# checksums: best effort, tolerate ancient userlands
( cd out && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd out && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd out && md5sum *.txt > MD5SUMS ) 2>/dev/null \
  || echo "(no checksum tool found — skipping; the data is still fine)"

TAG="${VENDOR:-unknown}-$(echo "${MODEL:-unknown}" | tr ' ' '_')-$(date -u +%Y%m%d 2>/dev/null || date +%Y%m%d)"
tar czf "capture-$TAG.tar.gz" out
echo ""
echo "DONE.  Please send back: capture-$TAG.tar.gz  (~15-20 MB is normal)"
