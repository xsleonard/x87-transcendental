#!/bin/bash
# h412: collect terminal-carrier traces for all hostile-set inputs.
set -e
cd /home/coduoserver/fsincos-residual-20260807-1
make -C src fsincos_skylake 2>&1 | tail -1
COMMON="--round18-poly --round21-table-bias --round23-narrow-coefficient \
 --round24-table-delta-rn67 --round29-p5-fmul-route \
 --round30-fsin-cosine-square --round31-fsin-cosine-tail \
 --round32-fsin-cosine-horner --round33-fsin-cosine-product \
 --round34-table-lookup-firc --round35-table-p-terminal \
 --round36-table-fadd-microcontrol --round37-p6-four-term \
 --round41-fsin-cosine-split --round42-p6-sine-split \
 --round43-p6-sine-bias --round44-p6-sine-bias \
 --round45-p6-sine-fraction --round46-p6-narrow-sine-fraction \
 --round47-p6-narrow-sine-fraction --round48-p6-narrow-sine-fraction \
 --round49-p6-carrier-interval --round50-fsin-operation-classes"
FCOS="--fcos-standalone $COMMON --round38-p6-cosine-split --round39-fcos-tiny \
 --round52-fcos-low3-carrier --round53-fcos-operation-classes"
mkdir -p h412
declare -A SETS=(
  [h363]=capture-kit/inputs/constraint_fcos_terminal_neighbors_h363.txt
  [h372]=capture-kit/inputs/constraint_fcos_scaled_tail_h372.txt
  [h380]=capture-kit/inputs/constraint_fcos_payload_h380.txt
  [h384]=capture-kit/inputs/constraint_fcos_payload_h384.txt
)
for s in h363 h372 h380 h384; do
  IN=${SETS[$s]}
  src/fsincos_skylake --batch $FCOS --debug-cosine-carrier < $IN > /dev/null 2> h412/${s}_trace.txt
  echo "$s: $(wc -l < h412/${s}_trace.txt) traces / $(wc -l < $IN) inputs"
done
