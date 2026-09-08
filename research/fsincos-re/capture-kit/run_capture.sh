#!/bin/sh
# x87 FSINCOS capture — builds the harness, runs the input sweeps under
# three FPU rounding modes plus standalone FSIN/FCOS, and packs the results
# for return.  The output tarball is ~15-20 MB (the hex significands do not
# compress much); that size is expected, not an error.
# Requirements: Linux on an x86-64 CPU, gcc.  Takes well under a minute.
# Nothing is installed and nothing outside this directory is written.
set -e
cd "$(dirname "$0")"
gcc -O2 -o x87_capture x87_capture.c
mkdir -p out
sh ./cpu_info.sh > out/cpu_info.txt 2>&1
VENDOR=$(grep -m1 vendor_id /proc/cpuinfo 2>/dev/null | awk '{print $3}')
MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | tr -cd '[:alnum:]._-' | cut -c1-40)
echo "CPU: $VENDOR $MODEL"
./x87_capture rn < inputs/sweep_inputs.txt  > out/sweep_rn.txt
./x87_capture rn < inputs/dense_qn.txt      > out/dense_rn.txt
./x87_capture rd < inputs/dense_qn.txt      > out/dense_rd.txt
./x87_capture ru < inputs/dense_qn.txt      > out/dense_ru.txt
./x87_capture rn sin < inputs/dense_qn.txt  > out/dense_fsin.txt
./x87_capture rn cos < inputs/dense_qn.txt  > out/dense_fcos.txt
./x87_capture rn < inputs/constraint_narrow_h59.txt > out/constraint_narrow_rn.txt
./x87_capture rd < inputs/constraint_narrow_h59.txt > out/constraint_narrow_rd.txt
./x87_capture ru < inputs/constraint_narrow_h59.txt > out/constraint_narrow_ru.txt
./x87_capture rn < inputs/constraint_mwidth_h62.txt > out/constraint_mwidth_rn.txt
./x87_capture rd < inputs/constraint_mwidth_h62.txt > out/constraint_mwidth_rd.txt
./x87_capture ru < inputs/constraint_mwidth_h62.txt > out/constraint_mwidth_ru.txt
./x87_capture rn < inputs/constraint_poly_h65.txt > out/constraint_poly_rn.txt
./x87_capture rd < inputs/constraint_poly_h65.txt > out/constraint_poly_rd.txt
./x87_capture ru < inputs/constraint_poly_h65.txt > out/constraint_poly_ru.txt
./x87_capture rn < inputs/constraint_poly_round75_h71.txt > out/constraint_poly_round75_rn.txt
./x87_capture rd < inputs/constraint_poly_round75_h71.txt > out/constraint_poly_round75_rd.txt
./x87_capture ru < inputs/constraint_poly_round75_h71.txt > out/constraint_poly_round75_ru.txt
./x87_capture rn < inputs/constraint_poly_product_h74.txt > out/constraint_poly_product_rn.txt
./x87_capture rd < inputs/constraint_poly_product_h74.txt > out/constraint_poly_product_rd.txt
./x87_capture ru < inputs/constraint_poly_product_h74.txt > out/constraint_poly_product_ru.txt
./x87_capture rn < inputs/constraint_wide_producer_h67.txt > out/constraint_wide_producer_rn.txt
./x87_capture rd < inputs/constraint_wide_producer_h67.txt > out/constraint_wide_producer_rd.txt
./x87_capture ru < inputs/constraint_wide_producer_h67.txt > out/constraint_wide_producer_ru.txt
./x87_capture rn < inputs/constraint_paired_table_h78.txt > out/constraint_paired_table_rn.txt
./x87_capture rd < inputs/constraint_paired_table_h78.txt > out/constraint_paired_table_rd.txt
./x87_capture ru < inputs/constraint_paired_table_h78.txt > out/constraint_paired_table_ru.txt
./x87_capture rn < inputs/constraint_small_h83.txt > out/constraint_small_rn.txt
./x87_capture rd < inputs/constraint_small_h83.txt > out/constraint_small_rd.txt
./x87_capture ru < inputs/constraint_small_h83.txt > out/constraint_small_ru.txt
./x87_capture rn < inputs/constraint_small_width_h85.txt > out/constraint_small_width_rn.txt
./x87_capture rd < inputs/constraint_small_width_h85.txt > out/constraint_small_width_rd.txt
./x87_capture ru < inputs/constraint_small_width_h85.txt > out/constraint_small_width_ru.txt
./x87_capture rn < inputs/constraint_small_chop_h87.txt > out/constraint_small_chop_rn.txt
./x87_capture rd < inputs/constraint_small_chop_h87.txt > out/constraint_small_chop_rd.txt
./x87_capture ru < inputs/constraint_small_chop_h87.txt > out/constraint_small_chop_ru.txt
./x87_capture rn < inputs/constraint_small_deep_h89.txt > out/constraint_small_deep_rn.txt
./x87_capture rd < inputs/constraint_small_deep_h89.txt > out/constraint_small_deep_rd.txt
./x87_capture ru < inputs/constraint_small_deep_h89.txt > out/constraint_small_deep_ru.txt
./x87_capture rn < inputs/constraint_table_residual_h93.txt > out/constraint_table_residual_rn.txt
./x87_capture rd < inputs/constraint_table_residual_h93.txt > out/constraint_table_residual_rd.txt
./x87_capture ru < inputs/constraint_table_residual_h93.txt > out/constraint_table_residual_ru.txt
./x87_capture rn < inputs/constraint_table_local_h95.txt > out/constraint_table_local_rn.txt
./x87_capture rd < inputs/constraint_table_local_h95.txt > out/constraint_table_local_rd.txt
./x87_capture ru < inputs/constraint_table_local_h95.txt > out/constraint_table_local_ru.txt
./x87_capture rn < inputs/constraint_narrow_coefficient_h97.txt > out/constraint_narrow_coefficient_rn.txt
./x87_capture rd < inputs/constraint_narrow_coefficient_h97.txt > out/constraint_narrow_coefficient_rd.txt
./x87_capture ru < inputs/constraint_narrow_coefficient_h97.txt > out/constraint_narrow_coefficient_ru.txt
./x87_capture rn < inputs/constraint_round24_parameters_h107.txt > out/constraint_round24_parameters_rn.txt
./x87_capture rd < inputs/constraint_round24_parameters_h107.txt > out/constraint_round24_parameters_rd.txt
./x87_capture ru < inputs/constraint_round24_parameters_h107.txt > out/constraint_round24_parameters_ru.txt
./x87_capture rn < inputs/constraint_reduced_table_parameters_h108.txt > out/constraint_reduced_table_parameters_rn.txt
./x87_capture rd < inputs/constraint_reduced_table_parameters_h108.txt > out/constraint_reduced_table_parameters_rd.txt
./x87_capture ru < inputs/constraint_reduced_table_parameters_h108.txt > out/constraint_reduced_table_parameters_ru.txt
( cd out && sha256sum *.txt > SHA256SUMS ) 2>/dev/null || ( cd out && shasum -a 256 *.txt > SHA256SUMS )
TAG="${VENDOR:-unknown}-$(echo "$MODEL" | tr ' ' '_' )-$(date -u +%Y%m%d)"
tar czf "capture-$TAG.tar.gz" out
echo ""
echo "DONE.  Please send back: capture-$TAG.tar.gz  (~15-20 MB is normal)"
