#!/bin/sh
# Focused replay of the h59 narrow-kernel, h62 m-width, h65/h71/h74
# polynomial, h67 wide-producer, h78 paired-table, h83-h89 small-path,
# h93/h95 table-tomography, h97 coefficient, h107 Round-24 parameter, and
# h108 reduced-path parameter discriminators.  Use this when a machine
# already has a full capture or a full recapture is inconvenient.  The
# 57,399 executions finish quickly.
set -e
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true
echo "using $BIN"

OUT=constraint-out
H59_INPUT=inputs/constraint_narrow_h59.txt
H62_INPUT=inputs/constraint_mwidth_h62.txt
H65_INPUT=inputs/constraint_poly_h65.txt
H71_INPUT=inputs/constraint_poly_round75_h71.txt
H74_INPUT=inputs/constraint_poly_product_h74.txt
H67_INPUT=inputs/constraint_wide_producer_h67.txt
H78_INPUT=inputs/constraint_paired_table_h78.txt
H83_INPUT=inputs/constraint_small_h83.txt
H85_INPUT=inputs/constraint_small_width_h85.txt
H87_INPUT=inputs/constraint_small_chop_h87.txt
H89_INPUT=inputs/constraint_small_deep_h89.txt
H93_INPUT=inputs/constraint_table_residual_h93.txt
H95_INPUT=inputs/constraint_table_local_h95.txt
H97_INPUT=inputs/constraint_narrow_coefficient_h97.txt
H107_INPUT=inputs/constraint_round24_parameters_h107.txt
H108_INPUT=inputs/constraint_reduced_table_parameters_h108.txt
mkdir -p "$OUT"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
VENDOR=$(grep -m1 vendor_id /proc/cpuinfo 2>/dev/null | awk '{print $3}')
MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | tr -cd '[:alnum:]._-' | cut -c1-40)
echo "CPU: $VENDOR $MODEL"

