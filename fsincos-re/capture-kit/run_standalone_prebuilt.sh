#!/bin/sh
# Standalone x87 FSIN/FCOS sibling capture for compiler-less x86 Linux.
#
# Captures standalone and paired FSIN/FCOS RN/RD/RU results plus a freshly
# cleared per-instruction status word over the 240k dense set and 50k sweep.
# It also records repeated-minimum timing for the existing polynomial and
# paired-table discriminator inputs.  Timing is useful on bare metal;
# virtual-machine scheduling/frequency noise may make it non-reproducible
# under KVM.
set -eu
cd "$(dirname "$0")"

case "$(uname -m)" in
    x86_64)                     BIN=bin/x87_capture_x86_64 ;;
    i386|i486|i586|i686)        BIN=bin/x87_capture_i686 ;;
    *) echo "unsupported machine: $(uname -m) (need x86)"; exit 1 ;;
esac
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null || true
echo "using $BIN"

OUT=standalone-out
DENSE=inputs/dense_qn.txt
SWEEP=inputs/sweep_inputs.txt
TINY=inputs/constraint_fsin_tiny_h117.txt
REDUCED_COEFFICIENT=inputs/constraint_fsin_reduced_coefficient_h130.txt
TABLE_TERMINAL=inputs/constraint_fsin_table_terminal_h135.txt
FMUL=inputs/constraint_fsin_fmul_h140.txt
COSINE_BOOLEAN=inputs/constraint_fsin_cosine_boolean_h147.txt
COSINE_BOOLEAN_BATCH=inputs/constraint_fsin_cosine_boolean_h148.txt
COSINE_TAIL=inputs/constraint_fsin_cosine_tail_h151.txt
COSINE_TWO_PREDICATE=inputs/constraint_fsin_cosine_two_predicate_h158.txt
COSINE_ROUND32_COMPOSITION=inputs/constraint_fsin_cosine_round32_composition_h161.txt
COSINE_PRODUCT=inputs/constraint_fsin_cosine_product_h163.txt
COSINE_PRODUCT_WIDTH=inputs/constraint_fsin_cosine_product_width_h165.txt
COSINE_ROUND33_OPERATION=inputs/constraint_fsin_cosine_round33_operation_h168.txt
TABLE_CORRECTION=inputs/constraint_fsin_table_correction_h171.txt
TABLE_PATH_GATE=inputs/constraint_fsin_table_path_gate_h175.txt
TABLE_JOINT_PRODUCT=inputs/constraint_table_joint_product_h183.txt
TABLE_LOOKUP_FIRC=inputs/constraint_table_lookup_firc_h185.txt
TABLE_STAGE_LOCAL=inputs/constraint_table_stage_local_h189.txt
TABLE_FADD_MICROCONTROL=inputs/constraint_table_fadd_microcontrol_h216.txt
TABLE_FADD_TREE=inputs/constraint_table_fadd_tree_h221.txt
TABLE_FADD_TREE_REFINED=inputs/constraint_table_fadd_tree_h223.txt
TABLE_FADD_TREE_FINAL=inputs/constraint_table_fadd_tree_h224.txt
POLY=inputs/constraint_poly_h65.txt
TABLE=inputs/constraint_paired_table_h78.txt
mkdir -p "$OUT"
sh ./cpu_info.sh > "$OUT/cpu_info.txt" 2>&1
VENDOR=$(grep -m1 vendor_id /proc/cpuinfo 2>/dev/null | awk '{print $3}')
MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | tr -cd '[:alnum:]._-' | cut -c1-40)
echo "CPU: $VENDOR $MODEL"

for RC in rn rd ru; do
    "./$BIN" "$RC" sin --status \
        < "$DENSE" > "$OUT/dense_fsin_${RC}_status.txt"
    echo " dense_fsin_${RC}_status done"
    "./$BIN" "$RC" cos --status \
        < "$DENSE" > "$OUT/dense_fcos_${RC}_status.txt"
    echo " dense_fcos_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$DENSE" > "$OUT/dense_fsincos_${RC}_status.txt"
    echo " dense_fsincos_${RC}_status done"
