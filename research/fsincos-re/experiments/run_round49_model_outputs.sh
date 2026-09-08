#!/bin/sh
# Produce paired FSINCOS outputs from the complete Round-49 C model.
set -eu

if [ "$#" -ne 3 ]; then
    echo "usage: $0 MODEL INPUT OUTPUT_DIRECTORY" >&2
    exit 2
fi
MODEL=$1
INPUT=$2
OUT=$3
mkdir -p "$OUT"

FLAGS='--batch
--round18-poly
--round21-table-bias
--round23-narrow-coefficient
--round24-table-delta-rn67
--round29-p5-fmul-route
--round30-fsin-cosine-square
--round31-fsin-cosine-tail
--round32-fsin-cosine-horner
--round33-fsin-cosine-product
--round34-table-lookup-firc
--round35-table-p-terminal
--round36-table-fadd-microcontrol
--round37-p6-four-term
--round38-p6-cosine-split
--round39-fcos-tiny
--round40-fsincos-tiny
--round41-fsin-cosine-split
--round42-p6-sine-split
--round43-p6-sine-bias
--round44-p6-sine-bias
--round45-p6-sine-fraction
--round46-p6-narrow-sine-fraction
--round47-p6-narrow-sine-fraction
--round48-p6-narrow-sine-fraction
--round49-p6-carrier-interval'

for RC in rn rd ru; do
    RC_FLAG=
    [ "$RC" = rn ] || RC_FLAG="--rc=$RC"
    # Intentional word splitting expands one fixed option per FLAGS line.
    # shellcheck disable=SC2086
    "$MODEL" $FLAGS $RC_FLAG < "$INPUT" > "$OUT/fsincos_${RC}.txt"
    echo " fsincos_${RC} model done"
done