"./$BIN" rn < "$H59_INPUT" > "$OUT/constraint_narrow_rn.txt"
echo " constraint_narrow_rn done"
"./$BIN" rd < "$H59_INPUT" > "$OUT/constraint_narrow_rd.txt"
echo " constraint_narrow_rd done"
"./$BIN" ru < "$H59_INPUT" > "$OUT/constraint_narrow_ru.txt"
echo " constraint_narrow_ru done"
"./$BIN" rn < "$H62_INPUT" > "$OUT/constraint_mwidth_rn.txt"
echo " constraint_mwidth_rn done"
"./$BIN" rd < "$H62_INPUT" > "$OUT/constraint_mwidth_rd.txt"
echo " constraint_mwidth_rd done"
"./$BIN" ru < "$H62_INPUT" > "$OUT/constraint_mwidth_ru.txt"
echo " constraint_mwidth_ru done"
"./$BIN" rn < "$H65_INPUT" > "$OUT/constraint_poly_rn.txt"
echo " constraint_poly_rn done"
"./$BIN" rd < "$H65_INPUT" > "$OUT/constraint_poly_rd.txt"
echo " constraint_poly_rd done"
"./$BIN" ru < "$H65_INPUT" > "$OUT/constraint_poly_ru.txt"
echo " constraint_poly_ru done"
"./$BIN" rn < "$H71_INPUT" > "$OUT/constraint_poly_round75_rn.txt"
echo " constraint_poly_round75_rn done"
"./$BIN" rd < "$H71_INPUT" > "$OUT/constraint_poly_round75_rd.txt"
echo " constraint_poly_round75_rd done"
"./$BIN" ru < "$H71_INPUT" > "$OUT/constraint_poly_round75_ru.txt"
echo " constraint_poly_round75_ru done"
"./$BIN" rn < "$H74_INPUT" > "$OUT/constraint_poly_product_rn.txt"
echo " constraint_poly_product_rn done"
"./$BIN" rd < "$H74_INPUT" > "$OUT/constraint_poly_product_rd.txt"
echo " constraint_poly_product_rd done"
"./$BIN" ru < "$H74_INPUT" > "$OUT/constraint_poly_product_ru.txt"
echo " constraint_poly_product_ru done"
"./$BIN" rn < "$H67_INPUT" > "$OUT/constraint_wide_producer_rn.txt"
echo " constraint_wide_producer_rn done"
"./$BIN" rd < "$H67_INPUT" > "$OUT/constraint_wide_producer_rd.txt"
echo " constraint_wide_producer_rd done"
"./$BIN" ru < "$H67_INPUT" > "$OUT/constraint_wide_producer_ru.txt"
echo " constraint_wide_producer_ru done"
"./$BIN" rn < "$H78_INPUT" > "$OUT/constraint_paired_table_rn.txt"
echo " constraint_paired_table_rn done"
"./$BIN" rd < "$H78_INPUT" > "$OUT/constraint_paired_table_rd.txt"
echo " constraint_paired_table_rd done"
"./$BIN" ru < "$H78_INPUT" > "$OUT/constraint_paired_table_ru.txt"
echo " constraint_paired_table_ru done"
"./$BIN" rn < "$H83_INPUT" > "$OUT/constraint_small_rn.txt"
echo " constraint_small_rn done"
"./$BIN" rd < "$H83_INPUT" > "$OUT/constraint_small_rd.txt"
echo " constraint_small_rd done"
"./$BIN" ru < "$H83_INPUT" > "$OUT/constraint_small_ru.txt"
echo " constraint_small_ru done"
"./$BIN" rn < "$H85_INPUT" > "$OUT/constraint_small_width_rn.txt"
echo " constraint_small_width_rn done"
"./$BIN" rd < "$H85_INPUT" > "$OUT/constraint_small_width_rd.txt"
echo " constraint_small_width_rd done"
"./$BIN" ru < "$H85_INPUT" > "$OUT/constraint_small_width_ru.txt"
echo " constraint_small_width_ru done"
"./$BIN" rn < "$H87_INPUT" > "$OUT/constraint_small_chop_rn.txt"
echo " constraint_small_chop_rn done"
"./$BIN" rd < "$H87_INPUT" > "$OUT/constraint_small_chop_rd.txt"
echo " constraint_small_chop_rd done"
"./$BIN" ru < "$H87_INPUT" > "$OUT/constraint_small_chop_ru.txt"
echo " constraint_small_chop_ru done"
"./$BIN" rn < "$H89_INPUT" > "$OUT/constraint_small_deep_rn.txt"
echo " constraint_small_deep_rn done"
"./$BIN" rd < "$H89_INPUT" > "$OUT/constraint_small_deep_rd.txt"
echo " constraint_small_deep_rd done"
"./$BIN" ru < "$H89_INPUT" > "$OUT/constraint_small_deep_ru.txt"
echo " constraint_small_deep_ru done"
"./$BIN" rn < "$H93_INPUT" > "$OUT/constraint_table_residual_rn.txt"
echo " constraint_table_residual_rn done"
"./$BIN" rd < "$H93_INPUT" > "$OUT/constraint_table_residual_rd.txt"
echo " constraint_table_residual_rd done"
"./$BIN" ru < "$H93_INPUT" > "$OUT/constraint_table_residual_ru.txt"
echo " constraint_table_residual_ru done"
"./$BIN" rn < "$H95_INPUT" > "$OUT/constraint_table_local_rn.txt"
echo " constraint_table_local_rn done"
"./$BIN" rd < "$H95_INPUT" > "$OUT/constraint_table_local_rd.txt"
echo " constraint_table_local_rd done"
"./$BIN" ru < "$H95_INPUT" > "$OUT/constraint_table_local_ru.txt"
echo " constraint_table_local_ru done"
"./$BIN" rn < "$H97_INPUT" > "$OUT/constraint_narrow_coefficient_rn.txt"
echo " constraint_narrow_coefficient_rn done"
"./$BIN" rd < "$H97_INPUT" > "$OUT/constraint_narrow_coefficient_rd.txt"
echo " constraint_narrow_coefficient_rd done"
"./$BIN" ru < "$H97_INPUT" > "$OUT/constraint_narrow_coefficient_ru.txt"
echo " constraint_narrow_coefficient_ru done"
"./$BIN" rn < "$H107_INPUT" > "$OUT/constraint_round24_parameters_rn.txt"
echo " constraint_round24_parameters_rn done"
"./$BIN" rd < "$H107_INPUT" > "$OUT/constraint_round24_parameters_rd.txt"
echo " constraint_round24_parameters_rd done"
"./$BIN" ru < "$H107_INPUT" > "$OUT/constraint_round24_parameters_ru.txt"
echo " constraint_round24_parameters_ru done"
"./$BIN" rn < "$H108_INPUT" > "$OUT/constraint_reduced_table_parameters_rn.txt"
echo " constraint_reduced_table_parameters_rn done"
"./$BIN" rd < "$H108_INPUT" > "$OUT/constraint_reduced_table_parameters_rd.txt"
echo " constraint_reduced_table_parameters_rd done"
"./$BIN" ru < "$H108_INPUT" > "$OUT/constraint_reduced_table_parameters_ru.txt"
echo " constraint_reduced_table_parameters_ru done"

# checksums: best effort, tolerate ancient userlands
( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && md5sum *.txt > MD5SUMS ) 2>/dev/null \
  || echo "(no checksum tool found — skipping; the data is still fine)"

TAG="${VENDOR:-unknown}-$(echo "${MODEL:-unknown}" | tr ' ' '_')-$(date -u +%Y%m%d 2>/dev/null || date +%Y%m%d)"
tar czf "constraint-capture-$TAG.tar.gz" "$OUT"
echo ""
echo "DONE.  Please send back: constraint-capture-$TAG.tar.gz"