done

for RC in rn rd ru; do
    "./$BIN" "$RC" sin --status \
        < "$SWEEP" > "$OUT/sweep_fsin_${RC}_status.txt"
    echo " sweep_fsin_${RC}_status done"
    "./$BIN" "$RC" cos --status \
        < "$SWEEP" > "$OUT/sweep_fcos_${RC}_status.txt"
    echo " sweep_fcos_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$SWEEP" > "$OUT/sweep_fsincos_${RC}_status.txt"
    echo " sweep_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TINY" > "$OUT/constraint_fsin_tiny_${RC}_status.txt"
    echo " constraint_fsin_tiny_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$REDUCED_COEFFICIENT" \
        > "$OUT/constraint_fsin_reduced_coefficient_${RC}_status.txt"
    echo " constraint_fsin_reduced_coefficient_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_TERMINAL" \
        > "$OUT/constraint_fsin_table_terminal_${RC}_status.txt"
    echo " constraint_fsin_table_terminal_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$FMUL" \
        > "$OUT/constraint_fsin_fmul_${RC}_status.txt"
    echo " constraint_fsin_fmul_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_BOOLEAN" \
        > "$OUT/constraint_fsin_cosine_boolean_${RC}_status.txt"
    echo " constraint_fsin_cosine_boolean_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_BOOLEAN_BATCH" \
        > "$OUT/constraint_fsin_cosine_boolean_h148_${RC}_status.txt"
    echo " constraint_fsin_cosine_boolean_h148_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_TAIL" \
        > "$OUT/constraint_fsin_cosine_tail_h151_${RC}_status.txt"
    echo " constraint_fsin_cosine_tail_h151_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_TWO_PREDICATE" \
        > "$OUT/constraint_fsin_cosine_two_predicate_h158_${RC}_status.txt"
    echo " constraint_fsin_cosine_two_predicate_h158_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_ROUND32_COMPOSITION" \
        > "$OUT/constraint_fsin_cosine_round32_composition_h161_${RC}_status.txt"
    echo " constraint_fsin_cosine_round32_composition_h161_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_PRODUCT" \
        > "$OUT/constraint_fsin_cosine_product_h163_${RC}_status.txt"
    echo " constraint_fsin_cosine_product_h163_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_PRODUCT_WIDTH" \
        > "$OUT/constraint_fsin_cosine_product_width_h165_${RC}_status.txt"
    echo " constraint_fsin_cosine_product_width_h165_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$COSINE_ROUND33_OPERATION" \
        > "$OUT/constraint_fsin_cosine_round33_operation_h168_${RC}_status.txt"
    echo " constraint_fsin_cosine_round33_operation_h168_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_CORRECTION" \
        > "$OUT/constraint_fsin_table_correction_h171_${RC}_status.txt"
    echo " constraint_fsin_table_correction_h171_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_PATH_GATE" \
        > "$OUT/constraint_fsin_table_path_gate_h175_${RC}_status.txt"
    echo " constraint_fsin_table_path_gate_h175_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_JOINT_PRODUCT" \
        > "$OUT/constraint_table_joint_product_h183_fsin_${RC}_status.txt"
    echo " constraint_table_joint_product_h183_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_JOINT_PRODUCT" \
        > "$OUT/constraint_table_joint_product_h183_fsincos_${RC}_status.txt"
    echo " constraint_table_joint_product_h183_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_LOOKUP_FIRC" \
        > "$OUT/constraint_table_lookup_firc_h185_fsin_${RC}_status.txt"
    echo " constraint_table_lookup_firc_h185_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_LOOKUP_FIRC" \
        > "$OUT/constraint_table_lookup_firc_h185_fsincos_${RC}_status.txt"
    echo " constraint_table_lookup_firc_h185_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_STAGE_LOCAL" \
        > "$OUT/constraint_table_stage_local_h189_fsin_${RC}_status.txt"
    echo " constraint_table_stage_local_h189_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_STAGE_LOCAL" \
        > "$OUT/constraint_table_stage_local_h189_fsincos_${RC}_status.txt"
    echo " constraint_table_stage_local_h189_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_FADD_MICROCONTROL" \
        > "$OUT/constraint_table_fadd_microcontrol_h216_fsin_${RC}_status.txt"
    echo " constraint_table_fadd_microcontrol_h216_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_FADD_MICROCONTROL" \
        > "$OUT/constraint_table_fadd_microcontrol_h216_fsincos_${RC}_status.txt"
    echo " constraint_table_fadd_microcontrol_h216_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_FADD_TREE" \
        > "$OUT/constraint_table_fadd_tree_h221_fsin_${RC}_status.txt"
    echo " constraint_table_fadd_tree_h221_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_FADD_TREE" \
        > "$OUT/constraint_table_fadd_tree_h221_fsincos_${RC}_status.txt"
    echo " constraint_table_fadd_tree_h221_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_FADD_TREE_REFINED" \
        > "$OUT/constraint_table_fadd_tree_h223_fsin_${RC}_status.txt"
    echo " constraint_table_fadd_tree_h223_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_FADD_TREE_REFINED" \
        > "$OUT/constraint_table_fadd_tree_h223_fsincos_${RC}_status.txt"
    echo " constraint_table_fadd_tree_h223_fsincos_${RC}_status done"
    "./$BIN" "$RC" sin --status \
        < "$TABLE_FADD_TREE_FINAL" \
        > "$OUT/constraint_table_fadd_tree_h224_fsin_${RC}_status.txt"
    echo " constraint_table_fadd_tree_h224_fsin_${RC}_status done"
    "./$BIN" "$RC" sincos --status \
        < "$TABLE_FADD_TREE_FINAL" \
        > "$OUT/constraint_table_fadd_tree_h224_fsincos_${RC}_status.txt"
    echo " constraint_table_fadd_tree_h224_fsincos_${RC}_status done"
done

# Precision-control falsifier: PC64 is the RN sweep/h171 result already
# recorded above.  PC24 and PC53 determine whether architectural precision
# reaches standalone FSIN's internal carrier or only ordinary arithmetic.
for PC in pc24 pc53; do
    "./$BIN" rn "$PC" sin --status \
        < "$SWEEP" > "$OUT/sweep_fsin_rn_${PC}_status.txt"
    echo " sweep_fsin_rn_${PC}_status done"
    "./$BIN" rn "$PC" sin --status \
        < "$TABLE_CORRECTION" \
        > "$OUT/constraint_fsin_table_correction_h171_rn_${PC}_status.txt"
    echo " constraint_fsin_table_correction_h171_rn_${PC}_status done"
done

for NAME in poly table; do
    case "$NAME" in
        poly) INPUT=$POLY ;;
        table) INPUT=$TABLE ;;
    esac
    for INSN in sin cos sincos; do
        "./$BIN" rn "$INSN" --status --timing=9 \
            < "$INPUT" > "$OUT/${NAME}_${INSN}_timing.txt"
        echo " ${NAME}_${INSN}_timing done"
    done
done

# Checksums: best effort for old live environments.
( cd "$OUT" && sha256sum *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && shasum -a 256 *.txt > SHA256SUMS ) 2>/dev/null \
  || ( cd "$OUT" && md5sum *.txt > MD5SUMS ) 2>/dev/null \
  || echo "(no checksum tool found — skipping; the data is still fine)"

TAG="${VENDOR:-unknown}-$(echo "${MODEL:-unknown}" | tr ' ' '_')-$(date -u +%Y%m%d 2>/dev/null || date +%Y%m%d)"
tar czf "standalone-capture-$TAG.tar.gz" "$OUT"
echo ""
echo "DONE.  Please send back: standalone-capture-$TAG.tar.gz"
